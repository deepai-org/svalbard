#!/usr/bin/env bash
# Cell area of the digital macro per chip configuration (split phase 2): yosys synthesis of pt_digital_macro with
# PT_CHIP = 1 (pt_rf), 2 (pt_wired) or 3 (both halves, the calibration against the hardened r8 macro), mapped to the
# in-window ss_032C_3v15 Liberty the hardening flow uses. No place-and-route: this sizes the outlines of
# {rf,wired}/config.json. Results: scratch/digital_hardening-synth/<PT_CHIP>/ (stat.txt, synth.log, netlist; the
# netlist of a chip configuration passes clamp_check.py --chip <chip>).
#   synth_area.sh <PT_CHIP>
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../../.." && pwd)
PROJ="$ROOT/projects/programmable_transceiver_platform"
CHIP=$1
OUT="$ROOT/scratch/digital_hardening-synth/$CHIP"; rm -rf "$OUT"; mkdir -p "$OUT"
IMAGE="${SVALBARD_DIGITAL_IMAGE:-svalbard/librelane-gf180-canary:2026.08}"
FILES=$(python3 -c "import json;print(' '.join('/src/'+f.split('::')[1] for f in json.load(open('$PROJ/verification/digital_hardening/config.json'))['VERILOG_FILES']))")
docker run --rm --network none --cpus 2 --memory 12g --entrypoint bash -v "$PROJ:/src:ro" -v "$OUT:/out" "$IMAGE" -lc "
  set -e; LIB=/src/verification/digital_hardening/liberty/gf180mcu_fd_sc_mcu7t5v0__ss_032C_3v15.lib
  yosys -V > /out/yosys_version.txt
  yosys -q -l /out/synth.log -p \"
    read_liberty -lib \$LIB
    read_verilog -sv -DSYNTHESIS -I/src/rtl $FILES
    chparam -set PT_CHIP $CHIP pt_digital_macro
    synth -top pt_digital_macro -flatten
    dfflibmap -liberty \$LIB
    abc -liberty \$LIB
    opt_clean -purge
    tee -o /out/stat.txt stat -liberty \$LIB
    write_verilog -noattr /out/pt_digital_macro.syn.v
  \""
grep -E "Chip area|Number of cells" "$OUT/stat.txt" | tail -2
