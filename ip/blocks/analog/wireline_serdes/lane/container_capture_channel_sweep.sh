#!/usr/bin/env bash
set -euo pipefail
. /src/lane/capture_stack.sh
prepare_capture_stack

run_channel() {
  local name="$1" resistance="$2" capacitance="$3"
  python3 /src/lane/run_capture_stress_case.py "${capture_args[@]}" \
    --jobs 1 --offset-ps 0 --allow-fail --case-id "$name" \
    --pattern prbs7 --bit-count 40 --simulation-timeout-s 900 \
    --channel-series-ohm-per-leg "$resistance" --channel-shunt-cap-f "$capacitance" \
    --work "/work/channel-${name}" --output "/work/channel-${name}.json"
}

run_channel ch6 6 1e-12 & p1=$!
run_channel ch7 7 1.25e-12 & p2=$!
run_channel ch8 8 1.5e-12 & p3=$!
run_channel ch9 9 1.75e-12 & p4=$!
wait "$p1" "$p2" "$p3" "$p4"

python3 /src/lane/merge_capture_channel_sweep.py \
  --case /work/channel-ch6.json --case /work/channel-ch7.json \
  --case /work/channel-ch8.json --case /work/channel-ch9.json \
  --output /work/capture-channel-sweep.json
