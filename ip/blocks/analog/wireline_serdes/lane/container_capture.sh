#!/usr/bin/env bash
set -euo pipefail
. /src/lane/capture_stack.sh
prepare_capture_stack
python3 /src/lane/run_capture.py "${capture_args[@]}" \
  --work /work/capture --output /work/capture.json

run_pvt_case() {
  local name="$1" mos="$2" resistor="$3" vdd="$4" temp="$5" tx_bias="$6"
  python3 /src/lane/run_capture.py "${capture_args[@]}" --offset-ps 0 --allow-fail \
    --mos-corner "$mos" --res-corner "$resistor" --vdd "$vdd" \
    --temperature "$temp" --tx-bias "$tx_bias" \
    --work "/work/capture-${name}" --output "/work/capture-${name}.json"
}
run_pvt_case ff ff res_ff 3.63 -40 1.00 & p1=$!
run_pvt_case ff_hot ff res_ss 2.97 125 0.90 & p2=$!
run_pvt_case ss_hot ss res_ff 2.97 125 1.30 & p3=$!
run_pvt_case ss_passive ss res_ss 2.97 125 1.20 & p4=$!
wait "$p1" "$p2" "$p3" "$p4"
python3 /src/lane/merge_capture_pvt.py \
  --case /work/capture.json --case /work/capture-ff.json \
  --case /work/capture-ff_hot.json --case /work/capture-ss_hot.json \
  --case /work/capture-ss_passive.json --output /work/capture-pvt.json
