#!/usr/bin/env python3
"""Blind MAPE-style judge: compares one agent diff with the maintainer's change.

Usage: judge.py <results/task/arm/claude-N> [--model opus]
Writes judge.json next to the run. The judge never sees the arm name.
"""
import argparse, json, re, subprocess, os
from pathlib import Path
ROOT = Path(os.environ.get("QTEXP_ROOT", Path(__file__).resolve().parent))  # experiment root
import sys
sys.path.insert(0, str(ROOT))
from usermd import user_md_aside

T = ROOT / "tasks"
CFG = ROOT / "claude-cfg"
CFG.mkdir(exist_ok=True)
(ROOT / "probe").mkdir(exist_ok=True)  # empty working directory for the judge

RUBRIC = """You are reviewing a change to Qt's qtbase as a senior Qt maintainer would.

You get: (A) the task description, (B) the change the Qt maintainer actually merged, (C) the
comments reviewers made on the maintainer's change, (D) a candidate change by someone else.
Compare (D) with (B), using (C) to understand what mattered to the reviewers. Judge the source
code; ignore differences in tests and in wording of documentation unless they change meaning.

Score each dimension from 0.0 to 1.0:
- design_match: does (D) make the same key design decisions as (B)? (where logic lives, what
  is guarded, what API/ABI surface is added, which existing helpers are reused)
- reviewer_concerns: how many of the substantive concerns in (C) does (D) already satisfy?
  (if (C) has no substantive concerns, give 1.0)
- minimality: is (D) free of changes that (B) did not need? 1.0 = no unneeded changes
- hidden_risk: 1.0 = no behaviour that a test suite would likely miss but a maintainer would
  reject; 0.0 = a real bug or unsafe case remains that (B) handles
Then name the single most important difference between (D) and (B) in one sentence.

Reply with JSON only:
{"design_match": x, "reviewer_concerns": x, "minimality": x, "hidden_risk": x,
 "key_difference": "..."}
"""


def src_part(diff):
    out, keep = [], False
    for line in diff.splitlines():
        if line.startswith("diff --git"):
            keep = " a/src/" in line
        if keep:
            out.append(line)
    return "\n".join(out)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("run"); p.add_argument("--model", default="opus")
    a = p.parse_args()
    run = Path(a.run).resolve()
    task = run.parts[-3]
    prompts = (T / "prompts.md").read_text()
    m = re.search(rf"^## {task}[^\n]*\n(.*?)(?=^#{{1,2}} |\Z)", prompts, re.S | re.M)
    review = (T / task / "review.txt").read_text()[:12000] or "(no reviewer comments)"
    msg = (RUBRIC + "\n\n(A) TASK\n" + m.group(1).strip()
           + "\n\n(B) MAINTAINER CHANGE\n" + (T / task / "src.diff").read_text()
           + "\n\n(C) REVIEWER COMMENTS ON (B)\n" + review
           + "\n\n(D) CANDIDATE CHANGE\n" + src_part((run / "agent.diff").read_text()))
    token = (ROOT / ".oauth-token").read_text().strip()
    env = dict(os.environ, CLAUDE_CONFIG_DIR=str(CFG), CLAUDE_CODE_OAUTH_TOKEN=token)
    with user_md_aside():
        r = subprocess.run(["claude", "-p", "--model", a.model, "--output-format", "json",
                            "--tools", ""], input=msg, text=True, capture_output=True,
                           cwd=str(ROOT / "probe"), env=env)
    meta = json.loads(r.stdout)
    text = meta.get("result", "")
    j = json.loads(text[text.find("{"):text.rfind("}") + 1])
    j["judge_cost_usd"] = meta.get("total_cost_usd")
    (run / "judge.json").write_text(json.dumps(j, indent=1, ensure_ascii=False))
    print(json.dumps({"run": str(run.relative_to(ROOT / "results")), **j},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
