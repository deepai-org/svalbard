#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
OUT="$ROOT/scratch/transceiver-repaired-geometry"
mkdir -p "$OUT"
python3 - "$ROOT" "$OUT" <<'PY'
from pathlib import Path
import hashlib,json,shutil,sys
root,out=map(Path,sys.argv[1:]);r=json.loads((root/'projects/programmable_transceiver_platform/evidence/current-repair-screen.json').read_text())
for name,dest in [('repaired.odb','digital.odb'),('repaired.v','input.v')]:
 source=root/'scratch/transceiver-current-repair'/name
 assert hashlib.sha256(source.read_bytes()).hexdigest()==r['artifact_sha256'][name]
 shutil.copyfile(source,out/dest)
shutil.copyfile(root/'scratch/transceiver-current-placement/pdk.sha256',out/'pdk.sha256')
PY
docker run --rm --network none --cpus 2 --memory 4g --read-only --tmpfs /tmp:rw,size=512m --entrypoint openroad -v "$ROOT/projects/programmable_transceiver_platform:/src:ro" -v "$ROOT/scratch/transceiver-current-repair:/input:ro" -v "$OUT:/out" sha256:9253a51f5fdcc7202a164aa26274b4b95533ecdedeb7eb47d6605f5881bfef17 -no_init -exit /src/verification/repaired_geometry_screen.tcl > "$OUT/placement.log" 2>&1
python3 "$ROOT/projects/programmable_transceiver_platform/verification/check_placement_screen.py" "$OUT" "$ROOT/projects/programmable_transceiver_platform/evidence/current-repair-screen.json"
python3 "$ROOT/projects/programmable_transceiver_platform/verification/report_repaired_geometry.py" "$ROOT"
