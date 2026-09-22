#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
OUT="$ROOT/scratch/transceiver-stream-rx"
mkdir -p "$OUT"
docker run --rm --network none --cpus 2 --memory 4g --read-only --tmpfs /tmp:rw,size=512m \
 --entrypoint /bin/sh -v "$ROOT/projects/programmable_transceiver_platform:/src:ro" -v "$OUT:/out" \
 sha256:9253a51f5fdcc7202a164aa26274b4b95533ecdedeb7eb47d6605f5881bfef17 -c '
 set -eu
 PYTHONDONTWRITEBYTECODE=1 python3 /src/verification/stream_vectors.py
 iverilog -g2012 -I/src/rtl -s tb_stream_rx -o /out/stream_rx /src/rtl/pt_stream_rx.sv /src/sim/tb_stream_rx.sv
 vvp /out/stream_rx
 yosys -Q -T -p "read_verilog -sv -I/src/rtl /src/rtl/pt_stream_rx.sv; hierarchy -check -top pt_stream_rx; proc; check -assert; stat" > /out/structure.log'
