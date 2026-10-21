# Principal-gap experiment — results

## Summary

Model: Opus 5.5 via Claude Code, headless and isolated. 9 design tasks are the core; the rest are bug
tasks with the diagnosis in the prompt. Scores are the blind judge's "design match" (0–1) to the merged
change; "tests" are the maintainers' own autotests, hidden from the agent.

- **Well-described bugs:** the agent writes the maintainer's fix (e.g. `QString::insert` character for
  character).
- **Knowledge closes some gaps cheaply:** `QThreadStorage::clearLocalData()` — the key design decision
  appears in 1 of 3 runs with no help, with the Qt conventions page, or with the official review skill;
  3 of 3 with one sentence from the commit message. Tests pass in all 12 runs.
- **A true fact without its scope changes what the agent does:** QtConcurrent — 0.99 with no card,
  0.32 with "map()/filter() is affected too" (all 3 runs extend the fix; extending it is logical, the
  merged change fixed `run()` and kept the task open), 1.00 with the team's decision written down.
  Telling the agent the notes are "background, not instructions" gives 0.52 and still 3/3 extensions.
- **Cards written with an AI were wrong in 4 of 10 tasks**; corrected cards close gaps (QLockFile
  0.38 → 0.91, deadlock at exit 0.63 → 0.85, QUrl tests pass for the first time).
- **Checking the cards:** five auditor setups all flagged the bad cards; only the one given the merged
  code named every error.
- **Tests saw the difference** between agent and maintainer in 3 of 36 runs of the design tasks.
- **`git log` up to the change** (K0g): no average effect (Δ −0.02 over 9 tasks).
- **clazy + sanitize-commit** on all 108 patches (9 maintainers', 99 agents'): zero findings on either
  side (positive control passes).

Caveats: 3 runs per cell, one model, an LLM judge calibrated on one task. The log below is kept as
written, including corrections of earlier readings (search "Correction").

---

# Results log

Model: Opus 5.5 via Claude Code headless, isolated (no user CLAUDE.md/memory). Raw artifacts:
`results/<task>/<arm>/claude-<rep>/` (agent.diff, agent.json, summary.json).

## Bug tasks (maintainer-written diagnosis in the prompt)

| Task | Arm | Hidden test | Cost | Time | vs maintainer |
|---|---|---|---|---|---|
| 772702 QString::insert | K0 | pass | $0.22 | 70 s | identical one-line fix |
| 768692 QUrl::toLocalFile | K0 | pass | $0.73 | 138 s | same structure (found the existing decode mode); extra caller fix in QFileSelector; `bool *ok` instead of maintainer's null+hasPath check |

Contamination check: both fixes and the decode mode were created Sept 2026 (model cutoff June
2026); the model, asked without tools, said it knows none of the three changes.

## Feature tasks

### 756614 QThreadStorage::clearLocalData()

Maintainer's key decision (from the commit message and docs): clearing must not create thread
data when the thread has none — "the only function unconditionally safe to call during
shutdown" — implemented as a new `QThreadStorageData::clear()` guarded by
`QThreadData::currentThreadData()`; QCollator drops its private `qthread_p.h` dependency.

| Arm | Hidden test | Cost | Time | Key decision matched? |
|---|---|---|---|---|
| K0 bare | pass 17/0 | $0.60 | 128 s | **No** — `d.set(nullptr)`; guard kept only in QCollator |
| K1 Qt conventions (wiki) | pass 17/0 | $0.99 | 178 s | **No** — same as K0 |
| K2 official `qt-cpp-review` skill | pass 17/0 | $0.53 | 89 s | **No** — same as K0 |
| K3 reviewer facts | pass 17/0 | $0.54 | 136 s | **Yes** — new `QThreadStorageData::clear()` with the guard, qthread_p.h removed from QCollator |

Reading: the hidden test passes in every arm — it cannot see the gap. General conventions and
the official skill do not close it; one task-specific fact does. Single repeat so far.

