#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
OUT="$ROOT/scratch/transceiver-pdn"
mkdir -p "$OUT"
python3 - "$ROOT" <<'PY'
import hashlib,json,sys
from pathlib import Path
r=Path(sys.argv[1]);e=json.loads((r/'projects/programmable_transceiver_platform/evidence/repaired-geometry-supply-screen.json').read_text())
assert hashlib.sha256((r/'scratch/transceiver-repaired-geometry/supply-connected.odb').read_bytes()).hexdigest()==e['artifact_sha256']['supply-connected.odb']
PY
docker run --rm --network none --cpus 2 --memory 4g --read-only --tmpfs /tmp:rw,size=512m --entrypoint openroad -v "$ROOT/projects/programmable_transceiver_platform:/src:ro" -v "$ROOT/scratch/transceiver-repaired-geometry:/input:ro" -v "$OUT:/out" sha256:9253a51f5fdcc7202a164aa26274b4b95533ecdedeb7eb47d6605f5881bfef17 -no_init -exit /src/verification/pdn_screen.tcl > "$OUT/pdn.log" 2>&1
python3 "$ROOT/projects/programmable_transceiver_platform/verification/report_pdn_screen.py" "$ROOT"
