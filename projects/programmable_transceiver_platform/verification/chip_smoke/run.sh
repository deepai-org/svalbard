#!/bin/bash
# Chip power-up smoke test of one chip, one command:   run.sh <rf|wired> [smoke.py options, e.g. --tree DIR --netlist F]
# Runs the test on the KH_CONN=1 top-level netlist, then the negative control (one c_* consumer pin unbound in a copy of
# the netlist: the test must FAIL with that exact wire). Exit 0 only if the test passes AND the negative control is caught.
# Layout mode:  run.sh <rf|wired> --layout <ASM_RUN dir> [--out DIR]: the same test on the netlist EXTRACTED from
# <run>/chip/pt_chip_top.gds (layout.sh), and as negative control the test on an extraction with the metal erased at one pad
# tie and one c_* consumer pin (must FAIL naming both). Default out scratch/chip_smoke/<chip>-layout.
# Summary: <out>/summary.json (+ <out>-mut/summary.json); default out scratch/chip_smoke/<chip>.
set -u
# layout negative control: metal erased at the POR_BYPASS pad pull-down tie, one c_* trim consumer pin and one block VSS pin
# (aosc.VSS: a floating rail pin that is not the named pad_tlp exception must still fail)
layout_cut() { case $1 in rf) echo io_bidir_16.PD,lna.ct2,aosc.VSS ;; wired) echo io_bidir_16.PD,ctle.ctle_peak2,aosc.VSS ;; esac; }
H=$(cd "$(dirname "$0")" && pwd); CHIP=${1:?rf|wired}; shift
export OMP_NUM_THREADS=1
if [ "${1:-}" = --layout ]; then      # layout mode: run.sh <chip> --layout <ASM_RUN dir> [--out DIR] [smoke.py options]
  RUN=${2:?run dir}; shift 2; OUT=$(cd "$H/../../../.." && pwd)/scratch/chip_smoke/$CHIP-layout
  [ "${1:-}" = --out ] && { OUT=$2; shift 2; }
  CUT=$(layout_cut "$CHIP")
  "$H/layout.sh" "$CHIP" "$RUN" "$OUT/extract" || { echo "chip_smoke $CHIP layout: extraction failed"; exit 1; }
  "$H/layout.sh" "$CHIP" "$RUN" "$OUT/extract-cut" "cut=$CUT" || { echo "chip_smoke $CHIP layout: cut extraction failed"; exit 1; }
  python3 "$H/smoke.py" --chip "$CHIP" --netlist "$OUT/extract/layout.spice" --out "$OUT/test" "$@"; RC=$?
  python3 "$H/selftest.py" --chip "$CHIP" --layout-cut "$OUT/extract-cut/layout.spice" "$CUT" --out "$OUT/test" "$@"; ST=$?
  echo "chip_smoke $CHIP layout ($RUN): test rc=$RC, negative control (metal erased at $CUT) rc=$ST"
  [ $RC -eq 0 ] && [ $ST -eq 0 ]; exit
fi
python3 "$H/smoke.py" --chip "$CHIP" "$@"; RC=$?
python3 "$H/selftest.py" --chip "$CHIP" "$@"; ST=$?
echo "chip_smoke $CHIP: test rc=$RC, negative control rc=$ST"
[ $RC -eq 0 ] && [ $ST -eq 0 ]