### 777778 QMimeDatabase::reload()

| Arm | Hidden test | Cost | Time | vs maintainer |
|---|---|---|---|---|
| K0 | pass (73/0, 57/0) | $0.75 | 131 s | Same design: static `reload()`, invalidate the last-check timestamp under the mutex, drop the developer-build export, port the two tests. Differences: keeps `int` seconds where the maintainer moved to `std::chrono` `5s`; adds an `exists()` guard so `reload()` does not create the shared instance. No meaningful gap. |

### 773405 QCborStreamReader::isNumber()/toNumber()

| Arm | Hidden test | Cost | Time | vs maintainer |
|---|---|---|---|---|
| K0 | pass (3646/0) | $0.57 | 130 s | Functionally equivalent. Style gap: agent adds an exported out-of-line function with a `switch`, a special case for the largest negative integer and a NaN fallback; maintainer writes it inline in the header, reusing the private `_toFloatingPoint<T>()` helper, and avoids the special case by computing `-val - 1` in double. Smaller API/ABI footprint and less code on the maintainer side. |

### 768691 QUrlDecodeForLocalFile

- K0 rep 1 **excluded — spec defect**: the prompt said the value "combines with
  QUrl::FullyDecoded"; the agent defined the bare flag (caller ORs `FullyDecoded` in), the
  maintainer's constant already includes it. Both readings are legitimate; the maintainer's
  test only accepts the second → 9 failures caused by my spec, not by the agent. Spec
  clarified 2026-10-13 and logged in `prompts.md`; rerun pending. Agent independently picked
  the same free bit (0x8000000) as the maintainer.
- K0 rep 1 (rerun, clarified spec): $0.88, 242 s, **6 of 33 rows fail**, all at the same
  assertion: on rejection, an empty-but-non-null output must become a *null* QString. Rejection
  itself (negative return, output left unchanged) is correct in every row. The null contract is
  not in the spec: it exists because the maintainer's *next* commit (`toLocalFile()` returns a
  null QString to signal failure) relies on it. Classified as **unstated contract** — the
  principal knows where the code goes next — and reported separately from plain failures.

## Repeats (2026-10-13) — 20 more runs, all graded

### 756614 QThreadStorage::clearLocalData() — key decision across 3 repeats per arm

"Matched" = new code does not create thread data when there is none (guard on
`QThreadData::currentThreadData()` inside the new function) and QCollator drops its private
`qthread_p.h` include. Checked by script, then the three matches outside K3 read by hand.

| Arm | Matched | Hidden test |
|---|---|---|
| K0 bare | 1 / 3 | pass 3/3 |
| K1 Qt conventions | 1 / 3 | pass 3/3 |
| K2 official skill | 1 / 3 | pass 3/3 |
| K3 reviewer facts | **3 / 3** | pass 3/3 |

Without the card the maintainer's design appears about one time in three — the model *can*
find it, but does not reliably. With one reviewer fact it appears every time. General
conventions and the official skill do not move the rate. Tests pass in all 12 runs.

### 768691 QUrlDecodeForLocalFile

