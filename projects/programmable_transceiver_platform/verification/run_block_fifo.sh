#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
OUT="$ROOT/scratch/transceiver-block-fifo"
mkdir -p "$OUT"
docker run --rm --network none --cpus 2 --memory 4g --read-only --tmpfs /tmp:rw,size=512m --entrypoint /bin/sh -v "$ROOT/projects/programmable_transceiver_platform:/src:ro" -v "$OUT:/out" sha256:9253a51f5fdcc7202a164aa26274b4b95533ecdedeb7eb47d6605f5881bfef17 -c '
set -eu
iverilog -g2012 -s tb_block_fifo -o /out/test /src/rtl/pt_fifo.sv /src/rtl/pt_block_fifo.sv /src/sim/tb_block_fifo.sv
vvp /out/test
python3 /src/verification/block_fifo_negative.py'
