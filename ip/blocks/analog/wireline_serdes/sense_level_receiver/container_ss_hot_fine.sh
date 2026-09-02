#!/usr/bin/env bash
set -euo pipefail
python3 /src/reference_level_receiver/run_single_output_sweep.py \
  --dut /src/sense_level_receiver/sense_level_receiver.pex.spice \
  --dut-subckt sense_level_receiver_pex --environment-ids ss_hot \
  --biases 1.05 1.08 1.10 1.12 1.15 1.18 1.20 1.22 1.25 \
  --reference-offsets 0.04 0.06 0.08 0.10 0.12 0.14 0.16 \
  --work /work/cases --output /work/result.json
