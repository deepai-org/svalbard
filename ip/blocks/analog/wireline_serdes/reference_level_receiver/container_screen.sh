#!/usr/bin/env bash
set -euo pipefail
python3 /src/reference_level_receiver/run_screen.py \
  --source /src/clock_pulse \
  --dut-source /src/reference_level_receiver/reference_level_receiver.spice \
  --dut-subckt reference_level_receiver --reference-input --vbias 1.15 \
  --work /work/cases --output /work/reference-level-receiver.json
