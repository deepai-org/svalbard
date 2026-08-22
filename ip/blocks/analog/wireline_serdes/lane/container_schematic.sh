#!/usr/bin/env bash
set -euo pipefail
python3 /src/lane/run_lane.py --source /src --work /work/schematic \
  --output /work/result.json --jobs 4 --allow-fail
