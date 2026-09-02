#!/usr/bin/env bash
set -euo pipefail
python3 /src/reference_level_receiver/run_envelope_matrix.py \
  --source /src/clock_pulse \
  --pex /src/reference_level_receiver/reference_level_receiver.pex.spice \
  --work /work/cases --output /work/parent-envelope.json
