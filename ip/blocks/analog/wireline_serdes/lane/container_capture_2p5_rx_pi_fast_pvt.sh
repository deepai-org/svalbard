#!/usr/bin/env bash
set -euo pipefail

common_args=(
  --source /src --jobs 1 --serial-rate-gbd 2.5
  --tx-pex /src/serializer/integrated_serializer_tx_2p5.pex.spice
  --tx-physical /src/serializer/integrated_tx_2p5_physical_result.json
  --rx-pi-capture-parent-pex
    /src/lane_rx_pi_capture/lane_rx_pi_capture_fast.pex.spice
  --rx-pi-capture-parent-physical
    /src/lane_rx_pi_capture/fast_physical_result.json
  --pattern prbs7 --bit-count 24 --simulation-timeout-s 900
  --channel-series-ohm-per-leg 6 --channel-shunt-cap-f 1e-12
  --tx-clock-jitter-ps 30 --tx-clock-duty 0.47
  --vdd-ripple-mv 20 --vdd-ripple-hz 100e6
  --restorer-mode data --capture-width-ps 380 --capture-delay-ps 550
  --capture-output-delay-ps 1050 --frontend-sense-width-ps 550
  --pi-control-a 1.15 --pi-control-b 1.15 --pi-buffer-bias 1.15
  --clock-restorer-bias 1.15 --pi-invert --allow-fail
)

run_case() {
  local name="$1"
  shift
  python3 /src/lane/run_capture_stress_case.py "${common_args[@]}" \
    --case-id "$name" "$@" --work "/work/capture-2p5-rx-pi-fast-${name}" \
    --output "/work/capture-2p5-rx-pi-fast-${name}.json"
}

run_case tt --tx-load-code 2 --tx-bias 1.5 --ac-initial-v 0.435 \
  --rx-bias 1.3 --restorer-bias 1.3 --sampler-bias 1.3 \
  --sampler-phase 22.5 --latency-ui 0 --frontend-latency-ui 2 \
  --frontend-write-latency-ui 0 --capture-latency-ui 0 \
  --rx-window-start-ps 100 --offset-ps 300 & p1=$!
run_case ff_cold --mos-corner ff --res-corner res_ff \
  --vdd 3.63 --temperature -40 --tx-load-code 2 --tx-bias 0.96 \
  --ac-initial-v 0.850 --rx-bias 1.2 --restorer-bias 1.2 \
  --sampler-bias 1.3 --sampler-phase 45 --latency-ui 0 \
  --frontend-latency-ui 2 --frontend-write-latency-ui 0 \
  --capture-latency-ui 0 --rx-window-start-ps 50 --offset-ps 100 & p2=$!
wait "$p1" "$p2"

run_case ff_hot --mos-corner ff --res-corner res_ss \
  --vdd 2.97 --temperature 125 --tx-load-code 2 --tx-bias 1.6 \
  --ac-initial-v 0.300 --rx-bias 1.2 --restorer-bias 1.2 \
  --sampler-bias 0.9 --sampler-phase 16.875 --latency-ui 0 \
  --frontend-latency-ui 2 --frontend-write-latency-ui 0 \
  --capture-latency-ui 0 --rx-window-start-ps 150 \
  --odd-frontend-skew-ps -150 --pi-input-phase-deg 5 \
  --offset-ps 300 & p3=$!
run_case ss_hot --mos-corner ss --res-corner res_ff \
  --vdd 2.97 --temperature 125 --tx-load-code 4 --tx-bias 1.7 \
  --ac-initial-v 1.100 --rx-bias 1.5 --restorer-bias 1.5 \
  --sampler-bias 1.2 --sampler-phase 135 --latency-ui 1 \
  --frontend-latency-ui 1 --frontend-write-latency-ui 1 \
  --capture-latency-ui 1 --rx-window-start-ps 250 \
  --clock-restorer-bias 1.3 --pi-input-phase-deg 135 \
  --even-frontend-skew-ps 250 --capture-delay-ps 400 \
  --offset-ps 600 & p4=$!
wait "$p3" "$p4"

run_case ss_passive --mos-corner ss --res-corner res_ss \
  --vdd 2.97 --temperature 125 --tx-load-code 4 --tx-bias 1.7 \
  --ac-initial-v 1.100 --rx-bias 1.5 --restorer-bias 1.5 \
  --sampler-bias 1.2 --sampler-phase 135 --latency-ui 1 \
  --frontend-latency-ui 1 --frontend-write-latency-ui 1 \
  --capture-latency-ui 1 --rx-window-start-ps 250 \
  --clock-restorer-bias 1.3 --pi-input-phase-deg 135 \
  --even-frontend-skew-ps 250 --capture-delay-ps 400 \
  --offset-ps 600

python3 /src/lane/merge_capture_2p5_calibrated.py \
  --case /work/capture-2p5-rx-pi-fast-tt.json \
  --case /work/capture-2p5-rx-pi-fast-ff_cold.json \
  --case /work/capture-2p5-rx-pi-fast-ff_hot.json \
  --case /work/capture-2p5-rx-pi-fast-ss_hot.json \
  --case /work/capture-2p5-rx-pi-fast-ss_passive.json \
  --claim routed_pi_rx_fast_capture_parent_extracted_2p5_gts_combined_stress_pvt \
  --physical-composition routed_phase_interpolator_rx_fast_dual_capture_parent \
  --output /work/capture-2p5-rx-pi-fast.json || true

python3 /src/lane_rx_pi_capture/check_fast_checkpoint.py \
  --aggregate /work/capture-2p5-rx-pi-fast.json \
  --physical /src/lane_rx_pi_capture/fast_physical_result.json \
  --pex /src/lane_rx_pi_capture/lane_rx_pi_capture_fast.pex.spice \
  --runner /src/lane/run_capture_stress_case.py \
  --merger /src/lane/merge_capture_2p5_calibrated.py \
  --testbench /src/lane/lane_tb.spice.in \
  --render /src/lane_rx_pi_capture/fast_layout.png \
  --top-schematic /src/lane_rx_pi_capture/lane_rx_pi_capture_fast.spice \
  --capture-schematic /src/lane_rx_capture/lane_rx_capture_fast.spice \
  --frontend-schematic /src/lane_rx_frontend/lane_rx_frontend_fast.spice \
  --converter-schematic /src/cdr/cml_to_cmos/cml_to_cmos_fast.spice \
  --top-layout /src/lane_rx_pi_capture/layout.tcl \
  --capture-layout /src/lane_rx_capture/layout.tcl \
  --frontend-layout /src/lane_rx_frontend/layout_fast.tcl \
  --frontend-base-layout /src/lane_rx_frontend/layout.tcl \
  --converter-layout /src/cdr/cml_to_cmos/layout.tcl \
  --case /work/capture-2p5-rx-pi-fast-tt.json \
  --case /work/capture-2p5-rx-pi-fast-ff_cold.json \
  --case /work/capture-2p5-rx-pi-fast-ff_hot.json \
  --case /work/capture-2p5-rx-pi-fast-ss_hot.json \
  --case /work/capture-2p5-rx-pi-fast-ss_passive.json
