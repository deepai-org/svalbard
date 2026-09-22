#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
OUT="$ROOT/scratch/transceiver-pfd-reset-phase"
mkdir -p "$OUT"
docker run --rm --platform linux/arm64 --network none --cpus 2 --memory 4g --entrypoint /bin/bash \
 -v "$ROOT/projects/programmable_transceiver_platform/analog:/screen:ro" \
 -v "$ROOT/ip/blocks/analog/wireline_serdes/pll:/vco:ro" \
 -v "$ROOT/ip/blocks/analog/wifi_80211b:/wifi:ro" \
 -v "$ROOT/scratch/transceiver-rf-ac-clock:/clock:ro" \
 -v "$ROOT/scratch/transceiver-rf-ideal-lo:/reference:ro" \
 -v "$ROOT/scratch/transceiver-divider-chain:/chain:ro" \
 -v "$ROOT/scratch/transceiver-pfd-pump-breakpoint:/baseline:ro" \
 -v "$ROOT/scratch/transceiver-closed-loop-gear:/pulse:ro" \
 -v "$ROOT/scratch/transceiver-closed-loop-pwl-reference:/pwl:ro" \
 -v "$OUT:/work" --workdir /work \
 sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305 \
 -lc 'python3 /screen/pll/pfd_reset_phase_screen.py'
