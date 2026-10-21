#!/bin/sh
# Rebuilds arms/K1-qt-conventions.md (arm K1) from the Qt wiki, which is not redistributed here.
# The experiment used the pages as fetched on 2026-10-12; sha256 of that file without its first
# (date) line:
#   d36444c5728f212b4b104d671f4fb49d8e4d883fd713e458cf3124099701ea08
# The wiki changes over time, so a fresh fetch may differ.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/arms/K1-qt-conventions.md"
TMP="$OUT.tmp"
fail() { echo "fetch failed: $1" >&2; rm -f "$TMP"; exit 1; }
echo "# Qt project conventions (from wiki.qt.io, fetched $(date +%Y-%m-%d))" > "$TMP"
echo >> "$TMP"
curl -fsSL "https://wiki.qt.io/index.php?title=Coding_Conventions&action=raw" >> "$TMP" || fail Coding_Conventions
printf '\n\n' >> "$TMP"
curl -fsSL "https://wiki.qt.io/index.php?title=Qt_Coding_Style&action=raw" >> "$TMP" || fail Qt_Coding_Style
mv "$TMP" "$OUT"
echo "wrote $OUT"
echo "sha256 without the date line: $(tail -n +2 "$OUT" | shasum -a 256 | cut -d' ' -f1)"
