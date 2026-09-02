#!/usr/bin/env bash
set -euo pipefail
cd /work
magic_run() {
  magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
    "$1" > "$2" 2>&1
}

python3 /src/event_lane_routed_parent/compile_source.py \
  --output /work/event_lane_routed_parent.spice
python3 /src/clock_pulse_hclk_window_probe/compile_event_capture_physical_source.py \
  --output /work/event_capture_physical.spice
python3 /src/clock_pulse/generate_pulse_layout.py \
  --source /work/event_capture_physical.spice --top retimed_event_capture_bridge \
  --output /work/event_capture_layout.tcl
magic_run /work/event_capture_layout.tcl /work/parent-event.log
python3 /src/clock_pulse_hclk_window_probe/compile_local_clock_fanout_source.py \
  --output /work/local_clock_fanout.spice
python3 /src/clock_pulse/generate_pulse_layout.py \
  --source /work/local_clock_fanout.spice --top local_clock_fanout \
  --output /work/local_clock_fanout_layout.tcl
magic_run /work/local_clock_fanout_layout.tcl /work/parent-fanout.log

magic_run /src/termination/layout.tcl /work/parent-termination.log
magic_run /src/serdes_rx/layout.tcl /work/parent-rx.log
export CML_TO_CMOS_FAST_LAYOUT=1
magic_run /src/cdr/cml_to_cmos/layout.tcl /work/parent-converter.log
unset CML_TO_CMOS_FAST_LAYOUT
magic_run /src/lane_rx_regenerative_frontend/layout.tcl /work/parent-front.log
magic_run /src/deserializer_split/layout.tcl /work/parent-capture.log
magic_run /src/lane_rx_regenerative_capture/layout.tcl /work/parent-lane.log
magic_run /src/reference_level_receiver/layout.tcl /work/parent-event-level.log
magic_run /src/event_lane_routed_parent/layout.tcl /work/parent-layout.log

sak-drc.sh -m -w /work/parent-drc /work/event_lane_routed_parent.mag \
  > /work/parent-drc-stage.log 2>&1
sak-lvs.sh -m -w /work/parent-lvs -s /work/event_lane_routed_parent.spice \
  -l /work/event_lane_routed_parent.mag -c event_lane_routed_parent \
  > /work/parent-lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n event_lane_routed_parent_pex \
  -w /work/parent-pex /work/event_lane_routed_parent.mag \
  > /work/parent-pex-stage.log 2>&1
pex=/work/parent-pex/event_lane_routed_parent.pex.spice
sed -i -E '1s/^\* PEX produced on .* using /\* PEX produced using /' "$pex"
grep -q '^\* PEX produced using ' "$pex"
export VCO_BAND_CELL_NAME=event_lane_routed_parent
export VCO_BAND_RENDER_PATH=/work/event_lane_routed_parent-layout.png
python3 /src/pll/render_vco_band.py > /work/parent-render.log 2>&1
python3 /src/event_lane_routed_parent/check_physical.py \
  --source /work/event_lane_routed_parent.spice \
  --layout /src/event_lane_routed_parent/layout.tcl \
  --drc /work/parent-drc/event_lane_routed_parent.magic.drc/event_lane_routed_parent.magic.drc.rpt \
  --lvs /work/parent-lvs/event_lane_routed_parent.magic.lvs/event_lane_routed_parent.lvs.out \
  --pex "$pex" --gds /work/event_lane_routed_parent.gds \
  --render /work/event_lane_routed_parent-layout.png \
  --output /work/event_lane_routed_parent_physical.json
cp "$pex" /work/event_lane_routed_parent.pex.spice
