#!/usr/bin/env bash
set -euo pipefail
python3 /src/reference_level_receiver/compile_variant.py --variant sense_fast \
  --top sense_fast_receiver --spice-output /work/sense_fast_receiver.spice \
  --layout-output /work/sense_fast_layout.tcl --manifest-output /work/manifest.json
python3 /src/reference_level_receiver/run_single_output_sweep.py \
  --dut /work/sense_fast_receiver.spice --dut-subckt sense_fast_receiver \
  --environment-ids ss_hot --biases 0.9 1.0 1.08 1.15 1.20 1.30 1.40 \
  --reference-offsets 0.0 0.05 0.10 0.15 0.20 0.25 0.30 \
  --work /work/cases --output /work/result.json
