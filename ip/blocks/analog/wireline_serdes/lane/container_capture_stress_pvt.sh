#!/usr/bin/env bash
set -euo pipefail
. /src/lane/capture_stack.sh
prepare_capture_stack

run_stress_pvt() {
  local name="$1" mos="$2" resistor="$3" vdd="$4" temp="$5" tx_bias="$6" rest_bias="$7"
  python3 /src/lane/run_capture_stress_case.py "${capture_args[@]}" \
    --jobs 1 --offset-ps 0 --allow-fail --case-id "$name" \
    --pattern prbs7 --bit-count 40 --simulation-timeout-s 900 \
    --channel-series-ohm-per-leg 6 --channel-shunt-cap-f 1e-12 \
    --tx-clock-jitter-ps 30 --tx-clock-duty 0.47 \
    --vdd-ripple-mv 20 --vdd-ripple-hz 100e6 \
    --restorer-mode data --restorer-bias "$rest_bias" --sampler-phase 78.75 \
    --mos-corner "$mos" --res-corner "$resistor" --vdd "$vdd" \
    --temperature "$temp" --tx-bias "$tx_bias" \
    --work "/work/stress-pvt-${name}" --output "/work/stress-pvt-${name}.json"
}

run_stress_pvt tt typical res_typical 3.30 27 1.10 1.30 & p1=$!
run_stress_pvt ff_cold ff res_ff 3.63 -40 1.00 1.30 & p2=$!
run_stress_pvt ff_hot ff res_ss 2.97 125 0.90 1.20 & p3=$!
run_stress_pvt ss_hot ss res_ff 2.97 125 1.30 1.40 & p4=$!
run_stress_pvt ss_passive ss res_ss 2.97 125 1.20 1.30 & p5=$!
wait "$p1" "$p2" "$p3" "$p4" "$p5"

python3 /src/lane/merge_capture_stress_pvt.py \
  --case /work/stress-pvt-tt.json --case /work/stress-pvt-ff_cold.json \
  --case /work/stress-pvt-ff_hot.json --case /work/stress-pvt-ss_hot.json \
  --case /work/stress-pvt-ss_passive.json --output /work/capture-stress-pvt.json