K0 ×3, K1, K2, K3: all **6 failures, identical** — the unstated null-on-rejection contract
(needed by the maintainer's next commit) is missed in every run, in every arm. The K3 card
does not mention it, so K3 is not expected to fix it. Stable, not noise.

### 773405 QCborStreamReader::toNumber() — inline in header like the maintainer?

K0: 1/3, K1: 0/1, K2: 1/1, K3: 1/1. Hidden test passes in all 6. Too few runs to read a trend.

### 777778 QMimeDatabase::reload()

K0 ×3: same design as the maintainer every time; tests pass.

Spend so far: 29 runs, ≈ $21.

## Blind judge (MAPE-style) — calibration on 756614 (2026-10-13)

`judge.py`: Opus, no tools, never told the arm; sees task, maintainer diff, reviewer
comments, candidate source diff; scores 0–1. ~$0.08 per judgement.

| Run | design_match | reviewer_concerns | minimality | hidden_risk | Manual verdict |
|---|---|---|---|---|---|
| K0-1 | 0.55 | 0.80 | 0.85 | 0.50 | no match |
| K0-2 | 0.55 | 0.80 | 0.85 | 0.45 | no match |
| K0-3 | 0.90 | 0.90 | 0.90 | 0.90 | match |
| K1-1 | 0.55 | 0.70 | 0.85 | 0.45 | no match |
| K1-2 | 0.90 | 0.85 | 0.85 | 0.90 | match |
| K1-3 | 0.60 | 0.85 | 0.85 | 0.50 | no match |
| K2-1 | 0.60 | 0.80 | 0.85 | 0.50 | no match |
| K2-2 | 0.85 | 0.85 | 0.85 | 0.90 | match |
| K2-3 | 0.55 | 0.80 | 0.85 | 0.50 | no match |
| K3-1 | 0.85 | 0.90 | 0.85 | 0.90 | match |
| K3-2 | 0.70 | 0.90 | 0.70 | 0.85 | match |
| K3-3 | 0.85 | 0.85 | 0.85 | 0.90 | match |

The judge separates all 12 the same way as the manual check (hidden_risk ≥ 0.85 for every
match, ≤ 0.50 for every non-match), blind to the arm. Usable for the remaining tasks.

754345 (QXmlStreamReader) needs QtGui for its tests (`qxmlstream` is built only with Gui,
Network and Xml) — parked unless Gui is added to the build.

## Second batch — grading validation (2026-10-13)

Baseline = parent of the maintainer's commit (except 764375, reverted on HEAD). Tests run from
their build directory (QFINDTESTDATA helpers; fixed in the harness after 765378 showed 9
false failures from a missing helper).

| Change | Without fix | With fix | Graded by |
|---|---|---|---|
| 764375 QtConcurrent / QThreadPool::clear | 1 failed | 0 failed | test + judge |
| 765378 deadlock at exit | deadlock test fails | 76 / 0 | test + judge |
| 750871 connect() type registration | 4 failed | 0 failed | test + judge |
| 754389 sender vptr race | 0 failed | 0 failed | **judge only** (race visible only under TSan) |
| 759321 QLockFile EBUSY on NFS | 0 failed | 0 failed | **judge only** (needs NFS) |
| 754345 QXmlStreamReader recursion | — | — | parked: tests need QtGui |

## Second batch — K0 vs K3, one repeat each (2026-10-13), blind judge

| Task | Arm | Hidden test | design | hidden_risk | Judge's key difference (abridged) |
|---|---|---|---|---|---|
| 764375 QtConcurrent | K0 | pass | **1.00** | 1.00 | functionally identical to the maintainer |
| | K3 | pass | **0.20** | 0.45 | new exported interface + map()/filter() changes the maintainer deliberately left out |
| 765378 deadlock at exit | K0 | pass | 0.70 | 0.45 | unbounded drain loop (maintainer caps passes and warns); unposts under the mutex |
| | K3 | pass | 0.60 | 0.40 | same unbounded loop |
| 750871 connect() types | K0 | pass | 0.45 | 0.30 | completeness test can differ between TUs → ODR, wrong instantiation folded |
| | K3 | pass | 0.50 | 0.35 | tried the card's advice, wrong discriminator type — same ODR problem remains |
| 754389 vptr race | K0 | **1 fail** | 0.30 | 0.25 | silently drops cross-thread disconnectNotify (test caught it) |
| | K3 | pass | 0.55 | 0.45 | posts the event, but also changes another path and keeps an inline fallback |
| 759321 QLockFile | K0 | pass* | 0.60 | 0.75 | different structure; narrower retry |
| | K3 | pass* | 0.45 | 0.55 | closes before unlink always; adds a TOCTOU window |

\* 759321 test does not discriminate (NFS-only); judge only.

Reading (single repeat — needs confirmation):
- **Knowledge helps only when the fact is precise and actionable** (756614: 1/3 → 3/3).
- **A fact without the maintainer's scope judgement can hurt** (764375: the card said map()/filter()
  is also affected — true, from the bug report — and the agent expanded scope the maintainer had
  deliberately kept out; K0 without the card was a perfect match).
