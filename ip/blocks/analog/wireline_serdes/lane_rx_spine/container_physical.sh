#!/usr/bin/env bash
set -euo pipefail
cd /work

magic_run() {
  magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
    "$1" > "$2" 2>&1
}

magic_run /src/serdes_rx/layout.tcl /work/spine-rx-layout.log
DATA_RESTORER_STAGE_CELL=cml_data_restorer_2p5_calibrated_stage \
  DATA_RESTORER_LOAD_LENGTH=4.2 \
  magic_run /src/data_restorer/stage_layout.tcl /work/spine-restorer-stage-layout.log
DATA_RESTORER_CELL=cml_data_restorer_2p5_calibrated \
  DATA_RESTORER_STAGE_CELL=cml_data_restorer_2p5_calibrated_stage \
  magic_run /src/data_restorer/layout.tcl /work/spine-restorer-layout.log
magic_run /src/cdr/layout.tcl /work/spine-sampler-layout.log
magic_run /src/lane_rx_spine/layout.tcl /work/lane-rx-spine-layout.log

sak-drc.sh -m -w /work/lane-rx-spine-drc /work/lane_rx_spine.mag \
  > /work/lane-rx-spine-drc-stage.log 2>&1
sak-lvs.sh -m -w /work/lane-rx-spine-lvs \
  -s /src/lane_rx_spine/lane_rx_spine.spice \
  -l /work/lane_rx_spine.mag -c lane_rx_spine \
  > /work/lane-rx-spine-lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n lane_rx_spine_pex \
  -w /work/lane-rx-spine-pex /work/lane_rx_spine.mag \
  > /work/lane-rx-spine-pex-stage.log 2>&1

export VCO_BAND_CELL_NAME=lane_rx_spine
export VCO_BAND_RENDER_PATH=/work/layout-lane-rx-spine.png
python3 /src/pll/render_vco_band.py > /work/lane-rx-spine-render.log 2>&1

drc=/work/lane-rx-spine-drc/lane_rx_spine.magic.drc/lane_rx_spine.magic.drc.rpt
lvs=/work/lane-rx-spine-lvs/lane_rx_spine.magic.lvs/lane_rx_spine.lvs.out
pex=/work/lane-rx-spine-pex/lane_rx_spine.pex.spice
python3 /src/lane_rx_spine/check_physical.py --source /src/lane_rx_spine \
  --drc "$drc" --lvs "$lvs" --pex "$pex" --gds /work/lane_rx_spine.gds \
  --render /work/layout-lane-rx-spine.png \
  --output /work/lane-rx-spine-physical-result.json
cp "$pex" /work/lane-rx-spine.pex.spice
