#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
OUT="$ROOT/scratch/transceiver-placement"
python3 - "$ROOT" <<'PY'
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1]);r=json.loads((root/'projects/programmable_transceiver_platform/evidence/digital-placement-screen.json').read_text())
assert hashlib.sha256((root/'scratch/transceiver-placement/digital.odb').read_bytes()).hexdigest()==r['artifact_sha256']['digital.odb'],'placement differs from retained evidence'
PY
for ESTIMATE in 0 1; do
 docker run --rm --network none --cpus 2 --memory 4g --read-only --tmpfs /tmp:rw,size=512m \
  --entrypoint openroad -e PT_ESTIMATE="$ESTIMATE" \
  -v "$ROOT/projects/programmable_transceiver_platform:/src:ro" -v "$OUT:/out" \
  sha256:9253a51f5fdcc7202a164aa26274b4b95533ecdedeb7eb47d6605f5881bfef17 \
  -no_init -exit /src/verification/placed_timing_screen.tcl > "$OUT/timing-rc$ESTIMATE.log" 2>&1
done
python3 "$ROOT/projects/programmable_transceiver_platform/verification/report_placed_timing.py" "$OUT"
