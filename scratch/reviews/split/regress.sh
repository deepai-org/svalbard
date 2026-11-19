#!/bin/bash
# Split acceptance regression (both chips):  regress.sh <tag> [repo root, default this checkout]
# chip-top run.sh of both chips (expected: only demand / staged / isolation-audit items), the r8 digital regression list
# (each chip-level target runs both chips), contract and spec checks. Serial, OMP_NUM_THREADS=1.
# Log: scratch/reviews/split/regress_<tag>.log (one line per target), per-target output next to it.
R=${2:-$(cd "$(dirname "$0")/../../.." && pwd)}; cd "$R" || exit 2; export OMP_NUM_THREADS=1
D=$(dirname "$0"); D=$(cd "$D" && pwd); L=$D/regress_$1.log; : > "$L"
run() { s=$(date +%s); "$@" > "$D/out_$1_$t.log" 2>&1; echo "$t rc=$? $(( $(date +%s)-s ))s" >> "$L"; }
P=projects/programmable_transceiver_platform
for c in rf wired; do
  t=chip-top-$c; s=$(date +%s); sh $P/integration/chips/$c/run.sh > "$D/out_$1_$t.log" 2>&1
  echo "$t $(grep -c 'NOT detected\|SELFTEST FAIL\|does not compile\|boundary sim: FAIL' "$D/out_$1_$t.log") problems; $(grep '^SUMMARY' "$D/out_$1_$t.log" | sed 's/.*staged/staged/') $(( $(date +%s)-s ))s" >> "$L"
done
for t in transceiver-regfile transceiver-regfile-formal transceiver-top-modes transceiver-chip-io transceiver-por-bypass-chip transceiver-contract transceiver-ctl-blocks transceiver-digital-rtl-checks; do
  s=$(date +%s); make $t > "$D/out_$1_$t.log" 2>&1; echo "$t rc=$? $(( $(date +%s)-s ))s" >> "$L"
done
for t in check_performance_requirements check_architecture_conn; do
  s=$(date +%s); python3 $P/spec/$t.py > "$D/out_$1_$t.log" 2>&1; echo "$t rc=$? $(( $(date +%s)-s ))s" >> "$L"
done
echo ALLDONE >> "$L"
