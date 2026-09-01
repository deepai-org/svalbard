#!/usr/bin/env bash
set -euo pipefail
python3 /src/clock_pulse_hclk_window_probe/test_event_edge_hold_screen.py
rc=0
python3 /src/clock_pulse_hclk_window_probe/run_event_edge_hold_screen.py \
  --lane-pex /src/lane_rx_regenerative_capture/lane_rx_regenerative_capture.pex.spice \
  --lane-physical /src/lane_rx_regenerative_capture/physical_result.json \
  --hold-mults 1 --hold-widths 0.5 --delay-mult 16 --jobs 2 \
  --work /work/cases --output /work/edge-hold-screen.json || rc=$?
if [[ "$rc" -ne 0 && "$rc" -ne 1 ]]; then
  exit "$rc"
fi
