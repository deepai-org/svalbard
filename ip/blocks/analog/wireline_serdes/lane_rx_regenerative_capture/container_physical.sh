#!/usr/bin/env bash
set -euo pipefail
cd /work
magic_run() {
  magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
    "$1" > "$2" 2>&1
}
magic_run /src/termination/layout.tcl /work/regcap-termination.log
magic_run /src/serdes_rx/layout.tcl /work/regcap-rx.log
export CML_TO_CMOS_FAST_LAYOUT=1
magic_run /src/cdr/cml_to_cmos/layout.tcl /work/regcap-converter.log
unset CML_TO_CMOS_FAST_LAYOUT
magic_run /src/lane_rx_regenerative_frontend/layout.tcl /work/regcap-front.log
magic_run /src/deserializer_split/layout.tcl /work/regcap-capture.log
magic_run /src/lane_rx_regenerative_capture/layout.tcl /work/regcap-parent.log
sak-drc.sh -m -w /work/regcap-drc /work/lane_rx_regenerative_capture.mag \
  > /work/regcap-drc-stage.log 2>&1
sak-lvs.sh -m -w /work/regcap-lvs \
  -s /src/lane_rx_regenerative_capture/lane_rx_regenerative_capture.spice \
  -l /work/lane_rx_regenerative_capture.mag -c lane_rx_regenerative_capture \
  > /work/regcap-lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n lane_rx_regenerative_capture_pex \
  -w /work/regcap-pex /work/lane_rx_regenerative_capture.mag \
  > /work/regcap-pex-stage.log 2>&1
pex=/work/regcap-pex/lane_rx_regenerative_capture.pex.spice
sed -i -E '1s/^\* PEX produced on .* using /\* PEX produced using /' "$pex"
grep -q '^\* PEX produced using ' "$pex"
export VCO_BAND_CELL_NAME=lane_rx_regenerative_capture
export VCO_BAND_RENDER_PATH=/work/layout-lane-rx-regenerative-capture.png
python3 /src/pll/render_vco_band.py > /work/regcap-render.log 2>&1
python3 /src/lane_rx_regenerative_capture/check_physical.py \
  --source /src/lane_rx_regenerative_capture \
  --drc /work/regcap-drc/lane_rx_regenerative_capture.magic.drc/lane_rx_regenerative_capture.magic.drc.rpt \
  --lvs /work/regcap-lvs/lane_rx_regenerative_capture.magic.lvs/lane_rx_regenerative_capture.lvs.out \
  --pex "$pex" --gds /work/lane_rx_regenerative_capture.gds \
  --render /work/layout-lane-rx-regenerative-capture.png \
  --output /work/lane-rx-regenerative-capture-physical.json
cp "$pex" /work/lane-rx-regenerative-capture.pex.spice
