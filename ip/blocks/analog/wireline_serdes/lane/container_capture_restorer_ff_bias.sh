#!/usr/bin/env bash
set -euo pipefail
. /src/lane/capture_stack.sh
prepare_capture_stack

run_case() {
  local name="$1" bias="$2"
  python3 /src/lane/run_capture_stress_case.py "${capture_args[@]}" \
    --jobs 1 --offset-ps 0 --allow-fail --case-id "$name" \
    --pattern prbs7 --bit-count 40 --simulation-timeout-s 900 \
    --channel-series-ohm-per-leg 6 --channel-shunt-cap-f 1e-12 \
    --tx-clock-jitter-ps 30 --tx-clock-duty 0.47 \
    --vdd-ripple-mv 20 --vdd-ripple-hz 100e6 \
    --mos-corner ff --res-corner res_ss --vdd 2.97 --temperature 125 \
    --tx-bias 0.90 --rx-bias 1.10 --sampler-phase 78.75 \
    --restorer-mode data --restorer-bias "$bias" \
    --work "/work/restorer-${name}" --output "/work/restorer-${name}.json"
}

run_case rb11 1.10 & p1=$!
run_case rb12 1.20 & p2=$!
run_case rb125 1.25 & p3=$!
run_case rb13 1.30 & p4=$!
wait "$p1" "$p2" "$p3" "$p4"

python3 /src/lane/merge_capture_restorer_sweep.py \
  --claim completed_fast_slow_passive_exact_pex_data_restorer_bias_screen \
  --axis restorer_bias_v \
  --expected rb11=1.10 --expected rb12=1.20 \
  --expected rb125=1.25 --expected rb13=1.30 \
  --case /work/restorer-rb11.json --case /work/restorer-rb12.json \
  --case /work/restorer-rb125.json --case /work/restorer-rb13.json \
  --output /work/capture-restorer-ff-bias.json
