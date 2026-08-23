#!/usr/bin/env bash
set -euo pipefail

. /src/lane/capture_stack.sh
prepare_capture_stack

common_args=(
  --source /src --jobs 1 --serial-rate-gbd 2.5
  --tx-pex /src/serializer/integrated_serializer_tx.pex.spice
  --term-pex /src/lane/termination_2p5.pex.spice
  --rx-pex /src/lane/rx_2p5.pex.spice
  --sampler-pex /src/lane/sampler_2p5.pex.spice
  --base-physical /src/lane/physical_2p5_result.json
  --restorer-pex /src/data_restorer/data_restorer_2p5.pex.spice
  --restorer-physical /src/data_restorer/physical_2p5_result.json
  --restorer-cell cml_data_restorer_2p5_pex
  --frontend-pex /work/cml_to_cmos-pex/cml_to_cmos.pex.spice
  --deserializer-pex /work/deserializer_split_capture-pex/deserializer_split_capture.pex.spice
  --deserializer-physical /work/capture-physical.json
  --pattern prbs7 --bit-count 24 --simulation-timeout-s 900
  --channel-series-ohm-per-leg 6 --channel-shunt-cap-f 1e-12
  --tx-clock-jitter-ps 30 --tx-clock-duty 0.47
  --vdd-ripple-mv 20 --vdd-ripple-hz 100e6
  --restorer-mode data --tx-load-code 2 --capture-width-ps 380
)

run_case() {
  local name="$1"
  shift
  python3 /src/lane/run_capture_stress_case.py "${common_args[@]}" \
    --case-id "$name" "$@" --work "/work/capture-2p5-${name}" \
    --output "/work/capture-2p5-${name}.json"
}

run_case ff_cold --mos-corner ff --res-corner res_ff \
  --vdd 3.63 --temperature -40 --tx-bias 1.1 --rx-bias 1.2 \
  --restorer-bias 1.2 --sampler-bias 1.1 --ac-initial-v 1.070 \
  --sampler-phase 67.5 --latency-ui 0 --rx-window-start-ps 50 \
  --offset-ps 100 & p1=$!
run_case ff_hot --mos-corner ff --res-corner res_ss \
  --vdd 2.97 --temperature 125 --tx-bias 1.6 --rx-bias 1.2 \
  --restorer-bias 1.2 --sampler-bias 0.9 --ac-initial-v 0.300 \
  --sampler-phase 16.875 --latency-ui 0 --rx-window-start-ps 100 \
  --offset-ps 300 & p2=$!
wait "$p1" "$p2"
