#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
OUT="$ROOT/scratch/transceiver-pdn-geometry"
mkdir -p "$OUT"
docker run --rm --network none --cpus 2 --memory 4g --read-only --tmpfs /tmp:rw,size=512m --entrypoint openroad -v "$ROOT/projects/programmable_transceiver_platform:/src:ro" -v "$ROOT/scratch/transceiver-pdn:/input:ro" -v "$OUT:/out" sha256:9253a51f5fdcc7202a164aa26274b4b95533ecdedeb7eb47d6605f5881bfef17 -no_init -exit /src/verification/pdn_geometry_dump.tcl > "$OUT/dump.log" 2>&1
python3 "$ROOT/projects/programmable_transceiver_platform/verification/check_pdn_geometry.py" "$ROOT"
