#!/usr/bin/env python3
"""One run of the principal-gap experiment: reset tree, set up arm, run agent, grade.

Usage: harness.py <task> <arm K0|K0g|K1|K2|K3|K3b|K3h> <rep> [--agent claude|none|oracle] [--model M]
  none   = make no change (harness check: hidden test must fail)
  oracle = apply the maintainer's fix (harness check: hidden test must pass)

The agent is not sandboxed: it has Bash and runs in qtbase/, next to the rest of this directory.
Nothing stops it from reading ../tasks or ../hidden.git; tools/audit_transcripts.py checks every
run's transcript for that (it found no such access in the published runs).
"""
import argparse, contextlib, fcntl, json, os, re, shutil, subprocess, sys, tempfile, time
from pathlib import Path
ROOT = Path(os.environ.get("QTEXP_ROOT", Path(__file__).resolve().parent))  # experiment root
sys.path.insert(0, str(ROOT))
from usermd import user_md_aside, restore_if_crashed

Q = ROOT / "qtbase"          # work tree the agent sees
H = ROOT / "hidden.git"      # full-history repo the harness resets from
B = ROOT / "b3"              # build dir
T = ROOT / "tasks"
A = ROOT / "arms"
R = ROOT / "results"
CFG = ROOT / "claude-cfg"    # template config: only .claude.json and settings.json are copied
CFG_RUNS = ROOT / "cfg-runs" # one fresh Claude Code config per run, removed afterwards
TEST_TIMEOUT_S = 900

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
# later changes built on the task's change, reverted first
PRE = {"768691": ["768692"]}
# K0g: the fix commit of each task; the agent gets the real history up to its parent, nothing after
FIX = {"756614": "9d390a21", "754389": "1e0b9402", "750871": "3bb40a97", "777778": "2dac0b62",
       "773405": "201029bc", "764375": "09e7b23d", "765378": "76f077c9", "768691": "e4d0d0b7",
       "759321": "78b7b6ff"}
SUFFIX = ("\n\nThe code is qtbase (Qt 6, dev branch). A Debug developer build is in {b} "
          "(build with `ninja -C {b} <target>`; autotests are under tests/auto). Find the root "
          "cause and fix it in the library source. You may add or change tests.")


# git must never find the experiment root's own .git from inside qtbase: when qtbase/.git is
# absent, `git apply` would run in that repo and silently skip every path outside qtbase/.
os.environ["GIT_CEILING_DIRECTORIES"] = str(ROOT)


