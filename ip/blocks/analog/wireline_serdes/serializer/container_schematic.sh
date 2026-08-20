#!/usr/bin/env bash
set -euo pipefail
cd /work
python3 /src/serializer/run_composed.py --source /src --work /work/sim \
  --output /work/serializer-schematic-result.json --jobs 4
