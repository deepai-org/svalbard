#!/usr/bin/env bash
set -euo pipefail

. /src/lane/capture_stack.sh
prepare_capture_stack

common_args=(
  --source /src --jobs 1 --serial-rate-gbd 2.5 \
  --tx-pex /src/serializer/integrated_serializer_tx.pex.spice \
  --term-pex /src/lane/termination_2p5.pex.spice \
  --rx-pex /src/lane/rx_2p5.pex.spice \
  --sampler-pex /src/lane/sampler_2p5.pex.spice \
  --base-physical /src/lane/physical_2p5_result.json \
  --restorer-pex /src/data_restorer/data_restorer_2p5.pex.spice \
  --restorer-physical /src/data_restorer/physical_2p5_result.json \
  --restorer-cell cml_data_restorer_2p5_pex \
  --frontend-pex /work/cml_to_cmos-pex/cml_to_cmos.pex.spice \
  --deserializer-pex /work/deserializer_split_capture-pex/deserializer_split_capture.pex.spice \
  --deserializer-physical /work/capture-physical.json \
  --pattern prbs7 --bit-count 24 --simulation-timeout-s 900 \
  --restorer-mode data --sampler-phase 22.5 --latency-ui 0 \
  --rx-window-start-ps 100 --tx-bias 1.2 --rx-bias 1.3 \
  --restorer-bias 1.3 --sampler-bias 1.1 --ac-initial-v 0.950 \
  --offset-ps 100 --allow-fail
)

run_case() {
  local name="$1"
  shift
  python3 /src/lane/run_capture_stress_case.py "${common_args[@]}" \
    --case-id "$name" "$@" \
    --work "/work/capture-2p5-${name}" \
    --output "/work/capture-2p5-${name}.json"
}

stress_args=(
  --channel-series-ohm-per-leg 6 --channel-shunt-cap-f 1e-12
  --tx-clock-jitter-ps 30 --tx-clock-duty 0.47
  --vdd-ripple-mv 20 --vdd-ripple-hz 100e6
)

run_case tt "${stress_args[@]}" --tx-bias 1.5 --ac-initial-v 0.435 \
  --sampler-phase 22.5 --latency-ui 0 --rx-window-start-ps 100 & p1=$!
run_case ff_cold "${stress_args[@]}" --mos-corner ff --res-corner res_ff \
  --vdd 3.63 --temperature -40 --tx-bias 1.4 --rx-bias 1.2 \
  --restorer-bias 1.2 --sampler-bias 1.1 --ac-initial-v 0.565 \
  --sampler-phase 67.5 --latency-ui 0 --rx-window-start-ps 0 & p2=$!
run_case ff_hot "${stress_args[@]}" --mos-corner ff --res-corner res_ss \
  --vdd 2.97 --temperature 125 --tx-bias 1.5 --rx-bias 1.2 \
  --restorer-bias 1.2 --sampler-bias 0.9 --ac-initial-v 0.115 \
  --sampler-phase 16.875 --latency-ui 0 --rx-window-start-ps 100 & p3=$!
run_case ss_hot "${stress_args[@]}" --mos-corner ss --res-corner res_ff \
  --vdd 2.97 --temperature 125 --tx-bias 1.6 --rx-bias 1.5 \
  --restorer-bias 1.5 --sampler-bias 1.2 --ac-initial-v 0.635 \
  --sampler-phase 135 --latency-ui 1 --rx-window-start-ps 250 & p4=$!
run_case ss_passive "${stress_args[@]}" --mos-corner ss --res-corner res_ss \
  --vdd 2.97 --temperature 125 --tx-bias 1.6 --rx-bias 1.5 \
  --restorer-bias 1.5 --sampler-bias 1.2 --ac-initial-v 0.592 \
  --sampler-phase 135 --latency-ui 1 --rx-window-start-ps 250 & p5=$!
wait "$p1" "$p2" "$p3" "$p4" "$p5"

python3 /src/lane/merge_capture_2p5_precal.py \
  --case /work/capture-2p5-tt.json --case /work/capture-2p5-ff_cold.json \
  --case /work/capture-2p5-ff_hot.json --case /work/capture-2p5-ss_hot.json \
  --case /work/capture-2p5-ss_passive.json \
  --output /work/capture-2p5-precal.json
