#!/bin/bash
# r8/sdcchk.sh <chip> <netlist dir>: read the SDC on a synthesized netlist of one chip (OpenSTA, ss lib), report errors/warnings.
cd /home/ubuntu/svalbard; C=$1; D=$(cd $2 && pwd); P=$PWD/projects/programmable_transceiver_platform
O=$PWD/scratch/digital-timing-close/sdcchk; mkdir -p $O
cat > $O/chk_$C.tcl <<T
read_liberty /src/verification/digital_hardening/liberty/gf180mcu_fd_sc_mcu7t5v0__ss_032C_3v15.lib
read_verilog /nl/pt_digital_macro.nl.v
link_design pt_digital_macro
set ::env(DESIGN_DIR) /src/integration
read_sdc /src/integration/pt_digital_macro.sdc
report_checks -group_path_count 1 -format end
puts SDC_OK
T
docker run --rm --network none --cpus 1 --memory 6g -e PT_CHIP=$C -e OMP_NUM_THREADS=1 -v $P:/src:ro -v $D:/nl:ro -v $O:/o --entrypoint bash svalbard/librelane-gf180-guarded:2026.11 -lc "sta -no_init -exit /o/chk_$C.tcl" > $O/chk_$C.log 2>&1
grep -n "Error\|ERROR\|SDC_OK\|Warning" $O/chk_$C.log | head -30
