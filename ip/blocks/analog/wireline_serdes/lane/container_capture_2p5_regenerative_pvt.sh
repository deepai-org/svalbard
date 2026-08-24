#!/usr/bin/env bash
set -euo pipefail

common_args=(
  --source /src --jobs 1 --serial-rate-gbd 2.5
  --tx-pex /src/serializer/integrated_serializer_tx_2p5.pex.spice
  --tx-physical /src/serializer/integrated_tx_2p5_physical_result.json
  --rx-regenerative-capture-parent-pex
    /src/lane_rx_regenerative_capture/lane_rx_regenerative_capture.pex.spice
  --rx-regenerative-capture-parent-physical
    /src/lane_rx_regenerative_capture/physical_result.json
  --pattern prbs7 --bit-count 24 --simulation-timeout-s 900
  --channel-series-ohm-per-leg 6 --channel-shunt-cap-f 1e-12
  --tx-clock-jitter-ps 30 --tx-clock-duty 0.47
  --vdd-ripple-mv 20 --vdd-ripple-hz 100e6
  --restorer-mode none --capture-width-ps 150 --capture-delay-ps 200
  --capture-output-delay-ps 1050 --frontend-sense-width-ps 550
  --frontend-tail-boost --latency-ui 0 --sampler-latency-ui 0
  --frontend-write-latency-ui 2
  --capture-latency-ui 2 --offset-ps 100 --allow-fail
)

run_case() {
  local name="$1"
  shift
  python3 /src/lane/run_capture_stress_case.py "${common_args[@]}" \
    --case-id "$name" "$@" --work "/work/regenerative-${name}" \
    --output "/work/regenerative-${name}.json"
}

run_case tt --tx-load-code 2 --tx-bias 1.5 --ac-initial-v 0.435 \
  --rx-bias 1.3 --frontend-latency-ui 2 & p1=$!
run_case ff_cold --mos-corner ff --res-corner res_ff --vdd 3.63 \
  --temperature -40 --tx-load-code 2 --tx-bias 0.96 --ac-initial-v 0.850 \
  --rx-bias 1.2 --frontend-latency-ui 0 & p2=$!
wait "$p1" "$p2"

run_case ff_hot --mos-corner ff --res-corner res_ss --vdd 2.97 \
  --temperature 125 --tx-load-code 2 --tx-bias 1.6 --ac-initial-v 0.300 \
  --rx-bias 1.2 --frontend-latency-ui 2 & p3=$!
run_case ss_hot --mos-corner ss --res-corner res_ff --vdd 2.97 \
  --temperature 125 --tx-load-code 4 --tx-bias 1.7 --ac-initial-v 1.100 \
  --rx-bias 1.5 --frontend-latency-ui 2 & p4=$!
wait "$p3" "$p4"

run_case ss_passive --mos-corner ss --res-corner res_ss --vdd 2.97 \
  --temperature 125 --tx-load-code 4 --tx-bias 1.7 --ac-initial-v 1.100 \
  --rx-bias 1.5 --frontend-latency-ui 2

python3 /src/lane/merge_capture_2p5_regenerative.py \
  --case /work/regenerative-tt.json \
  --case /work/regenerative-ff_cold.json \
  --case /work/regenerative-ff_hot.json \
  --case /work/regenerative-ss_hot.json \
  --case /work/regenerative-ss_passive.json \
  --output /work/regenerative-pvt.json
