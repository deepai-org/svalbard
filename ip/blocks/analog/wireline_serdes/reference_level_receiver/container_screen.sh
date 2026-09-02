#!/usr/bin/env bash
set -euo pipefail
python3 /src/reference_level_receiver/run_bias_sweep.py \
  --source /src/clock_pulse \
  --dut-source /src/reference_level_receiver/reference_level_receiver.spice \
  --dut-subckt reference_level_receiver \
  --work /work/cases --output /work/reference-level-receiver.json \
  --biases 0.85 0.90 1.00 1.08 1.20 1.40
