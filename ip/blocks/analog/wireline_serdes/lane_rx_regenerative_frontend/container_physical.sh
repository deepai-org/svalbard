#!/usr/bin/env bash
set -euo pipefail
cd /work

magic_run() {
  magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
    "$1" > "$2" 2>&1
}

magic_run /src/termination/layout.tcl /work/regen-termination.log
magic_run /src/serdes_rx/layout.tcl /work/regen-rx.log
export CML_TO_CMOS_FAST_LAYOUT=1
magic_run /src/cdr/cml_to_cmos/layout.tcl /work/regen-converter.log
unset CML_TO_CMOS_FAST_LAYOUT
magic_run /src/lane_rx_regenerative_frontend/layout.tcl /work/regen-parent.log

sak-drc.sh -m -w /work/regen-drc /work/lane_rx_regenerative_frontend.mag \
  > /work/regen-drc-stage.log 2>&1
sak-lvs.sh -m -w /work/regen-lvs \
  -s /src/lane_rx_regenerative_frontend/lane_rx_regenerative_frontend.spice \
  -l /work/lane_rx_regenerative_frontend.mag \
  -c lane_rx_regenerative_frontend > /work/regen-lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n lane_rx_regenerative_frontend_pex \
  -w /work/regen-pex /work/lane_rx_regenerative_frontend.mag \
  > /work/regen-pex-stage.log 2>&1

pex=/work/regen-pex/lane_rx_regenerative_frontend.pex.spice
sed -i -E '1s/^\* PEX produced on .* using /\* PEX produced using /' "$pex"
grep -q '^\* PEX produced using ' "$pex"
export VCO_BAND_CELL_NAME=lane_rx_regenerative_frontend
export VCO_BAND_RENDER_PATH=/work/layout-lane-rx-regenerative-frontend.png
python3 /src/pll/render_vco_band.py > /work/regen-render.log 2>&1

python3 /src/lane_rx_regenerative_frontend/check_physical.py \
  --source /src/lane_rx_regenerative_frontend \
  --drc /work/regen-drc/lane_rx_regenerative_frontend.magic.drc/lane_rx_regenerative_frontend.magic.drc.rpt \
  --lvs /work/regen-lvs/lane_rx_regenerative_frontend.magic.lvs/lane_rx_regenerative_frontend.lvs.out \
  --pex "$pex" --gds /work/lane_rx_regenerative_frontend.gds \
  --render /work/layout-lane-rx-regenerative-frontend.png \
  --output /work/lane-rx-regenerative-frontend-physical.json
cp "$pex" /work/lane-rx-regenerative-frontend.pex.spice
