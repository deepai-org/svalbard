#!/usr/bin/env bash
set -euo pipefail
cd /work
python3 /src/serializer/run_integrated_tx.py --source /src \
  --work /work/integrated-1p25 --output /work/integrated-tx-1p25-result.json \
  --rate 1.25e9 --jobs 4
python3 /src/serializer/run_integrated_tx.py --source /src \
  --work /work/integrated-2p5 --output /work/integrated-tx-2p5-result.json \
  --rate 2.5e9 --jobs 4