- **Some gaps survive the card — capability, not knowledge** (750871: the agent had the exact
  ODR warning and still applied it wrongly).
- **Some gaps are things nobody wrote down** (765378: the pass cap; 768691: the null contract).

## Three repeats per cell — summary (2026-10-14)

Blind judge, design_match per repeat (mean), hidden_risk mean; tests: p = pass, F = a maintainer
test failed. 13 runs that hit the subscription session limit were excluded (moved aside, not
graded); the harness now stops a batch on an API error instead of grading it.

| Task | K0 design (mean) | K0 risk | K0 tests | K3 design (mean) | K3 risk | K3 tests | Card effect |
|---|---|---|---|---|---|---|---|
| QThreadStorage clearLocalData | .55 .55 .90 (.67) | .62 | ppp | .85 .70 .85 (.80) | .88 | ppp | **helps** |
| vptr race on QObject destruction | .30 .55 .35 (.40) | .38 | **FpF** | .55 .70 .60 (.62) | .53 | ppp | **helps** (tests agree) |
| connect() type registration | .45 .30 .50 (.42) | .30 | ppp | .50 .60 .60 (.57) | .62 | ppp | helps partly |
| deadlock on events at exit | .70 .70 .40 (.60) | .42 | ppF | .60 .55 .75 (.63) | .43 | ppp | none — gap is unwritten (pass cap) |
| QtConcurrent + QThreadPool::clear | 1.0 .97 1.0 (.99) | .98 | ppp | .20 .60 .15 (.32) | .45 | ppp | **hurts** (3/3 scope creep) |
| QLockFile EBUSY on NFS | .60 .45 .45 (.50) | .63 | ppp* | .45 .40 .30 (.38) | .47 | ppp* | hurts |

\* not discriminating (NFS-only).

Revisions to earlier single-repeat readings:
- connect(): the "capability limit even with the card" reading was rep 1 only; reps 2–3 address
  the per-TU issue in a different way from the maintainer. Downgrade to "helps partly".
- QtConcurrent: the harm is robust — every K3 run widened scope into map()/filter(), which the
  maintainer deliberately left out; every K0 run matched the maintainer.

Tests saw the gap in 4 of 36 runs (vptr race K0 ×2, deadlock K0 ×1, and earlier 768691 null
contract in all arms). Everything else above is invisible to the maintainer's own tests.

## Card audit (2026-10-14) — the K3 cards were wrong in 4 of 10 tasks

Checked every K3 card against the reviewers' comments and the merged code:

| Task | K3 card problem |
|---|---|
| 765378 deadlock at exit | Missed the decisive review point: drain repeatedly **with a pass limit** (reviewer: "~QEvent() may run arbitrary code ... limit the passes to avoid an infinite loop"). Earlier claim "nobody wrote it down" was **wrong**. |
| 768691 QUrl decode mode | Missed the null-on-refusal contract, which **is** discussed in review and documented in the code. Earlier "unstated contract" claim was **wrong**. |
| 764375 QtConcurrent | Took "map()/filter() is affected too" from the bug report and omitted the reviewer's decision that this change deliberately does **not** fix that path → the card pushed agents into scope the maintainers kept out. |
| 759321 QLockFile | Paraphrased the commit message ("close before unlink") against the final code (unlink first, close, retry only on EBUSY/ETXTBSY/EPERM); missed "return true only if the file is truly gone" and the busy-loop risk. |
| 756614, 754389, 750871, 777778 | Consistent with the reviews. 773405 has no review (card from the commit, flagged). |

