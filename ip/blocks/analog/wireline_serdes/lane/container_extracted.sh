#!/usr/bin/env bash
set -euo pipefail

extract_cell() {
  local directory="$1" cell="$2" schematic="$3" pex_name="$4"
  magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
    "/src/${directory}/layout.tcl" > "/work/${cell}.layout.log" 2>&1
  sak-drc.sh -m -w "/work/${cell}-drc" "/work/${cell}.mag" \
    > "/work/${cell}.drc.log" 2>&1
  sak-lvs.sh -m -w "/work/${cell}-lvs" -s "/src/${directory}/${schematic}" \
    -l "/work/${cell}.mag" -c "$cell" > "/work/${cell}.lvs.log" 2>&1
  sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n "$pex_name" -w "/work/${cell}-pex" \
    "/work/${cell}.mag" > "/work/${cell}.pex.log" 2>&1
}

extract_cell termination serdes_termination termination.spice serdes_termination_pex
extract_cell serdes_rx serdes_rx serdes_rx.spice serdes_rx_pex
extract_cell cdr cdr_sampler cdr_sampler.spice cdr_sampler_pex

lane_args=(
  --source /src --jobs 4
  --tx-pex /src/serializer/integrated_serializer_tx.pex.spice
  --term-pex /work/serdes_termination-pex/serdes_termination.pex.spice
  --rx-pex /work/serdes_rx-pex/serdes_rx.pex.spice
  --sampler-pex /work/cdr_sampler-pex/cdr_sampler.pex.spice
)
python3 /src/lane/run_lane.py "${lane_args[@]}" --phase 135 \
  --work /work/extracted-smoke --output /work/extracted-smoke.json
python3 /src/lane/run_lane.py "${lane_args[@]}" \
  --work /work/extracted --output /work/extracted.json

run_pvt_case() {
  local name="$1" mos="$2" resistor="$3" vdd="$4" temp="$5" tx_bias="$6"
  python3 /src/lane/run_lane.py "${lane_args[@]}" --phase 135 --allow-fail \
    --mos-corner "$mos" --res-corner "$resistor" --vdd "$vdd" \
    --temperature "$temp" --tx-bias "$tx_bias" \
    --work "/work/pvt-${name}" --output "/work/pvt-${name}.json"
}
run_pvt_case tt typical res_typical 3.30 27 1.10
run_pvt_case ff ff res_ff 3.63 -40 1.00
run_pvt_case ff_hot ff res_ss 2.97 125 0.90
run_pvt_case ss_hot ss res_ff 2.97 125 1.30
run_pvt_case ss_passive ss res_ss 2.97 125 1.20
python3 /src/lane/merge_pvt.py \
  --case /work/pvt-tt.json --case /work/pvt-ff.json \
  --case /work/pvt-ff_hot.json --case /work/pvt-ss_hot.json \
  --case /work/pvt-ss_passive.json --output /work/pvt.json

python3 /src/lane/check_physical.py \
  --termination-drc /work/serdes_termination-drc/serdes_termination.magic.drc/serdes_termination.magic.drc.rpt \
  --termination-lvs /work/serdes_termination-lvs/serdes_termination.magic.lvs/serdes_termination.lvs.out \
  --termination-pex /work/serdes_termination-pex/serdes_termination.pex.spice \
  --rx-drc /work/serdes_rx-drc/serdes_rx.magic.drc/serdes_rx.magic.drc.rpt \
  --rx-lvs /work/serdes_rx-lvs/serdes_rx.magic.lvs/serdes_rx.lvs.out \
  --rx-pex /work/serdes_rx-pex/serdes_rx.pex.spice \
  --sampler-drc /work/cdr_sampler-drc/cdr_sampler.magic.drc/cdr_sampler.magic.drc.rpt \
  --sampler-lvs /work/cdr_sampler-lvs/cdr_sampler.magic.lvs/cdr_sampler.lvs.out \
  --sampler-pex /work/cdr_sampler-pex/cdr_sampler.pex.spice \
  --lane /work/extracted.json --output /work/physical.json
