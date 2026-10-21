#!/usr/bin/env python3
"""Card auditor through the kapt.ai pipeline qtcs_card_collegium (3 reviewers from different
vendors, one debate round, a chair).

Same prompt and material as auditor.py; only the judge differs.
Usage: kapt_auditor.py <task> [--tag kteam1] [--url https://www.kapt.ai]
Key: .kapt-key in the experiment root (created by the user). Writes audits/<task>/<tag>.json
"""
import argparse, json, sys, time, urllib.request
import os
from pathlib import Path
ROOT = Path(os.environ.get("QTEXP_ROOT", Path(__file__).resolve().parent))  # experiment root

sys.path.insert(0, str(ROOT))
from auditor import PROMPT, section  # same prompt, same card extraction

Q = ROOT


def main():
    p = argparse.ArgumentParser()
    p.add_argument("task"); p.add_argument("--tag", default="kteam1")
    p.add_argument("--url", default="https://www.kapt.ai")  # apex redirect drops auth headers
    a = p.parse_args()
    t = Q / "tasks" / a.task
    msg = (PROMPT
           + "\n\nTASK GIVEN TO THE ENGINEER\n" + section(Q / "tasks/prompts.md", a.task)
           + "\n\nCOMMIT MESSAGE OF THE REAL CHANGE\n" + (t / "commit.txt").read_text()
           + "\n\nREVIEW COMMENTS ON THE REAL CHANGE\n"
           + ((t / "review.txt").read_text()[:20000] or "(none)")
           + "\n\nTHE CARD TO CHECK\n" + section(Q / "arms/K3-cards.md", a.task))
    if len(msg) > 39000:
        msg = msg[:39000]  # API limit is 40,000 characters
    key = (Q / ".kapt-key").read_text().strip()
    req = urllib.request.Request(
        f"{a.url}/api/chat?stream=1", method="POST",
        data=json.dumps({"message": msg, "pipelineId": "qtcs_card_collegium",
                         "strategy": "conveyor", "modeAuto": False}).encode(),
        headers={"Authorization": f"Bearer {key}", "X-API-Key": key,
                 "Content-Type": "application/json", "X-User-Id": "qtexp_auditor",
                 # Cloudflare in front of kapt.ai rejects urllib's default signature (error 1010)
                 "User-Agent": "qtexp-auditor/1.0"})
    t0 = time.time()
    final, strategies, errors, types, bad_lines = None, set(), [], [], 0
    with urllib.request.urlopen(req, timeout=900) as resp:
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            try:
                ev = json.loads(line[5:].strip())
            except json.JSONDecodeError:
                bad_lines += 1
                continue
            if ev.get("type") not in ("agent_chunk", "composer_chunk"):
                types.append(ev.get("type"))
            for k in ("strategy", "executionMode"):
                if isinstance(ev.get(k), str):
                    strategies.add(ev[k])
            if ev.get("type") == "error":
                errors.append(str(ev)[:300])
            if ev.get("type") == "final":
                final = ev
    if final is None:
        print(json.dumps({"task": a.task, "tag": a.tag, "invalid": True, "errors": errors,
                          "last_events": types[-6:], "unparsed_lines": bad_lines}))
        sys.exit(3)
    text = final.get("response", "")
    try:
        j = json.loads(text[text.find("{"):text.rfind("}") + 1])
    except json.JSONDecodeError:
        j = {"verdict": "UNPARSED", "problems": [], "raw": text[:2000]}
    j.update(judge="kapt.ai qtcs_card_collegium", strategies_seen=sorted(strategies),
             cost_usd=(final.get("usage") or {}).get("costUsd"), wall_s=round(time.time() - t0),
             team=final.get("teamAnalysis"))
    out = Q / "audits" / a.task
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{a.tag}.json").write_text(json.dumps(j, indent=1, ensure_ascii=False, default=str))
    print(json.dumps({"task": a.task, "tag": a.tag, "verdict": j.get("verdict"),
                      "strategies": sorted(strategies), "cost_usd": j["cost_usd"]}))


if __name__ == "__main__":
    main()
