#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
OUT="$ROOT/scratch/transceiver-placement"
mkdir -p "$OUT"
python3 - "$ROOT" "$OUT" <<'PY'
from pathlib import Path
import hashlib,json,sys,shutil
root,out=map(Path,sys.argv[1:])
source=root/'scratch/transceiver-delay-mapping-sized/buffered/pt_digital_mapped.v'
report=json.loads((root/'projects/programmable_transceiver_platform/evidence/delay-sized-screen.json').read_text())
assert hashlib.sha256(source.read_bytes()).hexdigest()==report['area_screen']['mapped_netlist_sha256'],'netlist differs from characterized sizing candidate'
proof=json.loads((root/'projects/programmable_transceiver_platform/evidence/mapping-equivalence.json').read_text())
assert hashlib.sha256(source.with_suffix('.json').read_bytes()).hexdigest()==proof['gate_sha256'],'netlist JSON differs from proven candidate'
shutil.copyfile(source,out/'input.v')
PY
docker run --rm --network none --cpus 2 --memory 4g --read-only --tmpfs /tmp:rw,size=512m \
 --entrypoint /bin/sh -v "$ROOT/projects/programmable_transceiver_platform:/src:ro" -v "$OUT:/out" \
 sha256:9253a51f5fdcc7202a164aa26274b4b95533ecdedeb7eb47d6605f5881bfef17 -c '
 set -eu
 BASE=/pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0
 sha256sum "$BASE/techlef/gf180mcu_fd_sc_mcu7t5v0__nom.tlef" "$BASE/lef/gf180mcu_fd_sc_mcu7t5v0.lef" "$BASE/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.lib" > /out/pdk.sha256
 openroad -no_init -exit /src/verification/placement_screen.tcl > /out/placement.log 2>&1'
python3 "$ROOT/projects/programmable_transceiver_platform/verification/check_placement_screen.py" "$OUT"
