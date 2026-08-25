#!/usr/bin/env bash
set -euo pipefail
python3 /src/clock_pulse/run_pulse_generator.py \
  --source /src/clock_pulse --work /work/pulse-probe-cases \
  --output /work/pulse-probe-result.json \
  --environment tt --tap-code 0,8,9 \
  || test -s /work/pulse-probe-result.json
