#!/usr/bin/env bash
# Rough GF180 size and unplaced timing of the consolidation P2-6 (rtl/pt_pattern.sv)
# and P2-10 (rtl/pt_clocktree_slow.sv) standard-cell blocks with the LibreLane GF180
# canary image: yosys synth + abc onto gf180mcu_fd_sc_mcu7t5v0 (tt 25 C 3.3 V), then
# (abc -D 4000: delay mapping toward 250 MHz with abc fanout buffering and gate
# up/down-sizing, standing in for the placement-time repair a real flow does), then
# OpenSTA report_clock_min_period at tt_025C_3v30 and ss_125C_3v00 with no wire
# parasitics (optimistic: placement/routing/clock-tree not included). No network.
# Results: scratch/p2-digital/synth/<top>/{stat.txt,sta.txt,netlist.v}.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
PROJ="$ROOT/projects/programmable_transceiver_platform"
OUT="${OUT:-$ROOT/scratch/p2-digital/synth}"
IMAGE="${SVALBARD_DIGITAL_IMAGE:-svalbard/librelane-gf180-canary:2026.08}"
rm -rf "$OUT"; mkdir -p "$OUT"
docker image inspect "$IMAGE" --format '{{.Id}} {{.Architecture}}' > "$OUT/image.txt"
# As wired in pt_digital today: PRBS31 only, legacy tie-offs (yosys prunes the unused modes).
cat > "$OUT/wrappers.sv" <<'EOF'
module pt_pattern_tx_tied(input wire clk,rst_n,request,output wire [9:0] word,output wire ready);
 pt_pattern_tx #(.W(10)) gb(.clk(clk),.rst_n(rst_n),.request(request),.cfg_mode(3'd3),.cfg_invert(1'b0),
  .cfg_user(10'd0),.inject(1'b0),.word(word),.ready(ready));
