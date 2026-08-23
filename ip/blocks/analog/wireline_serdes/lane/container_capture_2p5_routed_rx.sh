#!/usr/bin/env bash
set -euo pipefail

common_args=(
  --source /src --jobs 1 --serial-rate-gbd 2.5
  --tx-pex /src/serializer/integrated_serializer_tx_2p5.pex.spice
  --tx-physical /src/serializer/integrated_tx_2p5_physical_result.json
  --term-pex /src/lane/termination_2p5.pex.spice
  --term-physical /src/lane/physical_2p5_result.json
  --rx-spine-pex /src/lane_rx_spine/lane_rx_spine.pex.spice
  --rx-spine-physical /src/lane_rx_spine/physical_result.json
  --restorer-cell cml_data_restorer_2p5_calibrated_pex
  --frontend-pex /src/lane/capture_2p5_calibrated_frontend.pex.spice
  --frontend-physical /src/lane/capture_2p5_calibrated_frontend_physical_result.json
  --deserializer-pex /src/lane/capture_2p5_calibrated_deserializer.pex.spice
  --deserializer-physical /src/lane/capture_2p5_calibrated_physical_result.json
  --pattern prbs7 --bit-count 24 --simulation-timeout-s 900
  --channel-series-ohm-per-leg 6 --channel-shunt-cap-f 1e-12
  --tx-clock-jitter-ps 30 --tx-clock-duty 0.47
  --vdd-ripple-mv 20 --vdd-ripple-hz 100e6
  --restorer-mode data --capture-width-ps 380 --allow-fail
)

run_case() {
  local name="$1"
  shift
  python3 /src/lane/run_capture_stress_case.py "${common_args[@]}" \
    --case-id "$name" "$@" --work "/work/capture-2p5-routed-${name}" \
    --output "/work/capture-2p5-routed-${name}.json"
}

run_case tt --tx-load-code 2 --tx-bias 1.5 --ac-initial-v 0.435 \
  --rx-bias 1.3 --restorer-bias 1.3 --sampler-bias 1.1 \
  --sampler-phase 22.5 --latency-ui 0 --rx-window-start-ps 100 \
  --offset-ps 100 & p1=$!
run_case ff_cold --mos-corner ff --res-corner res_ff \
  --vdd 3.63 --temperature -40 --tx-load-code 2 --tx-bias 0.96 \
  --ac-initial-v 0.850 --rx-bias 1.2 --restorer-bias 1.2 \
  --sampler-bias 1.1 --sampler-phase 67.5 --latency-ui 0 \
  --rx-window-start-ps 50 --offset-ps 100 & p2=$!
wait "$p1" "$p2"

run_case ff_hot --mos-corner ff --res-corner res_ss \
  --vdd 2.97 --temperature 125 --tx-load-code 2 --tx-bias 1.6 \
  --ac-initial-v 0.300 --rx-bias 1.2 --restorer-bias 1.2 \
  --sampler-bias 0.9 --sampler-phase 16.875 --latency-ui 0 \
  --rx-window-start-ps 100 --offset-ps 300 & p3=$!
run_case ss_hot --mos-corner ss --res-corner res_ff \
  --vdd 2.97 --temperature 125 --tx-load-code 4 --tx-bias 1.7 \
  --ac-initial-v 1.100 --rx-bias 1.5 --restorer-bias 1.5 \
  --sampler-bias 1.2 --sampler-phase 135 --latency-ui 1 \
  --rx-window-start-ps 250 --frontend-sense-width-ps 550 \
  --capture-delay-ps 400 --offset-ps 600 & p4=$!
wait "$p3" "$p4"

run_case ss_passive --mos-corner ss --res-corner res_ss \
  --vdd 2.97 --temperature 125 --tx-load-code 4 --tx-bias 1.7 \
  --ac-initial-v 1.100 --rx-bias 1.5 --restorer-bias 1.5 \
  --sampler-bias 1.2 --sampler-phase 135 --latency-ui 1 \
  --rx-window-start-ps 250 --frontend-sense-width-ps 550 \
  --capture-delay-ps 400 --offset-ps 600

python3 /src/lane/merge_capture_2p5_calibrated.py \
  --case /work/capture-2p5-routed-tt.json \
  --case /work/capture-2p5-routed-ff_cold.json \
  --case /work/capture-2p5-routed-ff_hot.json \
  --case /work/capture-2p5-routed-ss_hot.json \
  --case /work/capture-2p5-routed-ss_passive.json \
  --claim routed_rx_parent_extracted_2p5_gts_combined_stress_pvt \
  --physical-composition routed_rx_restorer_sampler_parent \
  --output /work/capture-2p5-routed.json
