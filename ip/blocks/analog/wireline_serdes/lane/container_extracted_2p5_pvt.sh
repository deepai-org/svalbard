#!/usr/bin/env bash
set -euo pipefail

lane_2p5_args=(
  --source /src --jobs 1
  --tx-pex /src/serializer/integrated_serializer_tx.pex.spice
  --term-pex /src/lane/termination_2p5.pex.spice
  --rx-pex /src/lane/rx_2p5.pex.spice
  --sampler-pex /src/lane/sampler_2p5.pex.spice
  --base-physical /src/lane/physical_2p5_result.json
  --restorer-pex /src/data_restorer/data_restorer_2p5.pex.spice
  --restorer-physical /src/data_restorer/physical_2p5_result.json
  --restorer-cell cml_data_restorer_2p5_pex
  --serial-rate-gbd 2.5 --allow-fail
)

run_pvt() {
  local name="$1" mos="$2" resistor="$3" vdd="$4" temp="$5"
  local tx_bias="$6" rx_bias="$7" restorer_bias="$8" sampler_bias="$9"
  local ac_initial_v="${10}"
  shift 10
  python3 /src/lane/run_lane.py "${lane_2p5_args[@]}" \
    --mos-corner "$mos" --res-corner "$resistor" --vdd "$vdd" \
    --temperature "$temp" --tx-bias "$tx_bias" --rx-bias "$rx_bias" \
    --restorer-bias "$restorer_bias" --sampler-bias "$sampler_bias" \
    --ac-initial-v "$ac_initial_v" "$@" \
    --work "/work/pvt-2p5-${name}" --output "/work/pvt-2p5-${name}.json"
}

run_pvt tt typical res_typical 3.30 27 1.20 1.30 1.30 1.10 0.950 \
  --phase 22.5 --phase 45 --phase 67.5 & p1=$!
run_pvt ff_cold ff res_ff 3.63 -40 1.10 1.20 1.20 1.10 1.076 \
  --phase 45 --phase 67.5 --phase 90 & p2=$!
run_pvt ff_hot ff res_ss 2.97 125 1.20 1.20 1.20 0.90 0.531 \
  --phase 11.25 --phase 16.875 --phase 22.5 & p3=$!
run_pvt ss_hot ss res_ff 2.97 125 1.50 1.50 1.50 1.20 0.796 \
  --phase 112.5 --phase 135 --phase 157.5 & p4=$!
run_pvt ss_passive ss res_ss 2.97 125 1.60 1.50 1.50 1.20 0.592 \
  --phase 112.5 --phase 135 --phase 157.5 & p5=$!
wait "$p1" "$p2" "$p3" "$p4" "$p5"

python3 /src/lane/merge_pvt.py --serial-rate-gbd 2.5 \
  --case /work/pvt-2p5-tt.json --case /work/pvt-2p5-ff_cold.json \
  --case /work/pvt-2p5-ff_hot.json --case /work/pvt-2p5-ss_hot.json \
  --case /work/pvt-2p5-ss_passive.json --output /work/pvt-2p5.json
