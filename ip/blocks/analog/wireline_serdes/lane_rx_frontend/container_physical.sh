#!/usr/bin/env bash
set -euo pipefail
cd /work

magic_run() {
  magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
    "$1" > "$2" 2>&1
}

bash /src/lane_rx_spine/container_physical.sh
magic_run /src/termination/layout.tcl /work/front-termination-layout.log
magic_run /src/cdr/cml_to_cmos/layout.tcl /work/front-converter-layout.log
magic_run /src/lane_rx_frontend/layout.tcl /work/lane-rx-frontend-layout.log

sak-drc.sh -m -w /work/lane-rx-frontend-drc /work/lane_rx_frontend.mag \
  > /work/lane-rx-frontend-drc-stage.log 2>&1
sak-lvs.sh -m -w /work/lane-rx-frontend-lvs \
  -s /src/lane_rx_frontend/lane_rx_frontend.spice \
  -l /work/lane_rx_frontend.mag -c lane_rx_frontend \
  > /work/lane-rx-frontend-lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n lane_rx_frontend_pex \
  -w /work/lane-rx-frontend-pex /work/lane_rx_frontend.mag \
  > /work/lane-rx-frontend-pex-stage.log 2>&1

pex=/work/lane-rx-frontend-pex/lane_rx_frontend.pex.spice
sed -i -E '1s/^\* PEX produced on .* using /\* PEX produced using /' "$pex"
grep -q '^\* PEX produced using ' "$pex"
export VCO_BAND_CELL_NAME=lane_rx_frontend
export VCO_BAND_RENDER_PATH=/work/layout-lane-rx-frontend.png
python3 /src/pll/render_vco_band.py > /work/lane-rx-frontend-render.log 2>&1

drc=/work/lane-rx-frontend-drc/lane_rx_frontend.magic.drc/lane_rx_frontend.magic.drc.rpt
lvs=/work/lane-rx-frontend-lvs/lane_rx_frontend.magic.lvs/lane_rx_frontend.lvs.out
python3 /src/lane_rx_frontend/check_physical.py \
  --source /src/lane_rx_frontend --drc "$drc" --lvs "$lvs" --pex "$pex" \
  --gds /work/lane_rx_frontend.gds --render /work/layout-lane-rx-frontend.png \
  --output /work/lane-rx-frontend-physical-result.json
cp "$pex" /work/lane-rx-frontend.pex.spice
