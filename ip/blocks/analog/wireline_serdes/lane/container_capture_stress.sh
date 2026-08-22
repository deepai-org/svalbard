#!/usr/bin/env bash
set -euo pipefail
. /src/lane/capture_stack.sh
prepare_capture_stack

run_stress() {
  local name="$1" resistance="$2" capacitance="$3" jitter="$4" duty="$5"
  python3 /src/lane/run_capture_stress_case.py "${capture_args[@]}" --jobs 1 --offset-ps 0 \
    --pattern prbs7 --bit-count 64 --case-id "$name" --simulation-timeout-s 900 \
    --channel-series-ohm-per-leg "$resistance" --channel-shunt-cap-f "$capacitance" \
    --tx-clock-jitter-ps "$jitter" --tx-clock-duty "$duty" \
    --work "/work/stress-${name}" --output "/work/stress-${name}.json"
}

run_stress prbs_base 0 0 0 0.50 & p1=$!
run_stress channel 6 1e-12 0 0.50 & p2=$!
run_stress timing 0 0 40 0.47 & p3=$!
run_stress combined 6 1e-12 30 0.47 & p4=$!
wait "$p1" "$p2" "$p3" "$p4"

python3 /src/lane/merge_capture_stress.py \
  --case /work/stress-prbs_base.json --case /work/stress-channel.json \
  --case /work/stress-timing.json --case /work/stress-combined.json \
  --output /work/capture-stress.json
