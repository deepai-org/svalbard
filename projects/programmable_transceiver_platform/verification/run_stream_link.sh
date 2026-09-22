#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
OUT="$ROOT/scratch/transceiver-stream-link"
mkdir -p "$OUT"
docker run --rm --network none --cpus 2 --memory 4g --read-only --tmpfs /tmp:rw,size=512m \
 --entrypoint /bin/sh -v "$ROOT/projects/programmable_transceiver_platform:/src:ro" -v "$OUT:/out" \
 sha256:9253a51f5fdcc7202a164aa26274b4b95533ecdedeb7eb47d6605f5881bfef17 -c '
 set -eu
 for mode in 0 1; do
  iverilog -g2012 -I/src/rtl -s tb_stream_link -Ptb_stream_link.MODE=$mode -o /out/link$mode /src/rtl/pt_stream*.sv /src/sim/tb_stream_link.sv
  vvp /out/link$mode
 done
 for top in pt_stream_link_rx pt_stream_link_tx; do
  yosys -Q -T -p "read_verilog -sv -I/src/rtl /src/rtl/pt_stream*.sv; hierarchy -check -top $top; proc; check -assert; stat" > /out/$top-structure.log
 done'
