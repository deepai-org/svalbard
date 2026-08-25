#!/usr/bin/env bash
set -euo pipefail
python3 /src/clock_pulse/run_pulse_generator.py \
  --source /src/clock_pulse --work /work/pulse-cases \
  --output /work/pulse-result.json \
  --tap-code 1,5,7 --tap-code 2,8,9 \
  --tap-code 1,7,8 --tap-code 2,10,11