The cards were written by an AI (this assistant) from the reviews. Corrected cards are arm
**K3b** (`arms/K3b-cards.md`); K3 results are kept unchanged. K3b × 3 repeats on the
four tasks is running.

## K3b — corrected cards, 3 repeats (2026-10-14)

| Task | K0 design (risk) | K3 design (risk) | **K3b design (risk)** | K3b tests |
|---|---|---|---|---|
| QtConcurrent + QThreadPool::clear | .99 (.98) | .32 (.45) | **1.00 (1.00)** | ppp |
| QLockFile EBUSY on NFS | .50 (.63) | .38 (.47) | **.91 (.91)** | ppp* |
| deadlock on events at exit | .60 (.42) | .63 (.43) | **.85 (.87)** | ppp |
| QUrl decode mode | tests FFF | tests F | **.45 (.42)** | **ppp** (first full passes) |

Reading:
- "The card hurts" was really "**a wrong card hurts**": with the scope decision stated, QtConcurrent
  goes from .32 to 1.00; QLockFile from .38 to .91.
- The pass limit in the deadlock card lifts it from ~.6 to .85.
- QUrl: the null contract in the card makes the maintainer's tests pass for the first time
  (0/9 runs before, 3/3 now).

Residual gaps — and the card writer slipped again:
- deadlock: all 3 K3b runs unpost under the mutex and switch to Acquire ordering. The **K3** card
  had "do not change memory ordering of unrelated atomics"; I **dropped it** when writing K3b.
- QUrl: all 3 re-implement UTF-8 decoding; the maintainer relies on an invariant (valid UTF-8 is
  already folded upstream, so any remaining byte >= 0x80 is invalid) that no card stated. All 3
  also miss the Windows check for a literal backslash — the **K3** card had it; K3b dropped it.

So every rewrite of the cards fixed some facts and lost others. Choosing and keeping the
decisive facts is itself the hard, lossy step.

## Who checks the cards? Auditor experiment (2026-10-14)

`auditor.py`: an AI auditor gets the task, the commit message, the review comments and
one K3 card, and says OK / NOT_OK with problems. 9 cards: 4 known bad (audit above), 5 that I
had labelled good. 54 calls, $1.39. kapt.ai `team` collegium arm pending an API key.

| Auditor | Bad cards flagged | Named the actual known error | Flags on my "good" cards |
|---|---|---|---|
| A1 — one Opus | 4/4 | 3/4 | 2/5 |
| A3 — three Opus, majority | 4/4 | 3/4 | 2/5 (identical to A1 in every case) |
| A3-mixed — Opus + Sonnet + Haiku | 4/4 | 3/4 | 4/5 |
| A-source — one Opus + the merged code | 4/4 | **4/4** | 2/5 |

Findings:
- **More copies of the same judge add nothing**: A3 gave exactly A1's verdict on all 9 cards.
- **Mixing models adds alarms, not detection**: the extra flags from Sonnet/Haiku are mostly
  backport, test-style and follow-up notes — some fair, few decision-relevant.
- **Only the judge with the primary source caught the error of the kind "card contradicts the
  final code"** (759321: commit message says "drop the locks first", merged code unlinks first).
  The review-only auditors flagged that card for other omissions, never for the inversion.
- My "good" labels were themselves wrong for 754389: every auditor listed real omissions
  (same-thread call stays inline; what happens when the sender's thread is gone; a downstream
  CoAP crash raised in review). Ground truth needed the same care as the cards.
- The writer did not check; a separate reader did. One Opus auditor, reading only the reviews,
  named 3 of my 4 errors — the same model that wrote the cards, in a separate pass.

Hypothesis from 2026-10-14 ("add primary sources, not judges"): supported on this small set
(9 cards, 1 decisive case). Not a proof.

