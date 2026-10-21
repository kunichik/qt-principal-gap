#!/usr/bin/env python3
"""Checks agent transcripts for what the harness cannot prevent (the agent is not sandboxed).

For every tool call: does it touch the experiment's own files (tasks, hidden.git, results, arms,
configs, the token)? For every task with hidden tests: does any tool output show a maintainer-only
test function (a sign of running an old build of the hidden test)? Are git stashes left unpopped?
Does the graded agent.diff change anything outside tests/? (A stash pop that never ran, e.g. in a
command the session ended before, leaves the fix out of the diff even when push and pop balance.)

Usage: audit_transcripts.py [transcript.jsonl ... | dir ...]
  default: results/*/*/claude-*/transcript.jsonl
Exit 1 if anything is found.
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import harness

OUTSIDE = re.compile(
    r"(qtexp/(tasks|hidden\.git|results|arms|claude-cfg|cfg-runs|audits|probe|\.oauth|\.kapt)"
    r"|(\.\./)+(tasks|results|arms|hidden\.git|claude-cfg|cfg-runs|audits|probe)\b"
    r"|hidden\.git|oauth-token|CLAUDE_CODE_OAUTH_TOKEN|prompts\.md|K3[bh]?-cards"
    r"|review\.txt|src\.diff|test\.diff)")


def tool_calls(path):
    for line in Path(path).read_text(errors="ignore").splitlines():
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        content = (d.get("message") or {}).get("content")
        if isinstance(content, list):
            for c in content:
                if isinstance(c, dict):
                    yield c


def maintainer_tests():
    out = {}
    for t in harness.TESTS:
        td = harness.T / t / "test.diff"
        if not td.exists():
            continue
        names = set(re.findall(r"^\+\s*void\s+(\w+)\s*\(\s*\)\s*;", td.read_text(), re.M))
        names -= {"init", "cleanup", "initTestCase", "cleanupTestCase"}
        try:
            marker = json.dumps(harness.prompt_for(t))[1:70]
        except KeyError:
            continue
        if names:
            out[t] = (names, marker)
    return out


def audit(path, mt):
    findings = []
    text = Path(path).read_text(errors="ignore")
    task = next((t for t, (_, marker) in mt.items() if marker in text), None)
    inputs, outputs, pushes, pops = [], [], 0, 0
    for c in tool_calls(path):
        if c.get("type") == "tool_use":
            s = json.dumps(c.get("input", {}))
            inputs.append(s)
            m = OUTSIDE.search(s)
            if m:
                findings.append(f"outside access: {m.group(0)} in {c.get('name')} {s[:160]}")
            cmd = c.get("input", {}).get("command", "") if c.get("name") == "Bash" else ""
            pops += len(re.findall(r"\bstash\s+(?:pop|apply)\b", cmd))
            pushes += len(re.findall(r"\bstash\b(?!\s+(?:pop|apply|list|show|drop))", cmd))
        elif c.get("type") == "tool_result":
            outputs.append(json.dumps(c.get("content")))
    if pushes > pops:
        findings.append(f"git stash: {pushes} push vs {pops} pop/apply")
    diff = Path(path).with_name("agent.diff")
    if Path(path).parent.name.startswith("claude-") and diff.exists() \
            and not re.search(r"^\+\+\+ b/(?!tests/)", diff.read_text(errors="ignore"), re.M):
        findings.append("agent.diff changes nothing outside tests/")
    if task:
        written = " ".join(inputs)
        for name in mt[task][0]:
            if name not in written and any(re.search(rf"tst_\w+::{re.escape(name)}\(", o) for o in outputs):
                findings.append(f"maintainer-only test function in output: {name}")
    return findings


def main():
    args = [Path(a) for a in sys.argv[1:]] or [ROOT / "results"]
    files = []
    for a in args:
        files += sorted(a.rglob("transcript.jsonl")) + sorted(a.rglob("*.jsonl")) if a.is_dir() else [a]
    files = sorted(set(files))
    mt = maintainer_tests()
    bad = 0
    for f in files:
        for finding in audit(f, mt):
            bad += 1
            print(f"{f}: {finding}")
    print(f"{len(files)} transcripts, {bad} findings")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
