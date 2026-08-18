#!/usr/bin/env bash
set -euo pipefail
python3 /src/run_dc.py --source /src --work /work/schematic-dc --output /work/schematic-dc.json --jobs 4
