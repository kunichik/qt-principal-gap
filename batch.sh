#!/bin/sh
# Runs (task arm rep) triples sequentially; one line per run in batch.log
cd "$(dirname "$0")"
while read t a r; do
  [ -z "$t" ] && continue
  if [ -f results/$t/$a/claude-$r/summary.json ]; then echo "skip $t $a $r" >> batch.log; continue; fi
  python3 harness.py $t $a $r --model opus > /tmp/claude-501/run.out 2>&1
  rc=$?
  tail -1 /tmp/claude-501/run.out >> batch.log
  [ $rc -eq 3 ] && { echo "STOPPED: api error / usage limit" >> batch.log; exit 3; }
done
