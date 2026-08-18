#!/usr/bin/env bash
set -euo pipefail
python3 /src/run_pvt.py --source /src --work /work/schematic-pvt \
  --output /work/schematic-pvt.json --jobs 4
