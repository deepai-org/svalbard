#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
OUT="$ROOT/scratch/transceiver-reference-load-startup-full"
mkdir -p "$OUT"
docker run --rm --platform linux/arm64 --network none --cpus 2 --memory 4g --entrypoint /bin/bash \
 -v "$ROOT/projects/programmable_transceiver_platform/analog:/screen:ro" \
 -v "$ROOT/ip/blocks/analog/wifi_80211b:/wifi:ro" \
 -v "$ROOT/scratch/transceiver-reference-load-startup-prepared:/baseline:ro" \
 -v "$ROOT/scratch/transceiver-adc-reference-current-prepared:/origin:ro" \
 -v "$OUT:/work" --workdir /work \
 sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305 \
 -lc 'python3 /screen/reference/measured_load_replay.py'
