#!/usr/bin/env bash
set -euo pipefail
python3 /src/capture_clock_bridge_drive_probe/run_drive_probe.py \
  --source /src \
  --capture-pex /src/lane/capture_2p5_fast_deserializer.pex.spice \
  --capture-physical /src/lane/capture_2p5_fast_physical_result.json \
  --work /work/cases --output /work/drive-probe.json --jobs 4 \
  || test -s /work/drive-probe.json
