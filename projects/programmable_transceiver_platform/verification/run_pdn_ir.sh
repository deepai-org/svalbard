#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
python3 - "$ROOT" <<'PY'
from pathlib import Path
import hashlib,json,sys
r=Path(sys.argv[1]);e=json.loads((r/'projects/programmable_transceiver_platform/evidence/digital-pdn-screen.json').read_text())
assert hashlib.sha256((r/'scratch/transceiver-pdn/digital-pdn.odb').read_bytes()).hexdigest()==e['artifact_sha256']['digital-pdn.odb']
PY
for LOAD in 0 24 48; do
 OUT="$ROOT/scratch/transceiver-pdn-ir$LOAD"
 mkdir -p "$OUT"
 docker run --rm --network none --cpus 2 --memory 4g --read-only --tmpfs /tmp:rw,size=512m --entrypoint openroad -e PT_CURRENT_MA="$LOAD" -v "$ROOT/projects/programmable_transceiver_platform:/src:ro" -v "$ROOT/scratch/transceiver-pdn:/input:ro" -v "$OUT:/out" sha256:9253a51f5fdcc7202a164aa26274b4b95533ecdedeb7eb47d6605f5881bfef17 -no_init -exit /src/verification/pdn_ir_screen.tcl > "$OUT/ir.log" 2>&1
done
python3 "$ROOT/projects/programmable_transceiver_platform/verification/check_pdnsim_loads.py" "$ROOT"
python3 "$ROOT/projects/programmable_transceiver_platform/verification/solve_pdn_resistance.py" "$ROOT"
