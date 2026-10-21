# The principal gap: AI coding agents on real qtbase changes

What separates an AI coding agent's change from the change a Qt maintainer merged — and how much of
that closes when the agent is given what the maintainers knew? This repository holds the harness,
the tasks, every run and every grade behind the talk *"What Qt Looks Like to an AI"* (Qt Contributors
Summit 2026, Oslo).

Results and their caveats: [`RESULTS.md`](RESULTS.md). What is specific to Qt:
[`QT-SPECIFIC-FINDINGS.md`](QT-SPECIFIC-FINDINGS.md).

## The experiment in one paragraph

Real qtbase changes merged after the model's training cutoff (by date). For each, the tree is put back
to the state before the change, history is hidden, and the agent (Claude Code, headless) gets only the
task. Each run is graded two ways: the autotest the author added with the change (hidden from the
agent, restored for grading), and a blind LLM judge that compares the agent's diff with the merged
one and reads the review comments (calibrated against manual verdicts, 12/12 on one task). The agent
gets different amounts of knowledge — the *arms*:

| Arm | What the agent gets |
|---|---|
| K0 | the task only |
| K0g | the task + the real `git log` up to the change's parent |
| K1 | + Qt's coding conventions from the wiki (`tools/fetch-k1.sh`) |
| K2 | + the official Qt agent skill for C++ review (`arms/K2-qt-cpp-review`, qtaiskills `92b48ae`) |
| K3 | + a short card of facts from the review and commit message (`arms/K3-cards.md`) |
| K3b | + corrected cards, checked against the merged code (`arms/K3b-cards.md`) |
| K3h | the K3 card framed as "background, not instructions" |

`tool_eval.py` also runs Qt's own checks — clazy (level1) and `sanitize-commit`, the script Qt Sanity
Bot runs — on every patch.

## Layout

```
harness.py      one run: reset tree, set up arm, run agent, grade with the hidden tests
judge.py        blind judge for one run (writes judge.json)
auditor.py      card auditors (one model / majority / mixed / with merged source)
kapt_auditor.py card audit through a multi-vendor "collegium" pipeline on kapt.ai (needs a key)
tool_eval.py    clazy + sanitize-commit on the maintainer's and every agent patch
batch.sh        run "task arm rep" lines sequentially; stops on a usage-limit/API error
usermd.py       moves ~/.claude/CLAUDE.md aside during a run (see below)
cxx             compiler wrapper for macOS with only the Command Line Tools
clazy-run.sh    clazy with the build's flags (precompiled headers stripped)
tools/          sanitize-commit (from qtrepotools), fetch-k1.sh
tasks/<id>/     prompt in tasks/prompts.md; src.diff / test.diff (the merged change), commit.txt,
                review.txt (Gerrit comments, reviewer names replaced by aliases)
arms/           arm material (K1 is fetched, not stored)
results/<id>/<arm>/claude-N/   agent.diff, agent.json, summary.json (tests), judge.json, tools.json
audits/<id>/    card audits
```

## Reproducing

You need: a qtbase checkout with history to `6c198cd0d78461413280fa9c9cd6cfa01e604a68` (2026-10-12),
Claude Code (`claude` on PATH) and Python 3, CMake, Ninja.

1. **Source.** Put a bare/shallow clone of qtbase at `hidden.git` (the agent never sees it) and a work
   tree at `qtbase/`. The harness resets `qtbase/` from `hidden.git` before every run.
2. **Build.** A Debug developer build in `b3/` with Core, Test, Concurrent and Network:
   ```
   cmake -S qtbase -B b3 -G Ninja -DCMAKE_BUILD_TYPE=Debug -DFEATURE_developer_build=ON \
         -DQT_BUILD_TESTS=ON -DFEATURE_gui=OFF -DFEATURE_widgets=OFF -DFEATURE_dbus=OFF
   ninja -C b3
   ```
   On macOS with only the Command Line Tools add `-DCMAKE_CXX_COMPILER=$PWD/cxx
   -DQT_NO_APPLE_SDK_AND_XCODE_CHECK=ON`. Autotests must run from the build dir (QFINDTESTDATA).
3. **Agent auth.** `claude setup-token`, then save the token in `.oauth-token` (never commit it). The
   harness runs Claude Code with an isolated config in `claude-cfg/`.
4. **Your own CLAUDE.md.** Claude Code reads `~/.claude/CLAUDE.md` whatever `CLAUDE_CONFIG_DIR` says,
   so `usermd.py` moves it aside for each run (with a lock) and puts it back afterwards.
5. **K1.** `tools/fetch-k1.sh` rebuilds the wiki material; it prints a checksum to compare with the one
   the experiment used.
6. **Run.** `python3 harness.py 756614 K0 1`, then `python3 judge.py results/756614/K0/claude-1`.
   Batches: `sh batch.sh < batch3.txt`.

All paths are relative to this directory; set `QTEXP_ROOT` to use another one.

## Limits

Three runs per arm and task; one model through one agent tool; an LLM judge (calibrated on one task);
cards written with an AI and audited against merged code; the "decisive point" per change classified
by the author. Treat the numbers as directions, not proofs.

## Licence

Code: MIT ([`LICENSE`](LICENSE)). Material from Qt and its tools keeps its own licence — see
[`NOTICE.md`](NOTICE.md).
