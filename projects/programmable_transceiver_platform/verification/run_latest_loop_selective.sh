#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
OUT="$ROOT/scratch/transceiver-latest-rf-loop-selective"
if [[ "${1:-}" == "--short" ]]; then OUT="$OUT-short"; fi
if [[ "${2:-}" == "--all-control" ]]; then OUT="$OUT-all-control"; fi
mkdir "$OUT"
docker run --rm --cidfile "$OUT/container.id" --platform linux/arm64 --network none --cpus 2 --memory 4g --entrypoint /bin/bash \
 -v "$ROOT/projects/programmable_transceiver_platform/analog:/screen:ro" \
 -v "$ROOT/ip/blocks/analog/wireline_serdes/pll:/vco:ro" \
 -v "$ROOT/ip/blocks/analog/wifi_80211b:/wifi:ro" \
 -v "$ROOT/scratch/transceiver-rf-ac-clock:/clock:ro" \
 -v "$ROOT/scratch/transceiver-rf-ideal-lo:/reference:ro" \
 -v "$ROOT/scratch/transceiver-divider-chain:/chain:ro" \
 -v "$ROOT/scratch/transceiver-latest-rf-loop-extended-prepared:/original:ro" \
 -v "$ROOT/scratch/transceiver-latest-rf-loop-extended:/killed:ro" \
 -v "$ROOT/scratch/transceiver-latest-rf-loop-selective-prepared:/prepared:ro" \
 -v "$OUT:/work" --workdir /work \
 sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305 \
 -lc 'python3 /screen/pll/selective_loop_screen.py "$@"' runner "$@"
