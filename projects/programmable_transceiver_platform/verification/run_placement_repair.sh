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
REPAIR="$ROOT/scratch/transceiver-placement-repair"
mkdir -p "$REPAIR"
docker run --rm --network none --cpus 2 --memory 4g --read-only --tmpfs /tmp:rw,size=512m \
 --entrypoint openroad -v "$ROOT/projects/programmable_transceiver_platform:/src:ro" \
 -v "$OUT:/input:ro" -v "$REPAIR:/out" \
 sha256:9253a51f5fdcc7202a164aa26274b4b95533ecdedeb7eb47d6605f5881bfef17 \
 -no_init -exit /src/verification/repair_placement_screen.tcl > "$REPAIR/repair.log" 2>&1
python3 "$ROOT/projects/programmable_transceiver_platform/verification/report_placement_repair.py" "$ROOT"
