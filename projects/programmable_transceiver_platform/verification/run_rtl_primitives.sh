#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
OUT="$ROOT/scratch/transceiver-rtl-primitives"
mkdir -p "$OUT"
docker run --rm --network none --cpus 2 --memory 4g --read-only --tmpfs /tmp:rw,size=512m --entrypoint /bin/sh -v "$ROOT/projects/programmable_transceiver_platform:/src:ro" -v "$OUT:/out" "${SVALBARD_DIGITAL_IMAGE:-sha256:9253a51f5fdcc7202a164aa26274b4b95533ecdedeb7eb47d6605f5881bfef17}" -c '
set -eu
python3 /src/verification/generate_crc.py --check
yosys -Q -T -p "read_verilog -sv -I/src/rtl /src/sim/crc_equivalence.sv; prep -top crc_equivalence; sat -verify -prove equal 1 -show-inputs" > /out/crc-equivalence.log
iverilog -g2012 -s tb_helpers -o /out/helpers /src/rtl/pt_helpers.sv /src/sim/tb_helpers.sv
vvp /out/helpers
iverilog -g2012 -s tb_sync_fifo_flags -o /out/test /src/rtl/pt_fifo.sv /src/sim/tb_sync_fifo_flags.sv
vvp /out/test
python3 /src/verification/fifo_flags_negative_control.py'
