#!/usr/bin/env bash
set -euo pipefail
cd /work
python3 /src/pll/run_divider_schematic.py --source /src/pll \
  --work /work/divider-schematic-sim \
  --output /work/divider-schematic-result.json
