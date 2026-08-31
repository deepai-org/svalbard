#!/usr/bin/env bash
set -euo pipefail
python3 /src/capture_clock_bridge/run_bridge_screen.py \
  --source /src \
  --capture-pex /src/lane/capture_2p5_fast_deserializer.pex.spice \
  --capture-physical /src/lane/capture_2p5_fast_physical_result.json \
  --work /work/screen --output /work/result.json
