#!/usr/bin/env bash
set -euo pipefail

# Regenerate the pulse PEX first.  The diagnostic cannot silently test a
# differently extracted leaf than the composed boundary screen.
/src/clock_pulse/container_pulse_extract.sh
pulse_pex=/work/pex/clock_pulse_generator.pex.spice
sed -i -E '1s/^\* PEX produced on .* using /\* PEX produced using /' "$pulse_pex"
python3 /src/pulse_bridge_lane/check_pulse_extract.py \
  --drc-log /work/drc-stage.log --lvs-log /work/lvs-stage.log --pex "$pulse_pex" \
  --schematic /src/clock_pulse/clock_pulse_generator.spice \
  --layout-generator /src/clock_pulse/generate_pulse_layout.py \
  --output /work/pulse-physical.json
python3 /src/pulse_bridge_lane/run_ff_cold_load_probe.py \
  --pulse-pex "$pulse_pex" --pulse-physical /work/pulse-physical.json \
  --bridge-pex /src/capture_clock_bridge/capture_clock_bridge.pex.spice \
  --bridge-physical /src/capture_clock_bridge/physical_result.json \
  --lane-pex /src/lane_rx_regenerative_capture/lane_rx_regenerative_capture.pex.spice \
  --lane-physical /src/lane_rx_regenerative_capture/physical_result.json \
  --work /work/load-probe --output /work/load-probe-result.json
