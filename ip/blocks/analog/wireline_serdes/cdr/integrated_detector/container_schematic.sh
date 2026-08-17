#!/usr/bin/env bash
set -euo pipefail

python3 /src/integrated_detector/run_representative_pvt.py --source /src \
  --work /work/cases --output /work/result.json --jobs 4
python3 /src/integrated_detector/summarize_result.py --input /work/result.json \
  --output /work/summary.json
