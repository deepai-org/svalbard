#!/usr/bin/env bash
set -euo pipefail

bash /src/serializer/container_integrated_tx_2p5_physical.sh
. /src/lane/capture_stack.sh
prepare_capture_stack
prepare_data_restorer_2p5_calibrated

common_args=(
  --source /src --jobs 1 --serial-rate-gbd 2.5
  --tx-pex /work/integrated-serializer-tx-2p5.pex.spice
  --tx-physical /work/integrated-tx-2p5-physical-result.json
  --term-pex /src/lane/termination_2p5.pex.spice
  --rx-pex /src/lane/rx_2p5.pex.spice
  --sampler-pex /src/lane/sampler_2p5.pex.spice
  --base-physical /src/lane/physical_2p5_result.json
  --restorer-pex /work/cml_data_restorer_2p5_calibrated-pex/cml_data_restorer_2p5_calibrated.pex.spice
  --restorer-physical /work/data-restorer-2p5-calibrated-physical.json
  --restorer-cell cml_data_restorer_2p5_calibrated_pex
  --frontend-pex /work/cml_to_cmos-pex/cml_to_cmos.pex.spice
  --frontend-physical /work/cml-to-cmos-physical.json
  --deserializer-pex /work/deserializer_split_capture-pex/deserializer_split_capture.pex.spice
  --deserializer-physical /work/capture-physical.json
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
    --case-id "$name" "$@" --work "/work/capture-2p5-${name}" \
    --output "/work/capture-2p5-${name}.json"
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
wait "$p1" "$p2" "$p3" "$p4"

run_case ss_passive --mos-corner ss --res-corner res_ss \
  --vdd 2.97 --temperature 125 --tx-load-code 4 --tx-bias 1.7 \
  --ac-initial-v 1.100 --rx-bias 1.5 --restorer-bias 1.5 \
  --sampler-bias 1.2 --sampler-phase 135 --latency-ui 1 \
  --rx-window-start-ps 250 --frontend-sense-width-ps 550 \
  --capture-delay-ps 400 --offset-ps 600

python3 /src/lane/merge_capture_2p5_calibrated.py \
  --case /work/capture-2p5-tt.json --case /work/capture-2p5-ff_cold.json \
  --case /work/capture-2p5-ff_hot.json --case /work/capture-2p5-ss_hot.json \
  --case /work/capture-2p5-ss_passive.json \
  --output /work/capture-2p5-calibrated.json
