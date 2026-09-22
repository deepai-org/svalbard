#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
VARIANT="${1:-baseline}"
case "$VARIANT" in baseline|replay) ;; *) exit 2 ;; esac
OUT="$ROOT/scratch/transceiver-sar-command-$VARIANT"
mkdir "$OUT"
docker run --rm --platform linux/arm64 --network none --cpus 1 --memory 4g --entrypoint /bin/bash \
 -v "$ROOT/projects/programmable_transceiver_platform/analog:/screen:ro" \
 -v "$ROOT/ip/blocks/analog/wifi_80211b:/wifi:ro" \
 -v "$ROOT/scratch/transceiver-sar-command-replay-prepared:/prepared:ro" \
 -v "$OUT:/work" --workdir /work \
 sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305 \
 -lc "python3 /screen/adc/sar_command_replay.py $VARIANT"
