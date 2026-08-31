#!/usr/bin/env bash
set -euo pipefail
python3 /src/rf_if_source_follower_output_probe/run_source_follower_probe.py \
  --source /src/rf_if_source_follower_output_probe --work /work/cases \
  --output /work/source-follower-probe.json --jobs 4 \
  || test -s /work/source-follower-probe.json
