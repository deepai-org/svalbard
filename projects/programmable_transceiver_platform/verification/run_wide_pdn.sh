#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
P="$ROOT/projects/programmable_transceiver_platform"
GRID="$ROOT/scratch/transceiver-wide-pdn"
IR="$ROOT/scratch/transceiver-wide-pdn-ir48"
GEO="$ROOT/scratch/transceiver-wide-pdn-geometry"
mkdir -p "$GRID" "$IR" "$GEO"
python3 - "$ROOT" <<'PY'
from pathlib import Path
import hashlib,json,sys
r=Path(sys.argv[1]);e=json.loads((r/'projects/programmable_transceiver_platform/evidence/repaired-geometry-supply-screen.json').read_text())
assert hashlib.sha256((r/'scratch/transceiver-repaired-geometry/supply-connected.odb').read_bytes()).hexdigest()==e['artifact_sha256']['supply-connected.odb']
PY
IMAGE=sha256:9253a51f5fdcc7202a164aa26274b4b95533ecdedeb7eb47d6605f5881bfef17
docker run --rm --network none --cpus 2 --memory 4g --read-only --tmpfs /tmp:rw,size=512m --entrypoint openroad -v "$P:/src:ro" -v "$ROOT/scratch/transceiver-repaired-geometry:/input:ro" -v "$GRID:/out" "$IMAGE" -no_init -exit /src/verification/wide_pdn_screen.tcl > "$GRID/pdn.log" 2>&1
docker run --rm --network none --cpus 2 --memory 4g --read-only --tmpfs /tmp:rw,size=512m --entrypoint openroad -e PT_CURRENT_MA=48 -v "$P:/src:ro" -v "$GRID:/input:ro" -v "$IR:/out" "$IMAGE" -no_init -exit /src/verification/pdn_ir_screen.tcl > "$IR/ir.log" 2>&1
docker run --rm --network none --cpus 2 --memory 4g --read-only --tmpfs /tmp:rw,size=512m --entrypoint openroad -v "$P:/src:ro" -v "$GRID:/input:ro" -v "$GEO:/out" "$IMAGE" -no_init -exit /src/verification/pdn_geometry_dump.tcl > "$GEO/dump.log" 2>&1
python3 - "$GRID" <<'PY'
import hashlib,json,sys
from pathlib import Path
p=Path(sys.argv[1]);(p/'build.json').write_text(json.dumps({'artifact_sha256':{'digital-pdn.odb':hashlib.sha256((p/'digital-pdn.odb').read_bytes()).hexdigest()}}))
PY
python3 "$P/verification/check_pdn_geometry.py" "$ROOT" "$GEO" "$GRID/digital-pdn.odb" "$GRID/build.json" "$P/evidence/wide-pdn-geometry.json"
python3 "$P/verification/solve_pdn_resistance.py" "$ROOT" "$IR" "$GRID/digital-pdn.odb" "$P/evidence/wide-pdn-resistance.json"
python3 "$P/verification/report_wide_pdn.py" "$ROOT"
