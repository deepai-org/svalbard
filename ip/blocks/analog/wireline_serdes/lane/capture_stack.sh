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
  magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
    /src/data_restorer/stage_layout.tcl > /work/data-restorer-stage.layout.log 2>&1
  extract_capture_cell data_restorer cml_data_restorer \
    data_restorer.spice cml_data_restorer_pex

  export VCO_BAND_CELL_NAME=cml_data_restorer
  export VCO_BAND_RENDER_PATH=/work/data-restorer-layout.png
  python3 /src/pll/render_vco_band.py > /work/data-restorer-render.log 2>&1
  python3 /src/pll/check_clock_restorer_physical.py --source /src/data_restorer \
    --drc /work/cml_data_restorer-drc/cml_data_restorer.magic.drc/cml_data_restorer.magic.drc.rpt \
    --lvs /work/cml_data_restorer-lvs/cml_data_restorer.magic.lvs/cml_data_restorer.lvs.out \
    --pex /work/cml_data_restorer-pex/cml_data_restorer.pex.spice \
    --gds /work/cml_data_restorer.gds --render /work/data-restorer-layout.png \
    --claim data_restorer_structural_physical_closure \
    --layout-source layout.tcl --schematic-source data_restorer.spice \
    --minimum-resistors 40 --minimum-capacitors 10 \
    --output /work/data-restorer-physical.json

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
    --restorer-pex /work/cml_data_restorer-pex/cml_data_restorer.pex.spice
    --restorer-physical /work/data-restorer-physical.json
    --frontend-pex /work/cml_to_cmos-pex/cml_to_cmos.pex.spice
    --deserializer-pex "$split_pex"
    --deserializer-physical /work/capture-physical.json
  )
}
