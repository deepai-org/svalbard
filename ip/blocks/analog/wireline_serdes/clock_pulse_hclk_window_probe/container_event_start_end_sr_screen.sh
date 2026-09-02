#!/bin/sh
set -eu
python3 /src/clock_pulse_hclk_window_probe/run_event_start_end_sr_screen.py \
  --lane-pex /src/lane_rx_regenerative_capture/lane_rx_regenerative_capture.pex.spice \
  --lane-physical /src/lane_rx_regenerative_capture/physical_result.json \
  --latch-mults 2 --pre-mults 4 --output-mults 8 --set-mults 8 \
  --control-id sense1_interval1_epoch0 \
  --jobs 2 --work /work/cases --output /work/start-end-sr-screen.json
