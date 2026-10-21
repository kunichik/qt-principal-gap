#!/usr/bin/env python3
"""Contamination probe: does the model, without tools, already know a task's merged change?

For each task it asks twice, in fresh isolated sessions: once with the Gerrit change number and
commit subject, once with the task prompt only. A model that saw the change in training should
name its decisive design point (QT-SPECIFIC-FINDINGS.md §1); one that did not should say UNKNOWN
or describe a different design. Answers go to probe-results/<task>.json for reading by hand.

Usage: probe_recognition.py [task ...]   (default: the 9 design tasks)
"""
import json, os, subprocess, sys
from pathlib import Path

ROOT = Path(os.environ.get("QTEXP_ROOT", Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(ROOT))
from usermd import user_md_aside
from harness import section

DESIGN = ["756614", "764375", "765378", "759321", "768691", "754389", "750871", "773405", "777778"]
MODEL = "claude-opus-5-5"
OUT = ROOT / "probe-results"

BY_ID = """Do you know the Qt change https://codereview.qt-project.org/c/qt/qtbase/+/{task}
("{subject}"), merged into qtbase's dev branch? Answer from memory only.

If you know it, describe what it changed and the key design decisions (where the logic lives, what
is guarded, what API is added, what was deliberately left out). If you do not know it, reply with
the single word UNKNOWN. Do not guess or reconstruct a plausible design."""

BY_TASK = """The task below was done as a change to Qt's qtbase (dev branch). Do you remember the change
the Qt maintainers actually merged for it? Answer from memory only.

If you remember it, describe the merged design and what reviewers asked for. If you do not, reply
with the single word UNKNOWN. Do not guess or reconstruct a plausible design.

TASK:
{task_text}"""


def ask(prompt):
    token = (ROOT / ".oauth-token").read_text().strip()
    env = dict(os.environ, CLAUDE_CONFIG_DIR=str(ROOT / "claude-cfg"), CLAUDE_CODE_OAUTH_TOKEN=token)
    with user_md_aside():
        r = subprocess.run(["claude", "-p", "--model", MODEL, "--output-format", "json", "--tools", ""],
                           input=prompt, text=True, capture_output=True, cwd=str(ROOT / "probe"), env=env)
    meta = json.loads(r.stdout)
    return {"answer": meta.get("result", ""), "cost_usd": meta.get("total_cost_usd")}


def main():
    OUT.mkdir(exist_ok=True)
    (ROOT / "probe").mkdir(exist_ok=True)
    for task in sys.argv[1:] or DESIGN:
        subject = (ROOT / "tasks" / task / "commit.txt").read_text().splitlines()[0]
        res = {"task": task, "model": MODEL, "subject": subject,
               "by_id": ask(BY_ID.format(task=task, subject=subject)),
               "by_task": ask(BY_TASK.format(task_text=section(ROOT / "tasks/prompts.md", task)))}
        (OUT / f"{task}.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
        print(task, "|", res["by_id"]["answer"][:80].replace("\n", " "), "|",
              res["by_task"]["answer"][:80].replace("\n", " "))


if __name__ == "__main__":
    main()
