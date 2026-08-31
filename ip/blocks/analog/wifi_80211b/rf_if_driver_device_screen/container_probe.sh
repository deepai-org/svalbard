#!/usr/bin/env bash
set -euo pipefail
python3 /src/rf_if_driver_device_screen/run_device_speed_probe.py \
  --work /work/cases --output /work/device-speed-probe.json --jobs 4 \
  || test -s /work/device-speed-probe.json
