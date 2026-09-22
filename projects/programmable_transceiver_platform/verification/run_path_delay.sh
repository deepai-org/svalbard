#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
OUT="$ROOT/scratch/transceiver-path-delay"
mkdir -p "$OUT"
for PT_CASE in 0 1; do
 docker run --rm --network none --cpus 2 --memory 4g --read-only --tmpfs /tmp:rw,size=512m --entrypoint openroad -e PT_ESTIMATE="$PT_CASE" -v "$ROOT/projects/programmable_transceiver_platform:/src:ro" -v "$ROOT/scratch/transceiver-placement-repair:/input:ro" sha256:9253a51f5fdcc7202a164aa26274b4b95533ecdedeb7eb47d6605f5881bfef17 -no_init -exit /src/verification/path_delay_screen.tcl > "$OUT/rc$PT_CASE.log" 2>&1
done
python3 "$ROOT/projects/programmable_transceiver_platform/verification/report_path_delay.py" "$ROOT"
