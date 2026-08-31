#!/usr/bin/env bash
set -euo pipefail

# Fresh pulse extraction is required: this chain must never quietly reuse a
# nominal PEX deck after the pulse source or its generated geometry changed.
/src/clock_pulse/container_pulse_extract.sh
pulse_pex=/work/pex/clock_pulse_generator.pex.spice
sed -i -E '1s/^\* PEX produced on .* using /\* PEX produced using /' "$pulse_pex"
python3 /src/pulse_bridge_lane/check_pulse_extract.py \
  --drc-log /work/drc-stage.log --lvs-log /work/lvs-stage.log --pex "$pulse_pex" \
  --schematic /src/clock_pulse/clock_pulse_generator.spice \
  --layout-generator /src/clock_pulse/generate_pulse_layout.py \
  --output /work/pulse-physical.json
python3 /src/pulse_bridge_lane/run_pulse_bridge_lane.py \
  --source /src --pulse-pex "$pulse_pex" --pulse-physical /work/pulse-physical.json \
  --bridge-pex /src/capture_clock_bridge/capture_clock_bridge.pex.spice \
  --bridge-physical /src/capture_clock_bridge/physical_result.json \
  --lane-pex /src/lane_rx_regenerative_capture/lane_rx_regenerative_capture.pex.spice \
  --lane-physical /src/lane_rx_regenerative_capture/physical_result.json \
  --work /work/screen --output /work/result.json
cp "$pulse_pex" /work/pulse-bridge-lane-pulse.pex.spice
