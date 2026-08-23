#!/usr/bin/env bash
set -euo pipefail
cd /work

magic_run() {
  magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
    "$1" > "$2" 2>&1
}

bash /src/lane_rx_frontend/container_physical.sh
magic_run /src/deserializer_split/layout.tcl /work/capture-child-layout.log
magic_run /src/lane_rx_capture/layout.tcl /work/lane-rx-capture-layout.log

sak-drc.sh -m -w /work/lane-rx-capture-drc /work/lane_rx_capture.mag \
  > /work/lane-rx-capture-drc-stage.log 2>&1
sak-lvs.sh -m -w /work/lane-rx-capture-lvs \
  -s /src/lane_rx_capture/lane_rx_capture.spice \
  -l /work/lane_rx_capture.mag -c lane_rx_capture \
  > /work/lane-rx-capture-lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n lane_rx_capture_pex \
  -w /work/lane-rx-capture-pex /work/lane_rx_capture.mag \
  > /work/lane-rx-capture-pex-stage.log 2>&1

pex=/work/lane-rx-capture-pex/lane_rx_capture.pex.spice
sed -i -E '1s/^\* PEX produced on .* using /\* PEX produced using /' "$pex"
grep -q '^\* PEX produced using ' "$pex"
export VCO_BAND_CELL_NAME=lane_rx_capture
export VCO_BAND_RENDER_PATH=/work/layout-lane-rx-capture.png
python3 /src/pll/render_vco_band.py > /work/lane-rx-capture-render.log 2>&1

drc=/work/lane-rx-capture-drc/lane_rx_capture.magic.drc/lane_rx_capture.magic.drc.rpt
lvs=/work/lane-rx-capture-lvs/lane_rx_capture.magic.lvs/lane_rx_capture.lvs.out
python3 /src/lane_rx_capture/check_physical.py \
  --source /src/lane_rx_capture --drc "$drc" --lvs "$lvs" --pex "$pex" \
  --gds /work/lane_rx_capture.gds --render /work/layout-lane-rx-capture.png \
  --output /work/lane-rx-capture-physical-result.json
cp "$pex" /work/lane-rx-capture.pex.spice
