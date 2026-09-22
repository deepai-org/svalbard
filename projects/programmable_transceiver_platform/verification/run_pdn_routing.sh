#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
for CASE in original wide; do
 if [ "$CASE" = original ]; then INPUT="$ROOT/scratch/transceiver-pdn"; else INPUT="$ROOT/scratch/transceiver-wide-pdn"; fi
 OUT="$ROOT/scratch/transceiver-pdn-routing-$CASE"
 mkdir -p "$OUT"
 docker run --rm --network none --cpus 2 --memory 4g --read-only --tmpfs /tmp:rw,size=512m --entrypoint openroad -v "$ROOT/projects/programmable_transceiver_platform:/src:ro" -v "$INPUT:/input:ro" -v "$OUT:/out" sha256:9253a51f5fdcc7202a164aa26274b4b95533ecdedeb7eb47d6605f5881bfef17 -no_init -exit /src/verification/pdn_routing_screen.tcl > "$OUT/routing.log" 2>&1
done
python3 "$ROOT/projects/programmable_transceiver_platform/verification/report_pdn_routing.py" "$ROOT"