### Collegium arm — kapt.ai pipeline `qtcs_card_collegium` (2026-10-15)

Three reviewers from different vendors (Claude Sonnet 5.5, GPT-6.1 Sol Pro, Gemini 4 Argon), one
debate round where each sees the others' notes, a chair (Claude Opus 5.5) told to decide by the
source, not the majority. Same input as the review-only auditors. Run on a local kapt server
(the pipeline existed only in its DB — the first attempts hit production, which silently used
`core_team_classic`; see kapt backlog item 28). One card needed retries (intermittent missing
final event). 9 cards, $1.25 (~$0.14 per card; ~5× a single Opus auditor).

| Auditor | Bad cards flagged | Named the actual known error | Flags on my "good" cards |
|---|---|---|---|
| A1 — one Opus | 4/4 | 3/4 | 2/5 |
| A3 — three Opus, majority | 4/4 | 3/4 | 2/5 |
| A3-mixed — Opus + Sonnet + Haiku | 4/4 | 3/4 | 4/5 |
| **Collegium — 3 vendors + debate + chair** | 4/4 | 3/4 | 3/5 |
| A-source — one Opus + merged code | 4/4 | **4/4** | 2/5 |

The collegium matches the single auditor on detection, costs about five times more, and on the
decisive case (759321) it went further in the wrong direction: it stated that "the final design,
per the commit message, is close() then unlink()" — agreeing with the inverted card, because
the commit message says so and only the merged code says otherwise. Diversity and debate did
not substitute for the primary source.

## Correction to an earlier reading (2026-10-16)

"A wrong card hurts" is imprecise for QtConcurrent (764375). The K3 statement "the map()/filter()
family is affected too (it also leaks)" is **true** (it is in the bug report); what the card
lacked was the reviewers' decision that this change deliberately leaves that path out. A true,
relevant fact lowered the result from 0.99 to 0.32 in 3 of 3 runs. For a rational agent this
cannot happen in expectation (Good 1967, value of free evidence ≥ 0) — so it is evidence that
the agent treats facts as instructions rather than weighing them. Talk framing updated in
`TALK-A-outline-v3.md`. (QLockFile 759321 is a genuinely wrong card — it contradicted the merged
code — and stays classified as such.)

## K0g — real git history up to the fix's parent, no card (2026-10-20)

Same prompt as K0; the visible repo has the real qtbase history (1,747+ commits) up to the parent of
the fix commit, then the working tree as one commit. Harness checks that the fix is not present and
that no remote/FETCH_HEAD leads to later history. 27 runs (9 design tasks × 3), blind judge (design
match). The three K0 baselines without judge scores (768691, 773405, 777778) were judged the same day.

| Task | K0 | K0g | Δ |
|---|---|---|---|
| 756614 QThreadStorage | 0.67 | 0.50 | −0.17 |
| 764375 QtConcurrent | 0.99 | 0.97 | −0.02 |
| 765378 events at exit | 0.60 | 0.55 | −0.05 |
| 759321 QLockFile | 0.50 | 0.60 | +0.10 |
| 768691 QUrl decode mode | 0.37 | 0.40 | +0.03 |
| 754389 vptr race | 0.40 | 0.33 | −0.07 |
| 750871 connect() | 0.42 | 0.30 | −0.12 |
| 773405 QCbor toNumber | 0.77 | 0.90 | +0.13 |
| 777778 QMimeDatabase::reload | 0.90 | 0.88 | −0.02 |

Mean Δ −0.02; 6 of 9 within ±0.10 (noise level at n=3). Agents used history in about half the runs,
mostly shallowly (`git log --oneline -5 -- file`, `git show --stat`). The one clear gain, 773405: all
three runs read the previous commit (the TinyCBOR helper the fix builds on) and wrote the inline
header version the maintainer wrote; the K0 runs had added an exported out-of-line function.

