#!/usr/bin/env bash
set -euo pipefail
python3 /src/rf_if_inverter_loop_driver/run_inverter_loop_probe.py \
  --source /src/rf_if_inverter_loop_driver --work /work/cases \
  --output /work/inverter-loop-probe.json --jobs 4 \
  || test -s /work/inverter-loop-probe.json
