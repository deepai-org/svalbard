#!/usr/bin/env bash
set -euo pipefail
python3 /src/clock_pulse_hclk_window_probe/test_event_start_end_sr_physical.py
python3 /src/clock_pulse_hclk_window_probe/compile_event_capture_state_free_sr_source.py \
  --latch-mult 2 --pre-mult 4 --output-mult 8 --set-mult 8 \
  --output /work/retimed_event_capture_bridge.spice
python3 /src/clock_pulse/generate_pulse_layout.py \
  --source /work/retimed_event_capture_bridge.spice \
  --top retimed_event_capture_bridge \
  --output /work/retimed_event_capture_bridge_layout.tcl
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /work/retimed_event_capture_bridge_layout.tcl > /work/layout.log 2>&1
klayout -b -r /src/clock_pulse_hclk_window_probe/render_event_capture_layout.py \
  > /work/render.log 2>&1
sak-drc.sh -m -w /work/drc /work/retimed_event_capture_bridge.mag \
  > /work/drc-stage.log 2>&1
sak-lvs.sh -m -w /work/lvs -s /work/retimed_event_capture_bridge.spice \
  -l /work/retimed_event_capture_bridge.mag -c retimed_event_capture_bridge \
  > /work/lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n retimed_event_capture_bridge_pex \
  -w /work/pex /work/retimed_event_capture_bridge.mag \
  > /work/pex-stage.log 2>&1
pex=/work/pex/retimed_event_capture_bridge.pex.spice
sed -i -E '1s/^\* PEX produced on .* using /\* PEX produced using /' "$pex"
grep -q '^\* PEX produced using ' "$pex"
cp "$pex" /work/retimed_event_capture_bridge.pex.spice
python3 /src/clock_pulse_hclk_window_probe/summarize_event_start_end_sr_physical.py
rc=0
python3 /src/clock_pulse_hclk_window_probe/run_event_lane_composition.py \
  --event-pex /work/retimed_event_capture_bridge.pex.spice \
  --event-physical /work/retimed-event-capture-start-end-sr-physical.json \
  --event-schematic /work/retimed_event_capture_bridge.spice \
  --event-source-revision retimed_capture_owned_start_end_sr_v7_timing_lane_core \
  --lane-pex /src/lane_rx_regenerative_capture/lane_rx_regenerative_capture.pex.spice \
  --lane-physical /src/lane_rx_regenerative_capture/physical_result.json \
  --case-ids tt:sense1_interval1_epoch0 ss_hot:sense1_interval1_epoch0 \
  --interface-debug-stages --jobs 2 \
  --work /work/lane-cases --output /work/lane-result.json || rc=$?
if [[ "$rc" -ne 0 && "$rc" -ne 1 ]]; then
  exit "$rc"
fi
