#!/bin/sh
# Runs (task arm rep) triples sequentially; one line per run in batch.log.
# Stops on exit 3 (usage limit / API error); an agent crash (exit 4) is logged and skipped.
cd "$(dirname "$0")"
out=$(mktemp)
while read t a r; do
  [ -z "$t" ] && continue
  if [ -f "results/$t/$a/claude-$r/summary.json" ]; then echo "skip $t $a $r" >> batch.log; continue; fi
  python3 harness.py "$t" "$a" "$r" --model opus < /dev/null > "$out" 2>&1
  rc=$?
  tail -1 "$out" >> batch.log
  [ $rc -eq 3 ] && { echo "STOPPED: api error / usage limit" >> batch.log; rm -f "$out"; exit 3; }
done
rm -f "$out"
