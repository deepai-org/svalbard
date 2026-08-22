#!/usr/bin/env bash
# Shared exact-PEX preparation for lane-to-parallel-CMOS verification flows.

extract_capture_cell() {
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

prepare_capture_stack() {
  extract_capture_cell termination serdes_termination termination.spice serdes_termination_pex
  extract_capture_cell serdes_rx serdes_rx serdes_rx.spice serdes_rx_pex
  extract_capture_cell cdr cdr_sampler cdr_sampler.spice cdr_sampler_pex
  extract_capture_cell cdr/cml_to_cmos cml_to_cmos cml_to_cmos.spice cml_to_cmos_pex
  extract_capture_cell deserializer_split deserializer_split_capture \
    deserializer_split.spice deserializer_split_capture_pex

  split_pex=/work/deserializer_split_capture-pex/deserializer_split_capture.pex.spice
  SPLIT_CAPTURE_PEX="$split_pex" \
    SPLIT_CAPTURE_RENDER=/work/capture-layout.png \
    klayout -b -r /src/deserializer_split/render_layout.py > /work/capture-render.log 2>&1
  python3 /src/deserializer_split/check_physical.py \
    --drc /work/deserializer_split_capture-drc/deserializer_split_capture.magic.drc/deserializer_split_capture.magic.drc.rpt \
    --lvs /work/deserializer_split_capture-lvs/deserializer_split_capture.magic.lvs/deserializer_split_capture.lvs.out \
    --pex "$split_pex" --gds /work/deserializer_split_capture.gds \
    --render /work/capture-layout.png \
    --layout /src/deserializer_split/layout.tcl \
    --schematic /src/deserializer_split/deserializer_split.spice \
    --output /work/capture-physical.json

  capture_args=(
    --source /src --jobs 4
    --tx-pex /src/serializer/integrated_serializer_tx.pex.spice
    --term-pex /work/serdes_termination-pex/serdes_termination.pex.spice
    --rx-pex /work/serdes_rx-pex/serdes_rx.pex.spice
    --sampler-pex /work/cdr_sampler-pex/cdr_sampler.pex.spice
    --frontend-pex /work/cml_to_cmos-pex/cml_to_cmos.pex.spice
    --deserializer-pex "$split_pex"
    --deserializer-physical /work/capture-physical.json
  )
}
