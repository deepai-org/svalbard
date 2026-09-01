#!/usr/bin/env bash
set -euo pipefail
python3 /src/clock_pulse_hclk_window_probe/test_recovery_contract.py
python3 /src/clock_pulse_hclk_window_probe/test_event_capture.py
python3 /src/clock_pulse_hclk_window_probe/compile_event_capture_source.py \
  --output /work/retimed_capture_events.spice
event_rc=0
python3 /src/clock_pulse_hclk_window_probe/run_event_capture_schematic.py \
  --source /work/retimed_capture_events.spice \
  --bridge /src/clock_pulse_hclk_window_probe/event_capture_bridge_direct_end_rebalanced.spice \
  --capture-pex /src/lane/capture_2p5_fast_deserializer.pex.spice \
  --capture-physical /src/lane/capture_2p5_fast_physical_result.json \
  --work /work/event-capture-cases \
  --output /work/event-capture-result.json || event_rc=$?
if [[ "$event_rc" -ne 0 && "$event_rc" -ne 1 ]]; then
  exit "$event_rc"
fi
