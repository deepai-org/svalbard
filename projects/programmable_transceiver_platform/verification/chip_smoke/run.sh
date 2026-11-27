#!/bin/bash
# Chip power-up smoke test of one chip, one command:   run.sh <rf|wired> [smoke.py options, e.g. --tree DIR --netlist F]
# Runs the test on the KH_CONN=1 top-level netlist, then the negative control (one c_* consumer pin unbound in a copy of
# the netlist: the test must FAIL with that exact wire). Exit 0 only if the test passes AND the negative control is caught.
# Summary: <out>/summary.json (+ <out>-mut/summary.json); default out scratch/chip_smoke/<chip>.
set -u
H=$(cd "$(dirname "$0")" && pwd); CHIP=${1:?rf|wired}; shift
export OMP_NUM_THREADS=1
python3 "$H/smoke.py" --chip "$CHIP" "$@"; RC=$?
python3 "$H/selftest.py" --chip "$CHIP" "$@"; ST=$?
echo "chip_smoke $CHIP: test rc=$RC, negative control rc=$ST"
[ $RC -eq 0 ] && [ $ST -eq 0 ]
