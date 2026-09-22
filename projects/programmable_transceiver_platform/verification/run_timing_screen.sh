#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
OUT="$ROOT/scratch/transceiver-synthesis"
# Always regenerate the mapped netlist so edited RTL cannot silently use stale evidence.
bash "$ROOT/projects/programmable_transceiver_platform/verification/run_synthesis.sh"
for MODE in 0 1; do
 docker run --rm --network none --cpus 2 --memory 4g --read-only \
  --tmpfs /tmp:rw,size=512m --entrypoint /bin/sh -e PT_MODE="$MODE" \
  -v "$ROOT/projects/programmable_transceiver_platform:/src:ro" -v "$OUT:/out" \
  sha256:9253a51f5fdcc7202a164aa26274b4b95533ecdedeb7eb47d6605f5881bfef17 \
  -c 'sta -exit /src/verification/timing_screen.tcl' > "$OUT/timing-mode$MODE.log" 2>&1
done
python3 "$ROOT/projects/programmable_transceiver_platform/verification/report_timing.py" "$OUT"
