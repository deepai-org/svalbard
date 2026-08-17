#!/usr/bin/env bash
set -euo pipefail

python3 /src/run_boundary_pvt.py --source /src --work /work/cases \
  --output /work/full-result.json --jobs 4
python3 /src/summarize_pvt.py --input /work/full-result.json \
  --dut /src/cml_phase_detector.spice --output /work/summary.json
