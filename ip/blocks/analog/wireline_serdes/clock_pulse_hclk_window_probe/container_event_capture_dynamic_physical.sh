#!/usr/bin/env bash
set -euo pipefail
python3 /src/clock_pulse_hclk_window_probe/test_event_capture_dynamic_state.py
python3 /src/clock_pulse_hclk_window_probe/test_event_capture_dynamic_physical.py
python3 /src/clock_pulse_hclk_window_probe/compile_event_capture_dynamic_physical_source.py \
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
python3 /src/clock_pulse_hclk_window_probe/summarize_event_capture_dynamic_physical.py
rc=0
python3 /src/clock_pulse_hclk_window_probe/run_event_capture_schematic.py \
  --combined-pex /work/retimed_event_capture_bridge.pex.spice \
  --combined-schematic /work/retimed_event_capture_bridge.spice \
  --combined-physical /work/retimed-event-capture-physical.json \
  --capture-pex /src/lane/capture_2p5_fast_deserializer.pex.spice \
  --capture-physical /src/lane/capture_2p5_fast_physical_result.json \
  --environment-ids tt ss_hot \
  --control-ids sense0_interval0_epoch0 sense0_interval0_epoch1 \
    sense0_interval1_epoch0 sense1_interval0_epoch0 \
  --internal-probes --work /work/pex-cases \
  --output /work/pex-result.json || rc=$?
if [[ "$rc" -ne 0 && "$rc" -ne 1 ]]; then
  exit "$rc"
fi
lane_rc=0
python3 /src/clock_pulse_hclk_window_probe/run_event_lane_composition.py \
  --event-pex /work/retimed_event_capture_bridge.pex.spice \
  --event-physical /work/retimed-event-capture-physical.json \
  --event-schematic /work/retimed_event_capture_bridge.spice \
  --event-source-revision retimed_joint_long_6_3_active_low_dynamic_state \
  --lane-pex /src/lane_rx_regenerative_capture/lane_rx_regenerative_capture.pex.spice \
  --lane-physical /src/lane_rx_regenerative_capture/physical_result.json \
  --case-ids tt:sense1_interval0_epoch0 ss_hot:sense1_interval0_epoch0 \
  --jobs 2 --work /work/lane-cases --output /work/lane-result.json || lane_rc=$?
if [[ "$lane_rc" -ne 0 && "$lane_rc" -ne 1 ]]; then
  exit "$lane_rc"
fi
