# What is specific to Qt in the experiment (2026-10-20)

What an agent meets in Qt that it would not meet in an arbitrary codebase. Data: `results/` (101
agent runs, 93 judged), `tasks/*/{commit,review}.txt`, `arms/K3*-cards.md`. The "decisive point" of
each change was classified by the author of this experiment, not by a Qt maintainer.

## 1. Where the decisive point of each design change is written down

| Change | Decisive point (what the agent got wrong without help) | In the commit message? | Only in Gerrit review / code |
|---|---|---|---|
| 756614 QThreadStorage::clearLocalData | new function must not re-create thread data | **yes** ("Since this is a new function, we can change a subtle problem…") | — |
| 754389 sender vptr race | notify inline only from the owning thread, else post | **yes** (full rationale) | — |
| 750871 connect() metatypes | reuse `qTryMetaTypeInterfaceForType()`, as moc does | **yes** | — |
| 777778 QMimeDatabase::reload | static; tests use reload(), variable no longer exported | **yes** | — |
| 773405 QCborStreamReader::toNumber | reuse TinyCBOR helpers | **partly** (names the helper commit) | no review |
| 764375 QtConcurrent + clear() | fix run() only; task kept open for map()/filter() | no — but footer is `Task-number:`, not `Fixes:` | review: "we don't want to close the task yet, because the patch doesn't fix map()/filter() path" |
| 765378 events at exit | bounded passes (MaxPasses) because ~QEvent() may post | no ("drain whatever those destructors post") | review: "we limit the passes to avoid an infinite loop" |
| 768691 QUrl decode mode | null result on refusal (contract of appendTo) | partly ("returns a negative value") | review + internal docs |
| 759321 QLockFile EBUSY | unlink while locked first; close + retry only on EBUSY/ETXTBSY/EPERM | **contradicts** the merged code ("We must drop the locks first, which close() does, then unlink()") | merged code only |

Counts (9 changes): 4 fully + 2 partly in the commit message; 2 only in review; 1 commit message
describes close-then-unlink while the merged code unlinks first and closes only as a fallback
(the message was written in review, PS3, next to the unlink-first code). For the **same** change none of this is visible to an
agent writing it (it is written with or after the change). For a **later** change in the same code,
an agent sees commit messages through `git log` — the review only if it goes to Gerrit.

## 2. Qt already has a footer that encodes scope

Qt commit footers distinguish `Fixes: QTBUG-…` (bug closed by this change) from `Task-number:
QTBUG-…` (related, not closed). 764375 uses `Task-number:` because map()/filter() remained broken —
the scope decision is encoded, but not *which part* is left out. A human Qt developer reads that;
neither our agent nor our AI-written card did.

## 3. Docs live next to the code

qdoc comments sit in the `.cpp` the agent edits. In 756614 the K0 runs read the existing shutdown
warning and copied it into their own docs (listing the new function as unsafe) — the hazard was
found because it was next to the code. (`results/756614/K0/claude-{1,2}/agent.diff`)

## 4. The agent follows Qt's own conventions

New API gets `\since` and a qdoc `\fn` block in agent diffs as in the maintainers' (756614, 777778;
773405 agents even add `\since` where the maintainer's diff has none in the .cpp). Code size is the
same as the maintainers': median 0.9× non-test lines over 11 tasks (earlier "agents write more" was
an artefact of counting tests). Exception: 764375 with the unscoped card, 61 vs 8 lines.

## 5. Qt's own AI aids carry style, not decisions

The official review skill (K2) and the wiki conventions (K1) did not move the decisive choice in
756614 (1/3 like no help). In Gerrit change 761210 (qtaiskills, LDR-1 regex fix), reviewers wrote
that regexes cannot understand QML and agents should use qmllint ("qmllint actually understands
QML"); the change was abandoned on 2026-10-19: "the same objective can be reached with QML linter,
which we can assume to be available."

## Not established

- Whether reading *past* Gerrit reviews would predict the next decision (not tested; question for the room).
- Giving the agent `git log` up to the change (K0g, 27 runs, 2026-10-20): no average effect
  (Δ 0.00); helps only where the knowledge is already in the history (773405). See
  `RESULTS.md`.

## 6. Agents already write Qt

qtbase, June – Oct 12, 2026: about 2,100 commits; at least 23 carry an AI co-author trailer (16
`Co-authored-by: Copilot`, 7 Claude models) — a lower bound, since the trailer is optional. One of our
tasks (768691) is such a commit. (`git --git-dir=hidden.git log` grep, 2026-10-20.)

## 7. Tools that understand Qt (verified 2026-10-20, for the questions in the ending)

- clazy — "Qt-oriented static code analyzer based on the Clang framework", 50+ Qt checks
  (connect-non-signal, qstring-allocations, range-loop-detach, …). github.com/KDE/clazy
- qmlls — QML Language Server, ships with Qt; qmllint diagnostics, completion, go to definition, find
  usages, formatting. doc.qt.io/qt-6/qtqml-tooling-qmlls.html. First version: not established — don't
  name one on stage.
- sanitize-commit — qtrepotools/git-hooks; checks commit message (incl. Task-number/Fixes footers),
  spelling, copyright headers, generated files, whitespace. Run by Qt Sanity Bot ("Simple Sanitizer");
  the wiki asks contributors to install it locally. wiki.qt.io/Early_Warning_System
- qdoc warning for a missing `\since`: not established — left out.

