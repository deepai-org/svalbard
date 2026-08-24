#!/usr/bin/env bash
set -euo pipefail
python3 /src/run_level_converter.py --source /src --work /work/cases \
  --output /work/level-converter.json
