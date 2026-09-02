#!/usr/bin/env bash
set -euo pipefail
python3 /src/reference_level_receiver/run_single_output_sweep.py \
  --dut /src/sense_level_receiver/sense_sr_receiver.spice \
  --dut-subckt sense_sr_receiver --consumer-pex /src/cdr/cml_to_cmos/cml_to_cmos_fast.pex.spice \
  --environment-ids ss_hot --pulse-high-ps 582 --minimum-duty 0.50 --maximum-duty 0.90 \
  --diagnostic-nodes XCORE.SETB XCORE.RESETB XCORE.Q XCORE.QB \
  --biases 1.0 --reference-offsets 0.0 \
  --work /work/cases --output /work/result.json
