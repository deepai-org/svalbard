#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
OUT="$ROOT/scratch/transceiver-current-placement"
mkdir -p "$OUT"
python3 - "$ROOT" "$OUT" <<'PY'
from pathlib import Path
import hashlib,json,sys,shutil
root,out=map(Path,sys.argv[1:]);p=root/'projects/programmable_transceiver_platform'
r=json.loads((p/'evidence/fifo-flags-screen.json').read_text())['area_screen']
for name,digest in r['source_sha256'].items():
 assert hashlib.sha256((p/name).read_bytes()).hexdigest()==digest,f'current source differs: {name}'
s=root/'scratch/transceiver-fifo-flags-mapping/buffered/pt_digital_mapped.v'
assert hashlib.sha256(s.read_bytes()).hexdigest()==r['mapped_netlist_sha256']
shutil.copyfile(s,out/'input.v')
PY
IMAGE=sha256:9253a51f5fdcc7202a164aa26274b4b95533ecdedeb7eb47d6605f5881bfef17
docker run --rm --network none --cpus 2 --memory 4g --read-only --tmpfs /tmp:rw,size=512m --entrypoint /bin/sh -v "$ROOT/projects/programmable_transceiver_platform:/src:ro" -v "$OUT:/out" "$IMAGE" -c '
set -eu
BASE=/pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0
sha256sum "$BASE/techlef/gf180mcu_fd_sc_mcu7t5v0__nom.tlef" "$BASE/lef/gf180mcu_fd_sc_mcu7t5v0.lef" "$BASE/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.lib" > /out/pdk.sha256
openroad -no_init -exit /src/verification/placement_screen.tcl > /out/placement.log 2>&1'
python3 "$ROOT/projects/programmable_transceiver_platform/verification/check_placement_screen.py" "$OUT" "$ROOT/projects/programmable_transceiver_platform/evidence/fifo-flags-screen.json"
for ESTIMATE in 0 1; do
 docker run --rm --network none --cpus 2 --memory 4g --read-only --tmpfs /tmp:rw,size=512m --entrypoint openroad -e PT_ESTIMATE="$ESTIMATE" -v "$ROOT/projects/programmable_transceiver_platform:/src:ro" -v "$OUT:/out" "$IMAGE" -no_init -exit /src/verification/placed_timing_screen.tcl > "$OUT/timing-rc$ESTIMATE.log" 2>&1
done
python3 "$ROOT/projects/programmable_transceiver_platform/verification/report_placed_timing.py" "$OUT"
python3 "$ROOT/projects/programmable_transceiver_platform/verification/report_current_placement.py" "$ROOT"
