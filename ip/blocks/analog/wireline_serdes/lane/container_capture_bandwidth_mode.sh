#!/usr/bin/env bash
set -euo pipefail
. /src/lane/capture_stack.sh
prepare_capture_stack

run_mode() {
  local name="$1" mode="$2" resistance="$3" capacitance="$4"
  python3 /src/lane/run_capture_stress_case.py "${capture_args[@]}" \
    --jobs 1 --offset-ps 0 --allow-fail --case-id "$name" \
    --pattern prbs7 --bit-count 40 --simulation-timeout-s 900 \
    --channel-series-ohm-per-leg "$resistance" --channel-shunt-cap-f "$capacitance" \
    --tx-clock-jitter-ps 30 --tx-clock-duty 0.47 \
    --vdd-ripple-mv 20 --vdd-ripple-hz 100e6 --rx-bandwidth-mode "$mode" \
    --mos-corner ss --res-corner res_ss --vdd 2.97 --temperature 125 --tx-bias 1.20 \
    --work "/work/mode-${name}" --output "/work/mode-${name}.json"
}

run_mode low_ch6 low 6 1e-12 & p1=$!
run_mode low_ch7 low 7 1.25e-12 & p2=$!
run_mode high_ch6 high 6 1e-12 & p3=$!
run_mode high_ch7 high 7 1.25e-12 & p4=$!
wait "$p1" "$p2" "$p3" "$p4"

python3 /src/lane/merge_capture_bandwidth_mode.py \
  --case /work/mode-low_ch6.json --case /work/mode-low_ch7.json \
  --case /work/mode-high_ch6.json --case /work/mode-high_ch7.json \
  --output /work/capture-bandwidth-mode.json
