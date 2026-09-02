#!/usr/bin/env bash
set -euo pipefail
python3 /src/reference_level_receiver/run_single_output_sweep.py \
  --dut /src/sense_level_receiver/sense_cmos_receiver.spice \
  --dut-subckt sense_cmos_receiver --consumer-pex /src/cdr/cml_to_cmos/cml_to_cmos_fast.pex.spice \
  --environment-ids ss_hot --pulse-high-ps 582 \
  --biases 1.0 --reference-offsets 0.0 \
  --work /work/cases --output /work/result.json
