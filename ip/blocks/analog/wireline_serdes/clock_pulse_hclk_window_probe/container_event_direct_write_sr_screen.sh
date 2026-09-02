#!/bin/sh
set -eu
python3 /src/clock_pulse_hclk_window_probe/run_event_direct_write_sr_screen.py \
  --lane-pex /src/lane_rx_regenerative_capture/lane_rx_regenerative_capture.pex.spice \
  --lane-physical /src/lane_rx_regenerative_capture/physical_result.json \
  --latch-mults 2 --write-mults 8 --latch-p-widths 8 \
  --control-id sense1_interval1_epoch0 --jobs 2 \
  --work /work/cases --output /work/direct-write-sr-screen.json
