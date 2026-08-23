#!/usr/bin/env bash
set -euo pipefail
. /src/lane/capture_stack.sh
prepare_capture_stack

run_factor() {
  local name="$1" resistance="$2" capacitance="$3" jitter="$4" duty="$5" ripple="$6"
  python3 /src/lane/run_capture_stress_case.py "${capture_args[@]}" \
    --jobs 1 --offset-ps 0 --allow-fail --case-id "$name" \
    --pattern prbs7 --bit-count 40 --simulation-timeout-s 900 \
    --channel-series-ohm-per-leg "$resistance" --channel-shunt-cap-f "$capacitance" \
    --tx-clock-jitter-ps "$jitter" --tx-clock-duty "$duty" \
    --vdd-ripple-mv "$ripple" --vdd-ripple-hz 100e6 \
    --work "/work/factor-${name}" --output "/work/factor-${name}.json"
}

run_factor baseline 0 0 0 0.50 0 & p1=$!
run_factor channel 10 2e-12 0 0.50 0 & p2=$!
run_factor timing 0 0 30 0.47 0 & p3=$!
run_factor ripple 0 0 0 0.50 20 & p4=$!
wait "$p1" "$p2" "$p3" "$p4"

python3 /src/lane/merge_capture_factor.py \
  --case /work/factor-baseline.json --case /work/factor-channel.json \
  --case /work/factor-timing.json --case /work/factor-ripple.json \
  --output /work/capture-factor.json
