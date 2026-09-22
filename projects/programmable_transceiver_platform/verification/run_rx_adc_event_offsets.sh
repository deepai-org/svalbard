#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
OUT="$ROOT/scratch/transceiver-rx-adc-event-offsets"
if [[ "${1:-}" == "--preflight" ]]; then OUT="$OUT-preflight"; fi
if [[ "${1:-}" == "--preflight-v2" ]]; then OUT="$OUT-preflight-v2"; set -- --preflight; fi
mkdir "$OUT"
docker run --rm --platform linux/arm64 --network none --cpus 2 --memory 4g --entrypoint /bin/bash \
 -v "$ROOT/projects/programmable_transceiver_platform/analog:/screen:ro" \
 -v "$ROOT/ip/blocks/analog/wireline_serdes/pll:/vco:ro" \
 -v "$ROOT/ip/blocks/analog/wifi_80211b:/wifi:ro" \
 -v "$ROOT/scratch/transceiver-rx-adc-loading/loaded:/baseline:ro" \
 -v "$ROOT/scratch/transceiver-rx-adc-connected-prepared:/prepared:ro" \
 -v "$ROOT/scratch/transceiver-rx-adc-event-offsets-prepared:/variants:ro" \
 -v "$OUT:/work" --workdir /work \
 sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305 \
 -lc 'python3 /screen/integration/rx_adc_event_offsets.py "$@"' runner "$@"
