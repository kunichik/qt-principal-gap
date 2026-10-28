# The principal gap: AI coding agents on real qtbase changes

What separates an AI coding agent's change from the change a Qt maintainer merged — and how much of
that closes when the agent is given what the maintainers knew? This repository holds the harness,
the tasks, every run and every grade behind the talk *"What Qt Looks Like to an AI"* (Qt Contributors
Summit 2026, Oslo).

Results and their caveats: [`RESULTS.md`](RESULTS.md). What is specific to Qt:
[`QT-SPECIFIC-FINDINGS.md`](QT-SPECIFIC-FINDINGS.md).

## The experiment in one paragraph

Real qtbase changes merged after the model's training cutoff (by merge date; the Gerrit reviews may
have been public earlier, and the no-tools recognition probe was run only for the two bug tasks). For
each, the fix is removed from the tree — for 756614, 768691, 773405, 777778 and 764375 by reverse-applying
it to the 2026-10-12 `HEAD`, so later unrelated commits stay; for the others by resetting to the
fix's parent — history is hidden (except arm K0g), and the agent (Claude Code, headless) gets the
task. Two prompt leaks are disclosed in `RESULTS.md`. Each run is graded two ways: the autotest the author added with the change (hidden from the
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
tools/          sanitize-commit (from qtrepotools), fetch-k1.sh, make-clazydb.py, audit_transcripts.py,
                rejudge.sh (judge test-retest), probe_recognition.py (contamination probe),
                make_calibration_packet.py + compare_calibration.py (blind human calibration)
probe-results/  contamination probe answers (tasks, pre-cutoff controls, API probe)
tasks/<id>/     prompt in tasks/prompts.md; src.diff / test.diff (the merged change), commit.txt,
                review.txt (Gerrit comments, reviewer names replaced by aliases)
arms/           arm material (K1 is fetched, not stored)
results/<id>/<arm>/claude-N/   agent.diff, agent.json, summary.json (tests), judge.json, judge-retest.json, tools.json
audits/<id>/    card audits
```

## Reproducing

You need: a qtbase checkout with history to `6c198cd0d78461413280fa9c9cd6cfa01e604a68` (2026-10-12),
Claude Code (`claude` on PATH) and Python 3, CMake, Ninja.

1. **Source.** Put a clone of qtbase at `hidden.git` with `HEAD` at
   `6c198cd0d78461413280fa9c9cd6cfa01e604a68` — tasks without a fixed baseline reset from `HEAD`,
   so another `HEAD` silently changes them. It needs history, not `--depth 1`: the baselines of
   some tasks are parents of older commits, and arm K0g fetches the history before each change
   (ours was a shallow clone of 2,305 commits, reaching back past 2025-02). Make a work tree at
   `qtbase/`; the harness resets it from `hidden.git` before every run.
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
6. **clazy (only for `tool_eval.py`).** Install clazy (e.g. `brew install clazy`), configure the build
   with `-DCMAKE_EXPORT_COMPILE_COMMANDS=ON`, then `tools/make-clazydb.py` writes
   `clazydb/compile_commands.json` without precompiled-header flags.
7. **Run.** `python3 harness.py 756614 K0 1`, then `python3 judge.py results/756614/K0/claude-1`.
   Batches: `sh batch.sh < batch3.txt`.

All paths are relative to this directory. The Python scripts also accept `QTEXP_ROOT`; the shell
scripts and `tools/*` always use the directory they are in.

## What the harness does not prevent

The agent is not sandboxed. It has Bash and runs in `qtbase/`, one `..` away from `tasks/`,
`hidden.git/` and earlier `results/`. Nothing but the directory layout keeps it from reading them.
`tools/audit_transcripts.py` checks each run's transcript for any access outside `qtbase/` and
`b3/`, for test output from a hidden test the agent did not write, for unpopped git stashes, and for
a graded diff that changes nothing outside `tests/`. The last check was added after an independent
review found one run whose fix was stashed when the session ended (754389 K0g rep 2, now excluded);
with it the script flags that run and reports 0 findings over the other published transcripts.
It does not detect what is in the prompt itself — see the two disclosures at the end of `RESULTS.md`. For new experiments, a container or sandbox that mounts only `qtbase/` and `b3/`
is the stronger fix.

## Harness versions

The published runs were made 2026-10-13 … 2026-10-20 with an earlier version of `harness.py`. The
current version also: gives every run a fresh Claude Code config and keeps its transcript in the
run directory; strips HTML comments from the task prompt (the earlier version passed an editorial
note into every **777778** prompt — see `RESULTS.md`); gives the agent no stdin (the earlier `batch.sh` let `claude -p` read
the rest of the batch list into 92 of 101 agent prompts — see `RESULTS.md`); records the diff against the baseline
snapshot rather than `HEAD`; removes stale test binaries from `b3/` before the agent and before
grading; restores whole hidden-test directories; records hung tests, skipped and blacklisted
counts; cleans ignored files between runs; grades runs that hit the budget limit instead of
dropping them. The audit above checks the earlier runs for the problems these changes prevent.

## Limits

Three runs per arm and task; one model through one agent tool; an LLM judge of the same model family
as the agent, one judgement per run, calibrated on one task against the author's verdicts and blind-checked by one independent
Qt developer (20+ years of Qt) on another (rank correlation 0.72, see RESULTS "Human calibration"); the judge
reads the same reviews the K3/K3b cards were written from, so K3b scores are an upper bound; cards
written with an AI and audited against merged code; the "decisive point" per change classified by the
author. Every published agent turn is `claude-opus-5-5` under Claude Code 2.1.296 (from the
transcripts); the scripts pass the alias `opus`, so a rerun may get a newer model. Treat the numbers
as directions, not proofs.

## Acknowledgements

- The qtbase authors and reviewers whose changes, commit messages and review comments this experiment
  is built on (reviewer names anonymised, see `REVIEWERS-ANONYMISED.txt`).
- An independent Qt developer with 20+ years of Qt experience, who scored the blind calibration packet
  on 759321, and also ran it through the Hermes agent with Qwen3.8-27B as a second, independent model
  (see RESULTS "Human calibration").
- Volker Hilsheimer, for the invitation to present this at Qt Contributors Summit 2026.
- Tools used to build the experiment and the talk: Claude Code (Claude Opus and Sonnet), Cursor,
  Slidev. The card-debate auditor ran on kapt.ai (Claude Sonnet 5.5, GPT-6.1 Sol Pro, Gemini 4 Argon;
  chair Claude Opus 5.5) — the author's own product, see the conflict-of-interest note in RESULTS.

## Licence

Code: MIT ([`LICENSE`](LICENSE)). `clazy-run.sh` and `cxx` are written for macOS with the Command
Line Tools; on Linux, call `clazy-standalone -p clazydb` directly. Material from Qt and its tools keeps its own licence — see
[`NOTICE.md`](NOTICE.md).
