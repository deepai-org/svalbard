#!/usr/bin/env bash
set -euo pipefail
python3 /src/clock_pulse_hclk_window_probe/test_event_assertion_screen.py
rc=0
python3 /src/clock_pulse_hclk_window_probe/run_event_assertion_screen.py \
  --lane-pex /src/lane_rx_regenerative_capture/lane_rx_regenerative_capture.pex.spice \
  --lane-physical /src/lane_rx_regenerative_capture/physical_result.json \
  --delay-cells 0 1 --environment-ids tt ss_hot \
  --control-id sense1_interval0_epoch0 --jobs 4 \
  --work /work/cases --output /work/assertion-screen.json || rc=$?
if [[ "$rc" -ne 0 && "$rc" -ne 1 ]]; then
  exit "$rc"
fi
