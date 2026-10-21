#!/bin/sh
# Judges every judged run once more, for test-retest of the judge. Each run's agent.diff is copied to
# rejudge/<task>/<arm>/<run>/ and judge.py runs there unchanged, so judge.json is never overwritten;
# copy the result to the run as judge-retest.json.
cd "$(dirname "$0")/.."
for j in results/*/*/claude-*/judge.json; do
  d=$(dirname "$j"); r=rejudge/${d#results/}
  [ -f "$r/judge.json" ] && continue
  mkdir -p "$r"; cp "$d/agent.diff" "$r/"
  python3 judge.py "$r" > "$r/judge.log" 2>&1   # exits 1 after writing: the run is outside results/
  [ -f "$r/judge.json" ] && cp "$r/judge.json" "$d/judge-retest.json" || echo "FAIL $r"
done
