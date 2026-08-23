#!/usr/bin/env bash
# Shared exact-PEX preparation for lane-to-parallel-CMOS verification flows.

canonicalize_capture_pex() {
  local path="$1"
  sed -i -E '1s/^\* PEX produced on .* using /\* PEX produced using /' "$path"
  grep -q '^\* PEX produced using ' "$path"
}

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
  canonicalize_capture_pex "/work/${cell}-pex/${cell}.pex.spice"
}

prepare_lane_base_stack() {
  extract_capture_cell termination serdes_termination termination.spice serdes_termination_pex
  extract_capture_cell serdes_rx serdes_rx serdes_rx.spice serdes_rx_pex
  extract_capture_cell cdr cdr_sampler cdr_sampler.spice cdr_sampler_pex
}

prepare_data_restorer_1p25() {
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
}

prepare_data_restorer_2p5() {
  DATA_RESTORER_STAGE_CELL=cml_data_restorer_2p5_stage \
    DATA_RESTORER_LOAD_LENGTH=3.6 \
    magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
    /src/data_restorer/stage_layout.tcl > /work/data-restorer-2p5-stage.layout.log 2>&1
  DATA_RESTORER_CELL=cml_data_restorer_2p5 \
    DATA_RESTORER_STAGE_CELL=cml_data_restorer_2p5_stage \
    magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
    /src/data_restorer/layout.tcl > /work/data-restorer-2p5.layout.log 2>&1
  sak-drc.sh -m -w /work/cml_data_restorer_2p5-drc \
    /work/cml_data_restorer_2p5.mag > /work/data-restorer-2p5.drc.log 2>&1
  sak-lvs.sh -m -w /work/cml_data_restorer_2p5-lvs \
    -s /src/data_restorer/data_restorer_2p5.spice \
    -l /work/cml_data_restorer_2p5.mag -c cml_data_restorer_2p5 \
    > /work/data-restorer-2p5.lvs.log 2>&1
  sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n cml_data_restorer_2p5_pex \
    -w /work/cml_data_restorer_2p5-pex /work/cml_data_restorer_2p5.mag \
    > /work/data-restorer-2p5.pex.log 2>&1
  canonicalize_capture_pex \
    /work/cml_data_restorer_2p5-pex/cml_data_restorer_2p5.pex.spice

  export VCO_BAND_CELL_NAME=cml_data_restorer_2p5
  export VCO_BAND_RENDER_PATH=/work/data-restorer-2p5-layout.png
  python3 /src/pll/render_vco_band.py > /work/data-restorer-2p5-render.log 2>&1
  python3 /src/pll/check_clock_restorer_physical.py --source /src/data_restorer \
    --drc /work/cml_data_restorer_2p5-drc/cml_data_restorer_2p5.magic.drc/cml_data_restorer_2p5.magic.drc.rpt \
    --lvs /work/cml_data_restorer_2p5-lvs/cml_data_restorer_2p5.magic.lvs/cml_data_restorer_2p5.lvs.out \
    --pex /work/cml_data_restorer_2p5-pex/cml_data_restorer_2p5.pex.spice \
    --gds /work/cml_data_restorer_2p5.gds \
    --render /work/data-restorer-2p5-layout.png \
    --claim data_restorer_2p5_structural_physical_closure \
    --layout-source layout.tcl --schematic-source data_restorer_2p5.spice \
    --minimum-resistors 40 --minimum-capacitors 10 \
    --output /work/data-restorer-2p5-physical.json
}

prepare_lane_frontend_stack() {
  prepare_lane_base_stack
  prepare_data_restorer_1p25

  lane_frontend_args=(
    --source /src --jobs 4
    --tx-pex /src/serializer/integrated_serializer_tx.pex.spice
    --term-pex /work/serdes_termination-pex/serdes_termination.pex.spice
    --rx-pex /work/serdes_rx-pex/serdes_rx.pex.spice
    --sampler-pex /work/cdr_sampler-pex/cdr_sampler.pex.spice
    --restorer-pex /work/cml_data_restorer-pex/cml_data_restorer.pex.spice
    --restorer-physical /work/data-restorer-physical.json
  )
}

prepare_capture_stack() {
  prepare_lane_frontend_stack
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
    "${lane_frontend_args[@]}"
    --frontend-pex /work/cml_to_cmos-pex/cml_to_cmos.pex.spice
    --deserializer-pex "$split_pex"
    --deserializer-physical /work/capture-physical.json
  )
}
