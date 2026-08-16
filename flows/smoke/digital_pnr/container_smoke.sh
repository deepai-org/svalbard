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

FINAL_DIR="$final" DFT_NETLIST=/work/counter.scan-replaced.v \
  openroad -no_init -no_splash /src/dft_probe.tcl > /work/dft-probe.log 2>&1

python3 /src/check_results.py \
  "$final/metrics.json" "$final" /work/design/runs/CANARY/warning.log \
  /work/gate-simulation.log /work/dft-probe.log \
  /work/counter.scan-replaced.v /work/result.json
echo 'digital-pnr-smoke: full core flow PASS'