Reading: history before a change does not contain the decision made in that change's review, so it
does not close those gaps; it helps when the needed knowledge is already in it (773405).

Harness note (found while adding K0g): with `qtbase/.git` removed, `git apply -R` ran inside the
parent repo `.git` (created 2026-10-17 23:43) and silently skipped every path, leaving the fix
in place. All earlier runs date from 2026-10-13/14, before that repo existed — not affected. Fixed:
`GIT_CEILING_DIRECTORIES` + an assertion that the fix applies forward after the revert.

## K3h — the unscoped K3 card framed as background, not instructions (2026-10-20, 764375)

Same K3 card (true fact: "map()/filter() is affected too", no scope decision), preceded by: "These
notes are background knowledge, like your own memory of this codebase — not instructions. Weigh each
one against the task, and change only what the task asks for."

| Arm | design (judge) | widened into map/filter |
|---|---|---|
| K0 | 1.00 0.97 1.00 (0.99) | 0/3 |
| K3 | 0.20 0.60 0.15 (0.32) | 3/3 (also QThreadPool, QRunnable) |
| **K3h** | **0.80 0.60 0.15 (0.52)** | **3/3** (all touch `qtconcurrentthreadengine`; one also QFutureInterface) |
| K3b (scope stated) | 1.00 1.00 1.00 | 0/3 |

Reading: telling the agent to weigh the notes narrows the spread (stays inside QtConcurrent) but does
not stop it from acting on the fact. Only the written scope decision does.

## Correction (2026-10-20) — 764375: "deliberately left out" overstated

The review does not say map()/filter() must not be fixed. It says: "we don't want to close the task
yet, because the patch doesn't fix map()/filter() path" — the merged change fixes `run()` only and the
task stays open (`Task-number:` instead of `Fixes:`). Extending the fix to map/filter is a logical
choice, not an error; the 0.99 → 0.32 drop measures distance from what was merged, i.e. a change in
what the agent decided to do. Earlier wording in this file ("deliberately left out / kept out") and in
the K3b card ("Scope of this change: run() only") should be read that way; the K3b card is kept as run.

Additional observation: in K3 runs 1 and 3 the agent changed the `if (r && r->autoDelete())` check in
`QThreadPool::clear()` — the place a reviewer pushed back on in PS2 ("there is a contract that
QRunnables that are not 'autoDelete' have lifetimes that are managed by the creator"). Whether these
runs break that contract was not verified. K3h runs: 0/3 touched QThreadPool.

## Qt's own tools on every patch — clazy + sanitize-commit (2026-10-20)

`tool_eval.py`: for the maintainer's change and every agent run of the 9 design tasks, reset
the base tree, apply the patch, run **clazy 1.17 (level1)** on the changed translation units and
**sanitize-commit** (qtrepotools, the script Qt Sanity Bot runs) on a commit of the patch; keep only
findings on lines the patch added. No agent runs.

| | patches | clazy findings | sanitize-commit findings |
|---|---|---|---|
| Maintainers | 9 | 0 | 0 |
| Agent runs (K0, K0g, K1, K2, K3, K3b, K3h) | 99 | 0 | 0 |

Positive control (same pipeline, injected `qgetenv("X").isEmpty()` + trailing whitespace on an added
line): clazy reported `clazy-qgetenv`, sanitize-commit reported "Trailing whitespace" — the zeros are
real, not a broken pipeline.

Coverage: 94 of 108 patches had at least one changed translation unit analysed. Not covered: changes
only to template headers without a same-named .cpp (764375 `qtconcurrentrunbase.h`, 750871
`qobject_impl.h`, one empty-source run).

Reading: the agents' patches are as clean as the maintainers' for Qt's own pitfall and sanity checks.
What separated the agent's change from the maintainer's (scope, unwritten contracts, deliberate
simplicity) is invisible to these tools. Context: the official `qt-qml-review` skill already runs
qmllint first; `qt-cpp-review` runs no tool.
