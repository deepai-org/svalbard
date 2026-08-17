#!/bin/sh
set -eu

test "$(librelane --bare-version)" = "3.0.5"
test "$(sha256sum /pdk/gf180mcuD/libs.tech/librelane/config.tcl | cut -d ' ' -f 1)" = \
  "dfd52190eb043b290273ff7a4dabb2b7d582a5a30c374409679aa4d2ecc2b02d"
test "$(sha256sum /pdk/gf180mcuD/libs.tech/librelane/gf180mcu_fd_io/config.tcl | cut -d ' ' -f 1)" = \
  "ebc2c799800f0950668f295e769d36c78149383e3431a4b0f4672bd0f798563e"

mkdir -p /work/home /work/tmp /work/design
cp /src/config.yaml /src/constraints.sdc /src/counter.v /src/pin_order.cfg /work/design/
cd /work/design
librelane \
  --manual-pdk --pdk-root /pdk \
  -p gf180mcuD -s gf180mcu_fd_sc_mcu7t5v0 \
  -j 2 --condensed --hide-progress-bar --run-tag CANARY \
  config.yaml > /work/librelane.log 2>&1

final=/work/design/runs/CANARY/final
iverilog -g2012 -DFUNCTIONAL -DUSE_POWER_PINS \
  -s counter_gate_tb -o /work/counter_gate_sim \
  /pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/verilog/primitives.v \
  /pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/verilog/gf180mcu_fd_sc_mcu7t5v0.v \
  "$final/pnl/counter.pnl.v" /src/counter_gate_tb.v
vvp /work/counter_gate_sim > /work/gate-simulation.log

DFT_INPUT_ODB=/work/design/runs/CANARY/32-openroad-repairdesignpostgpl/counter.odb \
  DFT_INPUT_SDC=/work/design/constraints.sdc \
  DFT_NETLIST=/work/counter.scan-raw.v \
  openroad -no_init -no_splash /src/dft_probe.tcl > /work/dft-probe.log 2>&1
python3 /src/normalize_scan_netlist.py \
  /work/counter.scan-raw.v /work/counter.scan-stitched.v
python3 /src/scan_to_bench.py \
  /work/counter.scan-stitched.v /work/counter.atpg.bench
yosys -ql /work/scan-equivalence.log /src/scan_equiv.ys
iverilog -g2012 -DFUNCTIONAL \
  -s counter_scan_tb -o /work/counter_scan_sim \
  /pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/verilog/primitives.v \
  /pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/verilog/gf180mcu_fd_sc_mcu7t5v0.v \
  /work/counter.scan-stitched.v /src/counter_scan_tb.v
vvp /work/counter_scan_sim > /work/scan-simulation.log
python3 /src/stuck_at.py /work/counter.scan-stitched.v /work/stuck-at.json
python3 /src/transition_fault.py \
  /work/counter.scan-stitched.v /work/transition-fault.json

mkdir /work/scan_design
cp /src/scan_config.yaml /src/constraints.sdc /src/scan_pin_order.cfg /work/scan_design/
cp /work/counter.scan-stitched.v /work/scan_design/counter.v
mv /work/scan_design/scan_pin_order.cfg /work/scan_design/pin_order.cfg
cd /work/scan_design
librelane \
  --manual-pdk --pdk-root /pdk \
  -p gf180mcuD -s gf180mcu_fd_sc_mcu7t5v0 \
  -j 2 --condensed --hide-progress-bar --run-tag SCAN \
  scan_config.yaml > /work/librelane-scan.log 2>&1

scan_final=/work/scan_design/runs/SCAN/final
iverilog -g2012 -DFUNCTIONAL -DUSE_POWER_PINS \
  -s counter_scan_tb -o /work/counter_scan_physical_sim \
  /pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/verilog/primitives.v \
  /pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/verilog/gf180mcu_fd_sc_mcu7t5v0.v \
  "$scan_final/pnl/counter.pnl.v" /src/counter_scan_tb.v
vvp /work/counter_scan_physical_sim > /work/scan-physical-simulation.log

echo 'digital-pnr-smoke: physical stages PASS'
