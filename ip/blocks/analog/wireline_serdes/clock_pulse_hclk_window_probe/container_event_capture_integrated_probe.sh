#!/usr/bin/env bash
set -euo pipefail
python3 /src/clock_pulse_hclk_window_probe/test_event_capture_integrated_state.py
python3 /src/clock_pulse_hclk_window_probe/compile_event_capture_integrated_state.py \
  --output /work/source.spice
python3 /src/clock_pulse_hclk_window_probe/run_event_capture_integrated_probe.py \
  --source /work/source.spice \
  --bridge /src/clock_pulse_hclk_window_probe/event_capture_bridge_direct_end_rebalanced.spice \
  --capture /src/lane/capture_2p5_fast_deserializer.pex.spice \
  --work /work/cases --output /work/result.json
