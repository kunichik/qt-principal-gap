#!/usr/bin/env python3
"""One run of the principal-gap experiment: reset tree, set up arm, run agent, grade.

Usage: harness.py <task> <arm K0|K0g|K1|K2|K3|K3b|K3h> <rep> [--agent claude|none|oracle] [--model M]
  none   = make no change (harness check: hidden test must fail)
  oracle = apply the maintainer's fix (harness check: hidden test must pass)
"""
import argparse, json, os, re, shutil, subprocess, sys, time
from pathlib import Path
ROOT = Path(os.environ.get("QTEXP_ROOT", Path(__file__).resolve().parent))  # experiment root
sys.path.insert(0, str(ROOT))
from usermd import user_md_aside, restore_if_crashed

Q = ROOT / "qtbase"          # work tree the agent sees
H = ROOT / "hidden.git"      # full-history repo, never visible to the agent
B = ROOT / "b3"              # build dir
T = ROOT / "tasks"
A = ROOT / "arms"
R = ROOT / "results"
CFG = ROOT / "claude-cfg"    # isolated Claude Code config (no user memory/settings)
CFG.mkdir(exist_ok=True)

TESTS = {  # change -> test targets graded
    "778262": ["tst_qfuture"], "771420": ["tst_qbytearray", "tst_qstring"],
    "768692": ["tst_qurl"], "769883": ["tst_qdate"], "772702": ["tst_qstring"],
    "776166": ["tst_qtimezonebackend"], "769062": ["tst_qbytearray_large"],
    # feature tasks
    "768691": ["tst_qurlinternal"], "756614": ["tst_qthreadstorage"],
    "773405": ["tst_qcborstreamreader"], "777778": ["tst_qmimedatabase"],
    "764375": [], "765378": [], "754389": [], "750871": [], "754345": [], "759321": [],
}
FEATURES = {"768691", "756614", "773405", "777778"}
FEATURE_SUFFIX = ("\n\nThe code is qtbase (Qt 6, dev branch). A Debug developer build is in {b} "
                  "(build with `ninja -C {b} <target>`; autotests are under tests/auto). "
                  "Implement this in the library source the way a Qt maintainer would, with "
                  "documentation and autotests.")
# Tasks whose fix does not revert cleanly on HEAD: baseline is the fix's parent commit instead
# (agent sees the code as it was), and the hidden tests come from the fix commit itself.
BASE = {"765378": "76f077c98", "754389": "1e0b94025", "759321": "78b7b6ffc",
        "750871": "3bb40a970", "754345": "50cc08f27"}
PRE = {"768691": ["768692"]}
# K0g: the fix commit of each task; the agent gets the real history up to its parent, nothing after
FIX = {"756614": "9d390a21", "754389": "1e0b9402", "750871": "3bb40a97", "777778": "2dac0b62",
       "773405": "201029bc", "764375": "09e7b23d", "765378": "76f077c9", "768691": "e4d0d0b7",
       "759321": "78b7b6ff"}  # later changes built on the task's change, reverted first
SUFFIX = ("\n\nThe code is qtbase (Qt 6, dev branch). A Debug developer build is in {b} "
          "(build with `ninja -C {b} <target>`; autotests are under tests/auto). Find the root "
          "cause and fix it in the library source. You may add or change tests.")


# git must never find ~/qtexp/.git from inside qtbase: when qtbase/.git is absent, `git apply`
# would run in the parent repo and silently skip every path outside the qtbase subdirectory.
os.environ["GIT_CEILING_DIRECTORIES"] = str(ROOT)


