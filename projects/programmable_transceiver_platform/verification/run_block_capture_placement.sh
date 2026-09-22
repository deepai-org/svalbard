#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
OUT="$ROOT/scratch/transceiver-block-capture-placement"
MAPPED="$ROOT/scratch/transceiver-block-capture-mapping"
mkdir -p "$OUT"
docker run --rm --network none --cpus 2 --memory 4g --read-only --tmpfs /tmp:rw,size=512m --entrypoint /bin/sh -v "$ROOT/projects/programmable_transceiver_platform:/src:ro" -v "$MAPPED:/mapped:ro" -v "$OUT:/out" sha256:9253a51f5fdcc7202a164aa26274b4b95533ecdedeb7eb47d6605f5881bfef17 -c 'set -eu
openroad -no_init -exit /src/verification/block_capture_place.tcl > /out/placement.log 2>&1
python3 /src/verification/block_capture_placed_timing.py'
