#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
OUT="$ROOT/scratch/transceiver-block-capture-hold"
MAPPED="$ROOT/scratch/transceiver-block-capture-mapping"
mkdir -p "$OUT"
test -f "$MAPPED/mapped.v"
docker run --rm --network none --cpus 2 --memory 4g --read-only --tmpfs /tmp:rw,size=512m --entrypoint /bin/sh -v "$ROOT/projects/programmable_transceiver_platform:/src:ro" -v "$MAPPED:/mapped:ro" -v "$OUT:/out" sha256:9253a51f5fdcc7202a164aa26274b4b95533ecdedeb7eb47d6605f5881bfef17 -c 'sta -exit /src/verification/block_capture_hold.tcl > /out/hold.log 2>&1'
