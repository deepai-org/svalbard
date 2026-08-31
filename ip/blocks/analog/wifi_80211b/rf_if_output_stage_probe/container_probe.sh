#!/usr/bin/env bash
set -euo pipefail
python3 /src/rf_if_output_stage_probe/run_output_stage_probe.py \
  --source /src/rf_if_output_stage_probe --work /work/cases \
  --output /work/output-stage-probe.json --jobs 4 \
  || test -s /work/output-stage-probe.json
