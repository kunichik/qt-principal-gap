# Third-party material

- `tasks/*/src.diff`, `tasks/*/test.diff`, `tasks/*/commit.txt` — changes and commit messages from
  qtbase (codereview.qt-project.org / code.qt.io), under the licences of the files they touch
  (see the SPDX headers in qtbase: LGPL-3.0-only / GPL-2.0-only / GPL-3.0-only /
  LicenseRef-Qt-Commercial and others). Commit messages are kept verbatim.
- `tasks/*/review.txt` — excerpts of public Gerrit review comments, quoted for research. Reviewer names
  are replaced by stable aliases (`REVIEWERS-ANONYMISED.txt`); the original reviews are public on
  codereview.qt-project.org.
- `arms/K2-qt-cpp-review/` — copy of the official Qt agent skill `qt-cpp-review` from qtaiskills
  (`92b48ae`), © The Qt Company Ltd., LicenseRef-Qt-Commercial OR BSD-3-Clause; its `LICENSE.txt` is
  included.
- `tools/sanitize-commit` — from qtrepotools/git-hooks, © The Qt Company Ltd. and Petroules
  Corporation, 3-clause BSD licence (see the file header).
- Arm K1 (Qt wiki "Coding Conventions" and "Qt Coding Style") is not redistributed; `tools/fetch-k1.sh`
  downloads it from wiki.qt.io.
- `results/*/agent.diff` and `agent.json` — output of Claude (Anthropic) produced in this experiment.
