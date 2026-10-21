#!/usr/bin/env python3
"""Card auditor: does an AI catch errors in a K3 card?

Usage: auditor.py <task> <model> <tag> [--source]
  --source  also show the maintainer's merged change (ground truth the card writer lacked)
Writes audits/<task>/<tag>.json
"""
import argparse, json, os, re, subprocess, sys
from pathlib import Path
ROOT = Path(os.environ.get("QTEXP_ROOT", Path(__file__).resolve().parent))  # experiment root

sys.path.insert(0, str(ROOT))
from usermd import user_md_aside

Q = ROOT
(Q / "claude-cfg").mkdir(exist_ok=True)
(Q / "probe").mkdir(exist_ok=True)  # empty working directory for the auditors
PROMPT = """An engineer is about to implement a change in Qt's qtbase. Someone wrote a short
"card" for them: the facts a maintainer of this code would want them to know, taken from the
code review of the real change. The engineer will follow the card closely.

Check the card against the source material below. Is it a faithful, decision-useful summary?
Flag any statement that is wrong, that contradicts what the reviewers finally decided (including
decisions about what is in or out of scope), or any point the reviewers treated as essential
that the card leaves out. Do not flag style or wording.

Reply with JSON only:
{"verdict": "OK" or "NOT_OK", "problems": ["...", "..."]}
"""


def section(path, task):
    text = re.sub(r"<!--.*?-->\n?", "", path.read_text(), flags=re.S)
    m = re.search(rf"^## {task}[^\n]*\n(.*?)(?=^#{{1,2}} |\Z)", text, re.S | re.M)
    return m.group(1).strip()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("task"); p.add_argument("model"); p.add_argument("tag")
    p.add_argument("--source", action="store_true")
    a = p.parse_args()
    t = Q / "tasks" / a.task
    msg = (PROMPT
           + "\n\nTASK GIVEN TO THE ENGINEER\n" + section(Q / "tasks/prompts.md", a.task)
           + "\n\nCOMMIT MESSAGE OF THE REAL CHANGE\n" + (t / "commit.txt").read_text()
           + "\n\nREVIEW COMMENTS ON THE REAL CHANGE\n"
           + ((t / "review.txt").read_text()[:20000] or "(none)"))
    if a.source:
        msg += "\n\nTHE MERGED SOURCE CHANGE\n" + (t / "src.diff").read_text()
    msg += "\n\nTHE CARD TO CHECK\n" + section(Q / "arms/K3-cards.md", a.task)
    token = (Q / ".oauth-token").read_text().strip()
    env = dict(os.environ, CLAUDE_CONFIG_DIR=str(Q / "claude-cfg"), CLAUDE_CODE_OAUTH_TOKEN=token)
    with user_md_aside():
        r = subprocess.run(["claude", "-p", "--model", a.model, "--output-format", "json",
                            "--tools", ""], input=msg, text=True, capture_output=True,
                           cwd=str(Q / "probe"), env=env)
    meta = json.loads(r.stdout)
    if meta.get("is_error"):
        print(json.dumps({"task": a.task, "tag": a.tag, "invalid": True,
                          "reason": str(meta.get("result"))[:200]}))
        sys.exit(3)
    text = meta.get("result", "")
    j = json.loads(text[text.find("{"):text.rfind("}") + 1])
    j.update(model=a.model, source=a.source, cost_usd=meta.get("total_cost_usd"))
    out = Q / "audits" / a.task
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{a.tag}.json").write_text(json.dumps(j, indent=1, ensure_ascii=False))
    print(json.dumps({"task": a.task, "tag": a.tag, "verdict": j["verdict"],
                      "n_problems": len(j.get("problems", []))}))


if __name__ == "__main__":
    main()
