#!/usr/bin/env bash
set -euo pipefail
cd /work

magic_run() {
  magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
    "$1" > "$2" 2>&1
}

# Build the hierarchy bottom-up. The fast converter retains the old cell name,
# outline, and pin coordinates; the versioned front-end route moves only the
# two metal-5 signal trunks that collide with the new child power mesh.
bash /src/lane_rx_spine/container_physical.sh
magic_run /src/termination/layout.tcl /work/fast-parent-termination.log
export CML_TO_CMOS_FAST_LAYOUT=1
magic_run /src/cdr/cml_to_cmos/layout.tcl /work/fast-parent-converter.log
unset CML_TO_CMOS_FAST_LAYOUT
magic_run /src/lane_rx_frontend/layout_fast.tcl /work/fast-parent-frontend.log
magic_run /src/deserializer_split/layout.tcl /work/fast-parent-capture.log
magic_run /src/lane_rx_capture/layout.tcl /work/fast-parent-rx-capture.log
magic_run /src/phase_interpolator/layout.tcl /work/fast-parent-pi.log
magic_run /src/pll/clock_restorer_layout.tcl /work/fast-parent-restorer.log
magic_run /src/pll/clock_restorer_cascade_layout.tcl \
  /work/fast-parent-restorer-cascade.log
magic_run /src/lane_rx_pi_capture/layout.tcl /work/fast-parent-layout.log

sak-drc.sh -m -w /work/fast-parent-drc /work/lane_rx_pi_capture.mag \
  > /work/fast-parent-drc-stage.log 2>&1
sak-lvs.sh -m -w /work/fast-parent-lvs \
  -s /src/lane_rx_pi_capture/lane_rx_pi_capture_fast.spice \
  -l /work/lane_rx_pi_capture.mag -c lane_rx_pi_capture \
  > /work/fast-parent-lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n lane_rx_pi_capture_pex \
  -w /work/fast-parent-pex /work/lane_rx_pi_capture.mag \
  > /work/fast-parent-pex-stage.log 2>&1

pex=/work/fast-parent-pex/lane_rx_pi_capture.pex.spice
sed -i -E '1s/^\* PEX produced on .* using /\* PEX produced using /' "$pex"
grep -q '^\* PEX produced using ' "$pex"
export VCO_BAND_CELL_NAME=lane_rx_pi_capture
export VCO_BAND_RENDER_PATH=/work/layout-lane-rx-pi-capture-fast.png
python3 /src/pll/render_vco_band.py > /work/fast-parent-render.log 2>&1

python3 /src/lane_rx_pi_capture/check_fast_physical.py \
  --drc /work/fast-parent-drc/lane_rx_pi_capture.magic.drc/lane_rx_pi_capture.magic.drc.rpt \
  --lvs /work/fast-parent-lvs/lane_rx_pi_capture.magic.lvs/lane_rx_pi_capture.lvs.out \
  --pex "$pex" --gds /work/lane_rx_pi_capture.gds \
  --render /work/layout-lane-rx-pi-capture-fast.png \
  --top-schematic /src/lane_rx_pi_capture/lane_rx_pi_capture_fast.spice \
  --capture-schematic /src/lane_rx_capture/lane_rx_capture_fast.spice \
  --frontend-schematic /src/lane_rx_frontend/lane_rx_frontend_fast.spice \
  --converter-schematic /src/cdr/cml_to_cmos/cml_to_cmos_fast.spice \
  --top-layout /src/lane_rx_pi_capture/layout.tcl \
  --capture-layout /src/lane_rx_capture/layout.tcl \
  --frontend-layout /src/lane_rx_frontend/layout_fast.tcl \
  --frontend-base-layout /src/lane_rx_frontend/layout.tcl \
  --converter-layout /src/cdr/cml_to_cmos/layout.tcl \
  --output /work/lane-rx-pi-capture-fast-physical.json
cp "$pex" /work/lane-rx-pi-capture-fast.pex.spice
