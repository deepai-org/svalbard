#!/usr/bin/env bash
set -euo pipefail
. /src/lane/capture_stack.sh
prepare_capture_stack

run_rx_bias() {
  local name="$1" rx_bias="$2"
  python3 /src/lane/run_capture_stress_case.py "${capture_args[@]}" \
    --jobs 1 --offset-ps 0 --allow-fail --case-id "$name" \
    --pattern prbs7 --bit-count 40 --simulation-timeout-s 900 \
    --channel-series-ohm-per-leg 7 --channel-shunt-cap-f 1.25e-12 \
    --tx-clock-jitter-ps 30 --tx-clock-duty 0.47 \
    --vdd-ripple-mv 20 --vdd-ripple-hz 100e6 \
    --mos-corner ss --res-corner res_ss --vdd 2.97 --temperature 125 \
    --tx-bias 1.20 --rx-bias "$rx_bias" \
    --work "/work/rx-bias-${name}" --output "/work/rx-bias-${name}.json"
}

run_rx_bias rx11 1.10 & p1=$!
run_rx_bias rx12 1.20 & p2=$!
run_rx_bias rx13 1.30 & p3=$!
run_rx_bias rx14 1.40 & p4=$!
wait "$p1" "$p2" "$p3" "$p4"

python3 /src/lane/merge_capture_rx_bias_sweep.py \
  --case /work/rx-bias-rx11.json --case /work/rx-bias-rx12.json \
  --case /work/rx-bias-rx13.json --case /work/rx-bias-rx14.json \
  --output /work/capture-rx-bias-sweep.json
