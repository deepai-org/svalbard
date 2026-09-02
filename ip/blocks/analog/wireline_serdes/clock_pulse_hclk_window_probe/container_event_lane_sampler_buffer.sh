#!/usr/bin/env bash
set -euo pipefail
python3 /src/clock_pulse_hclk_window_probe/test_event_lane_composition.py
rc=0
python3 /src/clock_pulse_hclk_window_probe/run_event_lane_composition.py \
  --event-pex /src/clock_pulse_hclk_window_probe/event_capture.pex.spice \
  --event-physical /src/clock_pulse_hclk_window_probe/event_capture_physical_result.json \
  --lane-pex /src/lane_rx_regenerative_capture/lane_rx_regenerative_capture.pex.spice \
  --lane-physical /src/lane_rx_regenerative_capture/physical_result.json \
  --case-ids tt:sense1_interval0_epoch0 ss_hot:sense1_interval0_epoch0 \
  --sampler-clock-stages 8 24 32 --sampler-final-p-mult 32 \
  --sampler-final-n-mult 32 \
  --sampler-boost-mode on \
  --capture-clock-buffer 4 8 \
  --clock-fanout-pex /src/clock_pulse_hclk_window_probe/local_clock_fanout.pex.spice \
  --clock-fanout-physical /src/clock_pulse_hclk_window_probe/local_clock_fanout_physical.json \
  --skip-debug-stages --jobs 1 \
  --work /work/cases --output /work/result.json || rc=$?
if [[ "$rc" -ne 0 && "$rc" -ne 1 ]]; then
  exit "$rc"
fi
