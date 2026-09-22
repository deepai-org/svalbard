#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
OUT="$ROOT/scratch/transceiver-block-rx-commit-mapping"
mkdir -p "$OUT"
docker run --rm --network none --cpus 2 --memory 4g --read-only --tmpfs /tmp:rw,size=512m --entrypoint /bin/sh -v "$ROOT/projects/programmable_transceiver_platform:/src:ro" -v "$OUT:/out" sha256:9253a51f5fdcc7202a164aa26274b4b95533ecdedeb7eb47d6605f5881bfef17 -c '
set -eu
LIB=/pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.lib
sha256sum "$LIB" > /out/library.sha256
printf "set_driving_cell gf180mcu_fd_sc_mcu7t5v0__buf_1\nset_load 5\n" > /out/abc.constr
yosys -Q -T -p "read_verilog -sv -I/src/rtl /src/rtl/pt_block_rx_commit.sv /src/rtl/pt_block_header.sv /src/rtl/pt_block_route_prefix.sv /src/rtl/pt_lane_compact.sv; synth -top pt_block_rx_commit -flatten; dfflibmap -liberty $LIB; abc -liberty $LIB -D 25600 -constr /out/abc.constr; read_liberty -lib $LIB; clean; check -assert; tee -o /out/stat.json stat -json -liberty $LIB; rename -enumerate; write_verilog -noattr /out/mapped.v; write_json /out/mapped.json" > /out/synthesis.log
sta -exit /src/verification/block_rx_commit_timing.tcl > /out/timing.log 2>&1'