endmodule
module pt_pattern_rx_tied(input wire clk,rst_n,enable,valid,input wire [9:0] data,output wire locked,lost_lock,
  output wire [15:0] errors_gray);
 wire [15:0] errors;
 pt_pattern_rx #(.W(10),.CW(16)) gb(.clk(clk),.rst_n(rst_n),.enable(enable),.valid(valid),.data(data),.cfg_mode(3'd3),
  .cfg_invert(1'b0),.clear(!enable),.locked(locked),.lost_lock(lost_lock),.errors(errors),.errors_gray(errors_gray));
endmodule
EOF
# PATTERN_SRC: override the pattern RTL (e.g. an earlier revision for a before/after table).
docker run --rm --network none --cpus 4 --memory 8g --user "$(id -u):$(id -g)" -e HOME=/tmp --entrypoint bash \
  -v "$PROJ:/src:ro" -v "$OUT:/out" ${PATTERN_SRC:+-v "$PATTERN_SRC:/pattern_src.sv:ro"} -e ONLY="${ONLY:-}" "$IMAGE" -lc '
set -e
L=/pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib
TT=$L/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.lib
SS=$L/gf180mcu_fd_sc_mcu7t5v0__ss_125C_3v00.lib
yosys -V > /out/yosys_version.txt
# synth <top> <files> <clocks> [flatten:1|0] [pre-synth yosys cmds] [STA exception tcl]
synth() {
  top=$1; files=$2; clocks=$3; flat=${4:-1}; pre=${5:-}; exc=${6:-}; d=/out/$top; mkdir -p $d
  fl=""; [ "$flat" = 1 ] && fl="-flatten"
  yosys -q -l $d/synth.log -p "
    read_liberty -lib $TT
    read_verilog -sv $files
    $pre
    synth -top $top $fl
    dfflibmap -liberty $TT
    abc -D 4000 -liberty $TT -script \"+strash;map {D};topo;buffer -N 8;upsize {D};dnsize {D}\"
    opt_clean
    tee -o $d/stat.txt stat -liberty $TT
    write_verilog -noattr $d/netlist.v"
  : > $d/sta.txt
  for lib in $TT $SS; do
    cat > $d/sta.tcl <<EOF
read_liberty $lib
read_verilog $d/netlist.v
link_design $top
proc setup_clocks {p} { foreach c {$clocks} { create_clock -name \$c -period \$p [get_ports \$c] } }
setup_clocks 2.0
set_input_transition 0.15 [all_inputs]
set_load 0.02 [all_outputs]
$exc
puts "== corner [file tail $lib]"
# smallest clock period with no setup violation (bisection; honours multicycle exceptions)
set lo 0.5; set hi 64.0
while {\$hi - \$lo > 0.02} { set m [expr (\$lo + \$hi) / 2.0]; setup_clocks \$m
  if {[sta::worst_slack_cmd max] >= 0} { set hi \$m } else { set lo \$m } }
puts [format "period_min = %.2f ns fmax = %.1f MHz" \$hi [expr 1000.0 / \$hi]]
setup_clocks \$hi
report_checks -path_delay max -format full -digits 3
catch { set icg [get_cells -quiet -filter "ref_name =~ *icgtp*" *]; puts "-- clock-gate enable checks ([llength \$icg] ICG cells)"; if {[llength \$icg]} { report_checks -to [get_pins -of_objects \$icg -filter "direction == input"] -path_delay min_max -digits 3 } }
catch { puts "-- output ports"; report_checks -to [all_outputs] -path_delay max -digits 3 }
EOF
    sta -no_init -exit $d/sta.tcl >> $d/sta.txt 2>&1 || true
  done
}
# pnr <top> <clocks> <exceptions>: placement-based estimate with OpenROAD (floorplan at 40 %
# utilization, global + detailed placement, Metal2/Metal3 wire RC, repair_design and
# repair_timing toward a 7.5 ns clock), then the same min-period bisection. Clocks stay
# ideal (no clock tree): this adds wiring, buffering and gate/flop sizing that the
# synth-only numbers lack, not CTS skew/latency or routed parasitics.
pnr() {
  top=$1; clocks=$2; exc=$3; d=/out/$top
  for lib in $TT $SS; do
    cat > $d/pnr.tcl <<EOF
set P /pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0
read_lef \$P/techlef/gf180mcu_fd_sc_mcu7t5v0__nom.tlef
read_lef \$P/lef/gf180mcu_fd_sc_mcu7t5v0.lef
read_liberty $lib
read_verilog $d/netlist.v
link_design $top
proc setup_clocks {p} { foreach c {$clocks} { create_clock -name \$c -period \$p [get_ports \$c] } }
setup_clocks 8.0
set_input_transition 0.15 [all_inputs]
set_load 0.02 [all_outputs]
$exc
setup_clocks 7.5   ;# repair target with margin below the 8 ns (125 MHz) requirement
initialize_floorplan -utilization 40 -aspect_ratio 1 -core_space 5 -site GF018hv5v_mcu_sc7
make_tracks
place_pins -hor_layers Metal3 -ver_layers Metal2
global_placement -density 0.6
set_wire_rc -signal -layer Metal2
set_wire_rc -clock -layer Metal3
estimate_parasitics -placement
repair_design
detailed_placement
estimate_parasitics -placement
repair_timing -setup -skip_pin_swap
detailed_placement
estimate_parasitics -placement
puts "== pnr corner [file tail $lib]"
set lo 0.5; set hi 64.0
while {\$hi - \$lo > 0.02} { set m [expr (\$lo + \$hi) / 2.0]; setup_clocks \$m
  if {[sta::worst_slack_cmd max] >= 0} { set hi \$m } else { set lo \$m } }
puts [format "pnr_period_min = %.2f ns fmax = %.1f MHz" \$hi [expr 1000.0 / \$hi]]
setup_clocks \$hi
report_checks -path_delay max -digits 3
catch { set icg [get_cells -quiet -filter "ref_name =~ *icgtp*" *]; puts "-- clock-gate enable checks ([llength \$icg] ICG cells)"; if {[llength \$icg]} { report_checks -to [get_pins -of_objects \$icg -filter "direction == input"] -path_delay min_max -digits 3 } }
catch { puts "-- output ports"; report_checks -to [all_outputs] -path_delay max -digits 3 }
report_design_area
EOF
    (cd /tmp && openroad -no_init -exit $d/pnr.tcl) > $d/pnr_$(basename $lib .lib).log 2>&1 || true
  done
}
P=/src/rtl/pt_pattern.sv; [ -f /pattern_src.sv ] && P=/pattern_src.sv
# The generator/checker core registers (and the RX pair register d2/v2) only update on
# their clock enable, at most every other clock, so paths between them get a two-cycle
# exception; the enables (ph, t), the TX word mux and the RX pair assembly stay
# single-cycle. Flattened netlists keep register net names (\<inst>.gen.h etc.), which
# select the core flops.
mc() { # <net glob of the core registers> [extra source net globs]
  echo "set core [get_cells -quiet -filter \"ref_name =~ *dff*\" -of_objects [get_pins -quiet -of_objects [get_nets -quiet {$1}] -filter \"direction == output\"]]
set src \$core
foreach g {$2} { set src [concat \$src [get_cells -quiet -filter \"ref_name =~ *dff*\" -of_objects [get_pins -quiet -of_objects [get_nets -quiet \$g] -filter \"direction == output\"]]] }
puts \"multicycle 2: [llength \$core] core flops, [llength \$src] sources\"
set_multicycle_path -setup 2 -from \$src -to \$core
set_multicycle_path -hold 1 -from \$src -to \$core"
}
if [ -z "$ONLY" ] || [ "$ONLY" = pattern ]; then
if grep -q "module pt_pattern_tx" $P; then
  # TX output: serializer-load constraint integration/pt_wired_tx.sdc (falling-edge capture).
  SDC_TX="set wtx_clk clk; set wtx_data {word*}; source /src/integration/pt_wired_tx.sdc"
  synth pt_pattern_tx "$P" "clk" 1 "" "$(mc "gen.*")
$SDC_TX"
  synth pt_pattern_rx "$P" "clk" 1 "" "$(mc "chk.*" "d2* v2")"
  synth pt_pattern_tx_tied "$P /out/wrappers.sv" "clk" 1 "" "$(mc "gb.gen.*")
$SDC_TX"
  synth pt_pattern_rx_tied "$P /out/wrappers.sv" "clk" 1 "" "$(mc "gb.chk.*" "gb.d2* gb.v2")"
  synth pt_pattern_gen20 "$P" "clk" 1 "chparam -set W 20 pt_pattern_gen; rename pt_pattern_gen pt_pattern_gen20" ""
  synth pt_pattern_check20 "$P" "clk" 1 "chparam -set W 20 pt_pattern_check; rename pt_pattern_check pt_pattern_check20" ""
  pnr pt_pattern_tx "clk" "$(mc "gen.*")
$SDC_TX"
  pnr pt_pattern_rx "clk" "$(mc "chk.*" "d2* v2")"
  pnr pt_pattern_tx_tied "clk" "$(mc "gb.gen.*")
$SDC_TX"
  pnr pt_pattern_rx_tied "clk" "$(mc "gb.chk.*" "gb.d2* gb.v2")"
else   # earlier single-word revision (before/after table)
  synth pt_pattern_gen "$P" "clk"
  synth pt_pattern_check "$P" "clk"
  pnr pt_pattern_gen "clk" ""
  pnr pt_pattern_check "clk" ""
fi
fi
if [ -z "$ONLY" ] || [ "$ONLY" = clocktree ]; then
C=/src/rtl/pt_clocktree_slow.sv
synth pt_ct_word "$C" "wclk"
synth pt_ct_detect_div "$C" "clk"
ASYNC="set_clock_groups -asynchronous -group wclk -group ref_clk -group det_clk_in"
synth pt_clocktree_slow "$C" "wclk ref_clk det_clk_in" 1 "" "$ASYNC"
pnr pt_ct_word "wclk" ""
pnr pt_clocktree_slow "wclk ref_clk det_clk_in" "$ASYNC"
fi
'
cat "$OUT/image.txt" "$OUT/yosys_version.txt"
set +o pipefail
for d in "$OUT"/*/; do
  t=$(basename "$d")
  cells=$(grep -E "^ +[0-9]+ +[0-9.E+]+ +cells$" "$d/stat.txt" | awk '{print $1}')
  area=$(grep -oE "Chip area for module .*: [0-9.]+" "$d/stat.txt" | grep -oE "[0-9.]+$")
  seq=$(grep -E "gf180mcu_fd_sc_mcu7t5v0__(dff|sdff|lat|icg)" "$d/stat.txt" | awk '{s+=$1} END {print s+0}')
  fmax=$(grep -E "^== corner|period_min" "$d/sta.txt" | sed -E 's/== corner gf180mcu_fd_sc_mcu7t5v0__//; s/.lib//' | tr '\n' ' ')
  pn=$(cat "$d"/pnr_*.log 2>/dev/null | grep -E "^== pnr corner|pnr_period_min" | sed -E 's/== pnr corner gf180mcu_fd_sc_mcu7t5v0__//; s/.lib//' | tr '\n' ' ')
  echo "$t: cells=$cells seq=$seq area_um2=$area | synth: $fmax${pn:+| placed+repaired: $pn}"
done | tee "$OUT/summary.txt"
