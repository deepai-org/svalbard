#!/usr/bin/env bash
set -euo pipefail
python3 /src/reference_level_receiver/run_bias_sweep.py \
  --source /src/clock_pulse \
  --pex /src/reference_level_receiver/reference_level_receiver.pex.spice \
  --dut-subckt reference_level_receiver_pex \
  --pulse-high-ps 510 --source-resistance-ohm 187 \
  --load-p-f 50e-15 --load-n-f 190e-15 \
  --biases 0.85 0.9 1.0 1.08 1.2 1.4 1.6 1.8 \
  --work /work/cases --output /work/result.json
