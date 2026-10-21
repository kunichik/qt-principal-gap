#!/bin/sh
# Rebuilds arms/K1-qt-conventions.md (arm K1) from the Qt wiki, which is not redistributed here.
# The experiment used the pages as fetched on 2026-10-12; sha256 of that file without its first
# (date) line:
#   d36444c5728f212b4b104d671f4fb49d8e4d883fd713e458cf3124099701ea08
# The wiki changes over time, so a fresh fetch may differ.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/arms/K1-qt-conventions.md"
{
  echo "# Qt project conventions (from wiki.qt.io, fetched $(date +%Y-%m-%d))"
  echo
  curl -sL "https://wiki.qt.io/index.php?title=Coding_Conventions&action=raw"
  echo
  echo
  curl -sL "https://wiki.qt.io/index.php?title=Qt_Coding_Style&action=raw"
} > "$OUT"
echo "wrote $OUT"
echo "sha256 without the date line: $(tail -n +2 "$OUT" | shasum -a 256 | cut -d' ' -f1)"
