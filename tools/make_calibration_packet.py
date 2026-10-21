#!/usr/bin/env python3
"""Builds a blind packet for a human Qt reviewer to calibrate the LLM judge on one task.

The packet holds what the judge saw — task, merged change, review comments (aliased), and every
agent run's source diff under a random letter — plus a scoring sheet with the judge's rubric. The
letter-to-run key is written outside the packet; keep it away from the reviewer until the sheet
is back, then compare with tools/compare_calibration.py.

Usage: make_calibration_packet.py <task> <published-repo> <out-dir>
"""
import csv, json, random, secrets, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from judge import RUBRIC, src_part
from harness import section

task, pub, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
runs = sorted(p for p in (pub / "results" / task).glob("*/claude-*") if (p / "judge.json").exists())
seed = secrets.randbits(32)
random.Random(seed).shuffle(runs)
letters = [chr(ord("A") + i) for i in range(len(runs))]

pk = out / f"packet-{task}"
(pk / "candidates").mkdir(parents=True, exist_ok=True)
t = pub / "tasks" / task
(pk / "1-task.md").write_text(section(pub / "tasks/prompts.md", task) + "\n")
(pk / "2-merged-change.diff").write_text((t / "src.diff").read_text())
(pk / "3-review-comments.txt").write_text((t / "review.txt").read_text())
for L, r in zip(letters, runs):
    (pk / "candidates" / f"{L}.diff").write_text(src_part((r / "agent.diff").read_text()) + "\n")
# the judge's rubric (judge.py RUBRIC), reworded only to name the packet's files
rubric = """Compare each candidate with the merged change, using the review comments to understand what
mattered to the reviewers. Judge the source code; ignore differences in tests and in wording of
documentation unless they change meaning. Score each dimension from 0.0 to 1.0:

- design_match: does the candidate make the same key design decisions as the merged change? (where
  logic lives, what is guarded, what API/ABI surface is added, which existing helpers are reused)
- reviewer_concerns: how many of the substantive concerns in the review comments does the candidate
  already satisfy? (if there are no substantive concerns, give 1.0)
- minimality: is the candidate free of changes the merged change did not need? 1.0 = no unneeded
  changes
- hidden_risk: 1.0 = no behaviour that a test suite would likely miss but a maintainer would reject;
  0.0 = a real bug or unsafe case remains that the merged change handles"""
assert "design_match" in RUBRIC and "hidden_risk" in RUBRIC
(pk / "README.md").write_text(f"""# Blind scoring of {len(runs)} candidate changes — qtbase {task}

Thank you for helping. Each file in `candidates/` is a change to the same task, written
independently. Some may be close to what was merged, some not. Please do not look up who wrote
them or how anyone else scored them.

Read `1-task.md`, `2-merged-change.diff` (what was merged) and `3-review-comments.txt` (review on
Gerrit, reviewer names replaced by aliases). Then score every candidate in `scores.csv`, using the
same instructions an automated judge got:

{rubric.strip()}

`key_difference` is optional; a short phrase is enough. Rough scores are fine — the comparison is
about ranking and the large gaps, not the second decimal. Time needed: about an hour.
""")
with open(pk / "scores.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["candidate", "design_match", "reviewer_concerns", "minimality", "hidden_risk", "key_difference"])
    for L in letters:
        w.writerow([L, "", "", "", "", ""])
key = {"task": task, "seed": seed, "key": {L: str(r.relative_to(pub)) for L, r in zip(letters, runs)}}
(out / f"KEY-{task}-do-not-send.json").write_text(json.dumps(key, indent=1))
print(f"{pk}  ({len(runs)} candidates); key: {out}/KEY-{task}-do-not-send.json")