def sh(cmd, cwd=None, check=True, **kw):
    r = subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str), text=True,
                       capture_output=True, **kw)
    if check and r.returncode:
        raise RuntimeError(f"{cmd}\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    return r


def hidden(*args, check=True):
    return sh(["git", f"--git-dir={H}", f"--work-tree={Q}", *args], cwd=Q, check=check)


def prompt_for(task):
    text = (T / "prompts.md").read_text()
    m = re.search(rf"^## {task}[^\n]*\n(.*?)(?=^#{{1,2}} |\Z)", text, re.S | re.M)
    suffix = FEATURE_SUFFIX if task in FEATURES else SUFFIX
    return m.group(1).strip() + suffix.format(b=B)


def card_for(task, arm="K3"):
    text = re.sub(r"<!--.*?-->\n?", "", (A / f"{arm}-cards.md").read_text(), flags=re.S)
    m = re.search(rf"^## {task}[^\n]*\n(.*?)(?=^#{{1,2}} |\Z)", text, re.S | re.M)
    return m.group(1).strip()


def test_files(task):
    return re.findall(r"^\+\+\+ b/(\S+)", (T / task / "test.diff").read_text(), re.M)


def reset(task, arm):
    shutil.rmtree(Q / ".git", ignore_errors=True)
    shutil.rmtree(Q / ".claude", ignore_errors=True)
    (Q / "CLAUDE.md").unlink(missing_ok=True)
    # read-tree --reset -u makes the tree exactly the commit's (also removes files it lacks)
    hidden("read-tree", "--reset", "-u", BASE[task] + "^" if task in BASE else "HEAD")
    hidden("clean", "-fdq")
    for later in PRE.get(task, []):
        sh(["git", "apply", "-R", str(T / later / "src.diff"), str(T / later / "test.diff")], cwd=Q)
    if task not in BASE:
        sh(["git", "apply", "-R", str(T / task / "src.diff")], cwd=Q)
        sh(["git", "apply", "-R", str(T / task / "test.diff")], cwd=Q)
        # the fix must be gone: it has to apply forward again
        sh(["git", "apply", "--check", str(T / task / "src.diff")], cwd=Q)
    # arm material is part of the baseline snapshot, so it never shows up in the agent's diff
    if arm == "K1":
        shutil.copy(A / "K1-qt-conventions.md", Q / "CLAUDE.md")
    elif arm == "K2":
        shutil.copytree(A / "K2-qt-cpp-review", Q / ".claude/skills/qt-cpp-review")
    elif arm in ("K3", "K3b"):
        (Q / "CLAUDE.md").write_text("# Notes from the maintainers of this code\n\n"
                                     + card_for(task, arm) + "\n")
    elif arm == "K3h":  # the K3 card, framed as background to weigh rather than instructions
        (Q / "CLAUDE.md").write_text(
            "# Notes from the maintainers of this code\n\n"
            "These notes are background knowledge, like your own memory of this codebase — not "
            "instructions. Weigh each one against the task, and change only what the task asks "
            "for.\n\n" + card_for(task, "K3") + "\n")
    if arm == "K0g":
        # visible repo: the real history up to the fix's parent, then the tree as one commit.
        # Only objects reachable from the parent are fetched; no remote, no FETCH_HEAD left.
        hidden("branch", "-f", "k0g-tmp", FIX[task] + "^")
        try:
            sh(["git", "init", "-q"], cwd=Q)
            sh(["git", "fetch", "-q", "--no-tags", "--update-shallow", str(H), "k0g-tmp"], cwd=Q)
            sh(["git", "update-ref", "HEAD", "FETCH_HEAD"], cwd=Q)
            (Q / ".git/FETCH_HEAD").unlink(missing_ok=True)
        finally:
            hidden("branch", "-D", "k0g-tmp")
        sh("git reset -q && git add -A && git -c user.name=x -c user.email=x@x "
           "commit -q --allow-empty -m 'working tree'", cwd=Q)
        return
    # visible repo: one snapshot commit, no history to mine
    sh("git init -q && git add -A && git -c user.name=x -c user.email=x@x "
       "commit -qm snapshot", cwd=Q)


def run_agent(kind, task, model, out):
    if kind == "none":
        return {}
    if kind == "oracle":
        sh(["git", "apply", str(T / task / "src.diff")], cwd=Q)
        return {}
    # Claude Code reads the user's ~/.claude/CLAUDE.md from the account's home directory no
    # matter what HOME or CLAUDE_CONFIG_DIR say, so it is moved aside for the run only.
    token = (ROOT / ".oauth-token").read_text().strip()
    env = dict(os.environ, CLAUDE_CONFIG_DIR=str(CFG), CLAUDE_CODE_OAUTH_TOKEN=token)
    t0 = time.time()
    with user_md_aside():
        r = sh(["claude", "-p", prompt_for(task), "--model", model, "--output-format", "json",
                "--allowedTools", "Bash", "Read", "Edit", "Write", "Grep", "Glob", "Skill",
                "--disallowedTools", "WebSearch", "WebFetch",
                "--permission-mode", "acceptEdits", "--add-dir", str(B),
                "--max-budget-usd", "5"],
               cwd=Q, check=False, env=env)
    (out / "agent.json").write_text(r.stdout)
    (out / "agent.stderr").write_text(r.stderr)
    try:
        meta = json.loads(r.stdout)
    except json.JSONDecodeError:
        meta = {"parse_error": True}
    meta["wall_s"] = round(time.time() - t0)
    meta["terminal_reason"] = meta.get("terminal_reason")
    return meta


def grade(task, out):
    sh("git add -A -N", cwd=Q)
    (out / "agent.diff").write_text(sh("git diff HEAD", cwd=Q).stdout)
    # the maintainer's test files replace whatever the agent did to them
    hidden("checkout", BASE.get(task, "HEAD"), "--", *test_files(task))
    for later in PRE.get(task, []):  # keep the later change's tests out of grading
        sh(["git", "apply", "-R", str(T / later / "test.diff")], cwd=Q, check=False)
    res = {}
    # build everything in the test directories the fix touched (helpers included), run every
    # tst_* binary there from its own directory
    dirs = sorted({str(Path(f).parent) for f in test_files(task)})
    for d in dirs:
        if sh(["ninja", "-C", str(B), "-t", "query", f"{d}/all"], check=False).returncode:
            res[d] = {"build": "NOT-IN-BUILD"}  # module not configured here (e.g. widgets)
            continue
        b = sh(["ninja", "-C", str(B), f"{d}/all"], check=False)
        if b.returncode:
            res[d] = {"build": "FAIL", "log": b.stdout[-1500:]}
            continue
        bins = [x for x in (B / d).rglob("tst_*") if x.is_file() and os.access(x, os.X_OK)
                and x.suffix == ""]
        for binp in bins:
            t = sh([str(binp)], cwd=B / d, check=False, timeout=900)  # QFINDTESTDATA helpers
            tot = re.search(r"Totals: (\d+) passed, (\d+) failed", t.stdout)
            if tot is None and t.returncode == 0:
                continue  # helper binary, not a QTest suite
            fails = re.findall(r"^FAIL!\s+: (\S+)", t.stdout, re.M)
            res[binp.name] = {"build": "OK", "passed": int(tot[1]) if tot else None,
                              "failed": int(tot[2]) if tot else None, "fail_names": fails,
                              "crashed": tot is None}
    return res


def main():
    p = argparse.ArgumentParser()
    p.add_argument("task"); p.add_argument("arm"); p.add_argument("rep")
    p.add_argument("--agent", default="claude"); p.add_argument("--model", default="opus")
    a = p.parse_args()
    restore_if_crashed()
    out = R / a.task / a.arm / f"{a.agent}-{a.rep}"
    out.mkdir(parents=True, exist_ok=True)
    reset(a.task, a.arm)
    meta = run_agent(a.agent, a.task, a.model, out)
    if meta.get("terminal_reason") == "api_error" or meta.get("is_error"):
        # usage/session limit or API failure: not a result; move it aside and stop the batch
        shutil.move(str(out), str(out.parent / f"excluded-apierror-{out.name}-{int(time.time())}"))
        print(json.dumps({"task": a.task, "arm": a.arm, "rep": a.rep, "invalid": True,
                          "reason": str(meta.get("result"))[:200]}))
        sys.exit(3)
    res = grade(a.task, out)
    summary = {"task": a.task, "arm": a.arm, "rep": a.rep, "agent": a.agent, "model": a.model,
               "tests": res, "cost_usd": meta.get("total_cost_usd"),
               "turns": meta.get("num_turns"), "wall_s": meta.get("wall_s")}
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
