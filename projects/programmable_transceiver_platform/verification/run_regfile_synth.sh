#!/usr/bin/env bash
# Rough GF180 synthesis size of the SPI control path (pt_mgmt = pt_spi + generated
# pt_regfile) with the LibreLane GF180 canary image (yosys + gf180mcuD 7-track 5V0 cells,
# typical 25 C / 3.3 V Liberty: the closest provided corner to the 27 C +/-5 C,
# 3.15-3.35 V operating window). No network. Results: scratch/pt_regfile/synth/.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
PROJ="$ROOT/projects/programmable_transceiver_platform"
OUT="$ROOT/scratch/pt_regfile/synth"
IMAGE="${SVALBARD_DIGITAL_IMAGE:-${SYNTH_IMAGE:-svalbard/librelane-gf180-canary:2026.08}}"
rm -rf "$OUT"; mkdir -p "$OUT"
docker image inspect "$IMAGE" --format '{{.Id}} {{.Architecture}}' > "$OUT/image.txt"
docker run --rm --network none --cpus 4 --memory 8g --entrypoint bash \
  -v "$PROJ:/src:ro" -v "$OUT:/out" "$IMAGE" -lc '
  set -e
  LIB=/pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.lib
  yosys -V > /out/yosys_version.txt
  yosys -q -l /out/synth.log -p "
    read_verilog -sv /src/rtl/pt_spi.sv /src/rtl/pt_regfile.sv
    synth -top pt_mgmt -flatten
    dfflibmap -liberty $LIB
    abc -liberty $LIB
    opt_clean
    tee -o /out/stat.txt stat -liberty $LIB
    write_verilog -noattr /out/pt_mgmt_gf180.v"'
cat "$OUT/image.txt" "$OUT/yosys_version.txt"
grep -E "Number of cells|Chip area|dff|DFF" "$OUT/stat.txt" | head -20
