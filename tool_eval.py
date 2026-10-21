#!/usr/bin/env python3
"""What Qt's own tools say about each patch: clazy (level1) and sanitize-commit.

For the maintainer's change and every agent run of the design tasks: reset the tree as the harness
does, apply the patch, run clazy on the changed translation units and sanitize-commit on a commit of
the patch, and keep only findings on lines the patch added. No agent runs, no subscription use.

Usage: tool_eval.py [task ...]     → results/<task>/<arm>/<run>/tools.json, summary on stdout
"""
import json, re, subprocess, sys
import os
from pathlib import Path
ROOT = Path(os.environ.get("QTEXP_ROOT", Path(__file__).resolve().parent))  # experiment root
sys.path.insert(0, str(ROOT))
import harness

Q, T, R = harness.Q, harness.T, harness.R
CLAZY = str(ROOT / "clazy-run.sh")
SANITIZE = str(ROOT / "tools/sanitize-commit")  # from qtrepotools/git-hooks
DESIGN = ["756614", "764375", "765378", "759321", "768691", "754389", "750871", "773405", "777778"]
CLAZYDB = ROOT / "clazydb/compile_commands.json"
if not CLAZYDB.exists():
    sys.exit(f"{CLAZYDB} is missing: configure the build with -DCMAKE_EXPORT_COMPILE_COMMANDS=ON, "
             "then run tools/make-clazydb.py")
COMPILED = {e["file"] for e in json.loads(CLAZYDB.read_text())}


def added_lines(diff):
    """{path: set(line numbers in the new file)} for lines the diff adds."""
    out, cur, ln = {}, None, 0
    for l in diff.splitlines():
        m = re.match(r"^\+\+\+ b/(\S+)", l)
        if m:
            cur = m.group(1); out.setdefault(cur, set()); continue
        m = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)", l)
        if m:
            ln = int(m.group(1)); continue
        if cur is None or l.startswith("---"):
            continue
        if l.startswith("+"):
            out[cur].add(ln); ln += 1
        elif l.startswith(" "):
            ln += 1
    return out


def translation_units(paths):
    """Changed .cpp files, plus a same-named .cpp for each changed header, if it is in the build."""
    tus = set()
    for p in paths:
        if "/tests/" in "/" + p:
            continue
        f = Q / p
        cand = [f] if f.suffix == ".cpp" else [f.with_suffix(".cpp"), f.with_name(f.stem.replace("_p", "") + ".cpp")]
        for c in cand:
            if str(c) in COMPILED:
                tus.add(str(c)); break
    return sorted(tus)


def run_clazy(tus, added):
    hits = []
    for tu in tus:
        r = subprocess.run([CLAZY, tu], capture_output=True, text=True, timeout=600)
        for m in re.finditer(r"^(/\S+?):(\d+):\d+: warning: (.*?) \[-W(clazy-[\w-]+)\]", r.stderr + r.stdout, re.M):
            path, line, msg, check = m.group(1), int(m.group(2)), m.group(3), m.group(4)
            rel = str(Path(path).resolve().relative_to(Q.resolve())) if path.startswith(str(Q)) else None
            if rel and line in added.get(rel, ()):
                hits.append({"file": rel, "line": line, "check": check, "msg": msg})
    return [dict(t) for t in {tuple(sorted(h.items())) for h in hits}]


def run_sanitize():
    harness.sh("git add -A && git -c user.name='Tool Evaluator' -c user.email=tool.evaluator@qt.io commit -q -m "
               "'Tool evaluation commit' -m 'Body.'", cwd=Q)
    r = subprocess.run(["perl", SANITIZE, "HEAD", "easy"], cwd=Q, capture_output=True, text=True)
    lines = [l.strip(" *") for l in (r.stdout + r.stderr).splitlines() if l.strip(" *")]
    skip = ("Suspicious changes in commit", "See http://wiki.qt.io/Early_Warning_System")
    return [l for l in lines if not l.startswith(skip) and "commit message" not in l.lower()]


def evaluate(task, arm, run, diff_files):
    harness.reset(task, "K0")                 # same base tree as every arm, no arm material
    diff = "".join(Path(f).read_text(errors="ignore") for f in diff_files)
    for f in diff_files:
        harness.sh(["git", "apply", "--whitespace=nowarn", f], cwd=Q)
    added = added_lines(diff)
    res = {"task": task, "arm": arm, "run": run,
           "clazy": run_clazy(translation_units(added), added), "sanitize": run_sanitize()}
    return res


def main():
    tasks = sys.argv[1:] or DESIGN
    for task in tasks:
        jobs = [("MAINTAINER", "oracle", [str(T / task / "src.diff"), str(T / task / "test.diff")])]
        for d in sorted((R / task).glob("*/claude-*")):
            if (d / "agent.diff").exists() and (d / "summary.json").exists() and "excluded" not in str(d):
                jobs.append((d.parent.name, d.name, [str(d / "agent.diff")]))
        for arm, run, files in jobs:
            out = (R / task / ("oracle-tools" if arm == "MAINTAINER" else f"{arm}/{run}"))
            out.mkdir(parents=True, exist_ok=True)
            try:
                res = evaluate(task, arm, run, files)
            except Exception as e:
                res = {"task": task, "arm": arm, "run": run, "error": str(e)[:500]}
            (out / "tools.json").write_text(json.dumps(res, indent=1))
            print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in res.items()}), flush=True)


if __name__ == "__main__":
    main()
