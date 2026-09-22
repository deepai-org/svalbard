#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
SHIFT_PS=${1:--100}
case "$SHIFT_PS" in
 -100) OUT="$ROOT/scratch/transceiver-wired-phase" ;;
 -200|-300) OUT="$ROOT/scratch/transceiver-wired-phase${SHIFT_PS}ps" ;;
 *) echo "Expected phase -100, -200 or -300 ps" >&2; exit 2 ;;
esac
mkdir -p "$OUT"
docker run --rm --platform linux/arm64 --network none --cpus 2 --memory 8g \
 --env SHIFT_PS="$SHIFT_PS" --env PDK=gf180mcuD --env PDKPATH=/foss/pdks/gf180mcuD --entrypoint /bin/bash \
 -v "$ROOT/ip/blocks/analog/wireline_serdes:/src:ro" \
 -v "$ROOT/projects/programmable_transceiver_platform/analog:/screen:ro" \
 -v "$ROOT/scratch/transceiver-wired-pulse-data-gf180:/baseline:ro" \
 -v "$OUT:/work" --workdir /work \
 sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305 \
 -lc 'python3 /screen/wired_phase_screen.py --shift-ps "$SHIFT_PS"' 
