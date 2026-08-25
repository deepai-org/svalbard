#!/usr/bin/env bash
set -euo pipefail
python3 /src/clock_pulse/run_pulse_generator.py \
  --source /src/clock_pulse --work /work/pulse-cases \
  --output /work/pulse-result.json \
  --tap-code 0,10,11 --tap-code 1,8,9 \
  --tap-code 0,8,9 --tap-code 2,8,9
