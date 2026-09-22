#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
OUT="$ROOT/scratch/transceiver-load-terminal-dc-grid"
mkdir "$OUT"
docker run --rm --name transceiver-load-terminal-dc-grid --platform linux/arm64 --network none --cpus 2 --memory 4g --entrypoint /bin/bash \
 -v "$ROOT/projects/programmable_transceiver_platform/analog:/screen:ro" \
 -v "$ROOT/projects/programmable_transceiver_platform/evidence/reference-load-bias-envelope.json:/input/envelope.json:ro" \
 -v "$OUT:/work" --workdir /work \
 sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305 \
 -lc 'python3 /screen/reference/load_terminal_dc_grid.py'
