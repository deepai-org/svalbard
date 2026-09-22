#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
SRC="$ROOT/scratch/transceiver-synthesis"
OUT="$ROOT/scratch/transceiver-buffering"
mkdir -p "$OUT"
bash "$ROOT/projects/programmable_transceiver_platform/verification/run_synthesis.sh"
python3 "$ROOT/projects/programmable_transceiver_platform/verification/buffer_netlist.py" "$SRC/pt_digital_mapped.json" "$OUT/buffered.json"
cp "$SRC/library.sha256" "$SRC/mapping-options.json" "$OUT/"
docker run --rm --network none --cpus 2 --memory 4g --read-only --tmpfs /tmp:rw,size=512m \
 --entrypoint /bin/sh -v "$ROOT/projects/programmable_transceiver_platform:/src:ro" -v "$OUT:/out" \
 sha256:9253a51f5fdcc7202a164aa26274b4b95533ecdedeb7eb47d6605f5881bfef17 -c '
 LIB=/pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.lib
 yosys -Q -T -p "read_json /out/buffered.json; hierarchy -top pt_digital; check -assert; tee -o /out/mapped-stat.json stat -json -liberty $LIB; write_verilog -noattr /out/pt_digital_mapped.v; write_json /out/pt_digital_mapped.json" > /out/buffer-check.log
 for mode in 0 1; do PT_MODE=$mode sta -exit /src/verification/timing_screen.tcl > /out/timing-mode$mode.log 2>&1; done'
python3 "$ROOT/projects/programmable_transceiver_platform/verification/report_synthesis.py" "$OUT"
python3 "$ROOT/projects/programmable_transceiver_platform/verification/report_timing.py" "$OUT"