def sh(cmd, cwd=None, check=True, **kw):
    r = subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str), text=True,
                       capture_output=True, stdin=subprocess.DEVNULL, **kw)
    if check and r.returncode:
        raise RuntimeError(f"{cmd}\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    return r


def hidden(*args, check=True):
    return sh(["git", f"--git-dir={H}", f"--work-tree={Q}", *args], cwd=Q, check=check)


@contextlib.contextmanager
def tree_lock():
    """qtbase/ and b3/ are shared: one run (or tool_eval) at a time."""
    with open(ROOT / ".tree.lock", "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        yield


def section(path, task):
    """The `## <task>` section of a notes file; HTML comments (editorial notes) are dropped."""
    text = re.sub(r"<!--.*?-->\n?", "", Path(path).read_text(), flags=re.S)
    m = re.search(rf"^## {task}[^\n]*\n(.*?)(?=^#{{1,2}} |\Z)", text, re.S | re.M)
    if m is None:
        raise KeyError(f"no section '## {task}' in {path}")
    return m.group(1).strip()


def prompt_for(task):
    suffix = FEATURE_SUFFIX if task in FEATURES else SUFFIX
    return section(T / "prompts.md", task) + suffix.format(b=B)


def card_for(task, arm="K3"):
    return section(A / f"{arm}-cards.md", task)


def test_files(task):
    return re.findall(r"^\+\+\+ b/(\S+)", (T / task / "test.diff").read_text(), re.M)


def test_dirs(task):
    return sorted({str(Path(f).parent) for f in test_files(task)})


def purge_test_binaries(task):
    """Built test binaries outlive a run in b3/: a later agent could run the previous grade's
    build of the hidden test, and grading would pick up binaries of targets that no longer exist."""
    for d in test_dirs(task):
        for x in list((B / d).rglob("tst_*")) if (B / d).exists() else []:
            if x.is_dir() and x.suffix == ".app":
                shutil.rmtree(x, ignore_errors=True)
            elif x.is_file() and os.access(x, os.X_OK):
                x.unlink()


def reset(task, arm):
    """Puts qtbase/ in the task's baseline state for the arm; returns the snapshot commit."""
    shutil.rmtree(Q / ".git", ignore_errors=True)
    shutil.rmtree(Q / ".claude", ignore_errors=True)
    (Q / "CLAUDE.md").unlink(missing_ok=True)
    # read-tree --reset -u makes the tree exactly the commit's (also removes files it lacks);
    # clean -x also removes ignored scratch files (tmp/, build/, *.orig, *.rej) of earlier runs
    hidden("read-tree", "--reset", "-u", BASE[task] + "^" if task in BASE else "HEAD")
    hidden("clean", "-ffdxq")
    for later in PRE.get(task, []):
        sh(["git", "apply", "-R", str(T / later / "src.diff"), str(T / later / "test.diff")], cwd=Q)
    if task not in BASE:
        sh(["git", "apply", "-R", str(T / task / "src.diff")], cwd=Q)
        sh(["git", "apply", "-R", str(T / task / "test.diff")], cwd=Q)
        # the fix must be gone: it has to apply forward again
        sh(["git", "apply", "--check", str(T / task / "src.diff")], cwd=Q)
    purge_test_binaries(task)
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
    else:
        # visible repo: one snapshot commit, no history to mine
        sh("git init -q && git add -A && git -c user.name=x -c user.email=x@x "
           "commit -qm snapshot", cwd=Q)
    return sh("git rev-parse HEAD", cwd=Q).stdout.strip()


def fresh_config():
    """A Claude Code config for one run: no transcripts or memory from earlier runs."""
    CFG_RUNS.mkdir(exist_ok=True)
    cfg = Path(tempfile.mkdtemp(prefix="run-", dir=CFG_RUNS))
    for name in (".claude.json", "settings.json"):
        if (CFG / name).exists():
            shutil.copy(CFG / name, cfg / name)
    return cfg


def run_agent(kind, task, model, out):
    if kind == "none":
        return {}
    if kind == "oracle":
        sh(["git", "apply", str(T / task / "src.diff")], cwd=Q)
        return {}
    # Claude Code reads the user's ~/.claude/CLAUDE.md from the account's home directory no
    # matter what HOME or CLAUDE_CONFIG_DIR say, so it is moved aside for the run only.
    token = (ROOT / ".oauth-token").read_text().strip()
    cfg = fresh_config()
    env = dict(os.environ, CLAUDE_CONFIG_DIR=str(cfg), CLAUDE_CODE_OAUTH_TOKEN=token)
    t0 = time.time()
    try:
        with user_md_aside():
            r = sh(["claude", "-p", prompt_for(task), "--model", model, "--output-format", "json",
                    "--allowedTools", "Bash", "Read", "Edit", "Write", "Grep", "Glob", "Skill",
                    "--disallowedTools", "WebSearch", "WebFetch",
                    "--permission-mode", "acceptEdits", "--add-dir", str(B),
                    "--max-budget-usd", "5"],
                   cwd=Q, check=False, env=env)
        # keep the session transcript with the run, for tools/audit_transcripts.py
        with open(out / "transcript.jsonl", "w") as tr:
            for f in sorted((cfg / "projects").rglob("*.jsonl")):
                tr.write(f.read_text(errors="ignore"))
    finally:
        shutil.rmtree(cfg, ignore_errors=True)
    (out / "agent.json").write_text(r.stdout)
    (out / "agent.stderr").write_text(r.stderr)
    try:
        meta = json.loads(r.stdout)
    except json.JSONDecodeError:
        meta = {"parse_error": True}
    meta["wall_s"] = round(time.time() - t0)
    return meta


def run_test(binp, cwd):
    try:
        t = sh([str(binp)], cwd=cwd, check=False, timeout=TEST_TIMEOUT_S)  # QFINDTESTDATA helpers
    except subprocess.TimeoutExpired:
        return {"build": "OK", "hung": True, "timeout_s": TEST_TIMEOUT_S}
    tot = re.search(r"Totals: (\d+) passed, (\d+) failed, (\d+) skipped, (\d+) blacklisted",
                    t.stdout)
    if tot is None and t.returncode == 0:
        return None  # helper binary, not a QTest suite
    fails = re.findall(r"^FAIL!\s+: (\S+)", t.stdout, re.M)
    n = (lambda i: int(tot[i]) if tot else None)
    return {"build": "OK", "passed": n(1), "failed": n(2), "skipped": n(3), "blacklisted": n(4),
            "fail_names": fails, "crashed": tot is None}


def grade(task, out, snapshot):
    sh("git add -A -N", cwd=Q)
    # against the snapshot, not HEAD: an agent that committed its fix still has it recorded
    (out / "agent.diff").write_text(sh(["git", "diff", snapshot], cwd=Q).stdout)
    stash = sh("git stash list", cwd=Q).stdout.strip()
    flags = {"stash_left": bool(stash), "committed": sh("git rev-parse HEAD", cwd=Q).stdout.strip() != snapshot}
    # the maintainer's test directories replace whatever the agent did there (extra files,
    # BLACKLIST, CMakeLists.txt, test data), then only the maintainer's targets are built
    for d in test_dirs(task):
        shutil.rmtree(Q / d, ignore_errors=True)
        hidden("checkout", BASE.get(task, "HEAD"), "--", d)
    for later in PRE.get(task, []):  # keep the later change's tests out of grading
        sh(["git", "apply", "-R", str(T / later / "test.diff")], cwd=Q, check=False)
    purge_test_binaries(task)
    res = {}
    for d in test_dirs(task):
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
            r = run_test(binp, B / d)
            if r is not None:
                res[binp.name] = r
    return res, flags


def main():
    p = argparse.ArgumentParser()
    p.add_argument("task"); p.add_argument("arm"); p.add_argument("rep")
    p.add_argument("--agent", default="claude"); p.add_argument("--model", default="opus")
    a = p.parse_args()
    restore_if_crashed()
    out = R / a.task / a.arm / f"{a.agent}-{a.rep}"
    out.mkdir(parents=True, exist_ok=True)
    with tree_lock():
        snapshot = reset(a.task, a.arm)
        meta = run_agent(a.agent, a.task, a.model, out)
        if meta.get("terminal_reason") == "api_error" or meta.get("api_error_status"):
            # usage/session limit or API failure: not a result; move it aside and stop the batch
            shutil.move(str(out), str(out.parent / f"excluded-apierror-{out.name}-{int(time.time())}"))
            print(json.dumps({"task": a.task, "arm": a.arm, "rep": a.rep, "invalid": True,
                              "reason": str(meta.get("result"))[:200]}))
            sys.exit(3)
        if meta.get("parse_error"):
            # the agent process produced no result (crash): not a graded run; the batch goes on
            shutil.move(str(out), str(out.parent / f"excluded-crash-{out.name}-{int(time.time())}"))
            print(json.dumps({"task": a.task, "arm": a.arm, "rep": a.rep, "invalid": True,
                              "reason": "agent produced no JSON result"}))
            sys.exit(4)
        res, flags = grade(a.task, out, snapshot)
    summary = {"task": a.task, "arm": a.arm, "rep": a.rep, "agent": a.agent, "model": a.model,
               "tests": res, "flags": flags, "cost_usd": meta.get("total_cost_usd"),
               "turns": meta.get("num_turns"), "wall_s": meta.get("wall_s"),
               "agent_subtype": meta.get("subtype")}  # e.g. a budget limit is graded, not dropped
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
