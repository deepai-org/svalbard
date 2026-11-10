#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
OUT="$ROOT/scratch/transceiver-rtl-primitives"
mkdir -p "$OUT"
docker run --rm --network none --cpus 2 --memory 4g --read-only --tmpfs /tmp:rw,size=512m --entrypoint /bin/sh -v "$ROOT/projects/programmable_transceiver_platform:/src:ro" -v "$OUT:/out" "${SVALBARD_DIGITAL_IMAGE:-sha256:b60278092f08c0a42fa93ed640d15d84eec53d7799790962781157ec34ceff43}" -c '
set -eu
iverilog -g2012 -s tb_helpers -o /out/helpers /src/rtl/pt_helpers.sv /src/sim/tb_helpers.sv
vvp /out/helpers
iverilog -g2012 -s tb_sync_fifo_flags -o /out/test /src/rtl/pt_fifo.sv /src/sim/tb_sync_fifo_flags.sv
vvp /out/test
python3 /src/verification/fifo_flags_negative_control.py'
