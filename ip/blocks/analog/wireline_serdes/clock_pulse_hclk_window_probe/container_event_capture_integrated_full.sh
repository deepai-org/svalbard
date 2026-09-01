#!/usr/bin/env bash
set -euo pipefail
python3 /src/clock_pulse_hclk_window_probe/test_event_capture_integrated_state.py
python3 /src/clock_pulse_hclk_window_probe/compile_event_capture_integrated_state.py \
  --output /work/source.spice
rc=0
python3 /src/clock_pulse_hclk_window_probe/run_event_capture_schematic.py \
  --source /work/source.spice \
  --bridge /src/clock_pulse_hclk_window_probe/event_capture_bridge_direct_end_rebalanced.spice \
  --capture-pex /src/lane/capture_2p5_fast_deserializer.pex.spice \
  --capture-physical /src/lane/capture_2p5_fast_physical_result.json \
  --work /work/cases --output /work/result.json || rc=$?
if [[ "$rc" -ne 0 && "$rc" -ne 1 ]]; then
  exit "$rc"
fi
