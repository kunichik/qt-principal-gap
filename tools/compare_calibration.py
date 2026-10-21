#!/usr/bin/env python3
"""Compares a human reviewer's scores.csv with the LLM judge's scores for the same runs.

Usage: compare_calibration.py <KEY-task.json> <scores.csv> <published-repo>
Prints per-candidate scores side by side, Spearman rank correlation and mean absolute difference
per dimension.
"""
import csv, json, sys
from pathlib import Path

DIMS = ["design_match", "reviewer_concerns", "minimality", "hidden_risk"]


def ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2
        i = j + 1
    return r


def spearman(a, b):
    ra, rb = ranks(a), ranks(b)
    n = len(a); ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = sum((x - ma) ** 2 for x in ra) ** .5; vb = sum((y - mb) ** 2 for y in rb) ** .5
    return cov / (va * vb) if va and vb else float("nan")


key = json.loads(Path(sys.argv[1]).read_text())["key"]
human = {row["candidate"]: row for row in csv.DictReader(open(sys.argv[2]))}
pub = Path(sys.argv[3])
rows = []
for L, run in sorted(key.items()):
    j = json.loads((pub / run / "judge.json").read_text())
    h = human.get(L, {})
    if not h.get("design_match"):
        continue
    rows.append((L, run, {d: float(h[d]) for d in DIMS}, {d: j[d] for d in DIMS}))
print(f"{'cand':4} {'run':32} " + " ".join(f"{d[:8]:>15}" for d in DIMS))
for L, run, h, j in rows:
    print(f"{L:4} {run[8:]:32} " + " ".join(f"{h[d]:6.2f}/{j[d]:<6.2f}  " for d in DIMS))
print(f"\n{len(rows)} candidates scored (human/judge)")
for d in DIMS:
    hs, js = [r[2][d] for r in rows], [r[3][d] for r in rows]
    mad = sum(abs(x - y) for x, y in zip(hs, js)) / len(rows)
    print(f"{d:18} spearman {spearman(hs, js):5.2f}   mean |human - judge| {mad:.2f}")
