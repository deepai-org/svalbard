#!/usr/bin/env bash
# Simulation and lint of the consolidation P2-6 / P2-10 standard-cell blocks with the
# host iverilog/verilator (same tools as check_regfile.py).
#   run_p2_sim.sh pattern     rtl/pt_pattern.sv          sim/tb_pt_pattern.sv
#   run_p2_sim.sh clocktree   rtl/pt_clocktree_slow.sv   sim/tb_pt_clocktree_slow.sv
# pattern also runs sim/tb_digital_prbs.sv (pt_digital loopback). Both re-elaborate pt_chip. Logs: scratch/p2-digital/sim/.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
PROJ="$ROOT/projects/programmable_transceiver_platform"
OUT="$ROOT/scratch/p2-digital/sim"
mkdir -p "$OUT"
cd "$PROJ"
case "${1:-}" in
  pattern)   rtl=rtl/pt_pattern.sv;        tb=tb_pt_pattern;        tops="pt_pattern_gen pt_pattern_check"; pass=PATTERN_PASS ;;
  clocktree) rtl=rtl/pt_clocktree_slow.sv; tb=tb_pt_clocktree_slow; tops="pt_clocktree_slow"; pass=CLOCKTREE_SLOW_PASS ;;
  *) echo "usage: $0 pattern|clocktree" >&2; exit 2 ;;
esac
for t in $tops; do
  verilator --lint-only -Wall -Wno-DECLFILENAME -Wno-WIDTH -Wno-UNUSEDSIGNAL -Wno-SYNCASYNCNET "$rtl" --top-module "$t" \
    > "$OUT/lint_$t.log" 2>&1 || { cat "$OUT/lint_$t.log"; exit 1; }
done
iverilog -g2012 -s "$tb" -o "$OUT/$tb.vvp" "$rtl" "sim/$tb.sv"
vvp -n "$OUT/$tb.vvp" | tee "$OUT/$tb.log" | tail -12
grep -q "^$pass\$" "$OUT/$tb.log"
if [ "$1" = pattern ]; then   # pt_digital-level loopback through the legacy wire_trim[15] path
  iverilog -g2012 -I rtl -s tb_digital_prbs -o "$OUT/tb_digital_prbs.vvp" rtl/*.sv sim/tb_digital_prbs.sv
  vvp -n "$OUT/tb_digital_prbs.vvp" | tee "$OUT/tb_digital_prbs.log" | tail -3
  grep -q "^DIGITAL_PRBS_PASS\$" "$OUT/tb_digital_prbs.log"
fi
iverilog -g2012 -I rtl -s pt_chip -o "$OUT/pt_chip.vvp" integration/pt_chip.sv rtl/*.sv > "$OUT/pt_chip_elab.log" 2>&1 \
  || { cat "$OUT/pt_chip_elab.log"; exit 1; }
echo "pt_chip elaboration: ok"
