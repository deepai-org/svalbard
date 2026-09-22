#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
OUT="$ROOT/scratch/transceiver-tx-stage-compare"
mkdir -p "$OUT"
python3 - "$ROOT" "$OUT" <<'PYREF'
from pathlib import Path
import sys
root,out=map(Path,sys.argv[1:])
s=(root/'projects/programmable_transceiver_platform/evidence/experiments/tx-before-stage.sv').read_text()
(out/'reference.sv').unlink(missing_ok=True)
(out/'reference.sv').write_text(s.replace('module pt_stream_tx(', 'module pt_stream_tx_reference('))
PYREF
docker run --rm --network none --cpus 2 --memory 4g --read-only --tmpfs /tmp:rw,size=512m --entrypoint /bin/sh -v "$ROOT/projects/programmable_transceiver_platform:/src:ro" -v "$OUT:/out" sha256:9253a51f5fdcc7202a164aa26274b4b95533ecdedeb7eb47d6605f5881bfef17 -c '
set -eu
iverilog -g2012 -I/src/rtl -s tb_tx_stage_compare -o /out/compare /src/rtl/pt_stream_tx.sv /out/reference.sv /src/sim/tb_tx_stage_compare.sv
vvp /out/compare'
