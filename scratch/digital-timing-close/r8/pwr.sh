#!/bin/bash
# r8/pwr.sh <chip>: routed netlist + SPEF of the kept run, tt_025C_3v30: report_power (activity 0.1 on data, clocks 1/edge)
# and register count per clock domain. Output scratch/digital-timing-close/pwr9/<chip>.log
cd /home/ubuntu/svalbard; C=$1; R=$PWD/scratch/digital_hardening-$C/design/runs/${C^^}/final; O=$PWD/scratch/digital-timing-close/pwr9
P=$PWD/projects/programmable_transceiver_platform
cat > $O/$C.tcl <<T
read_liberty /pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.lib
read_verilog /r/nl/pt_digital_macro.nl.v
link_design pt_digital_macro
set ::env(DESIGN_DIR) /src/integration
read_sdc /src/integration/pt_digital_macro.sdc
read_spef /r/spef/nom/pt_digital_macro.nom.spef
set_power_activity -global -activity 0.1
report_power
foreach c [all_clocks] { puts "REGS [get_name \$c] [llength [all_registers -clock \$c]] period [get_property \$c period]" }
T
docker run --rm --name dig-$C-pwr --network none --cpus 1 --memory 8g -e PT_CHIP=$C -v $P:/src:ro -v $R:/r:ro -v $O:/o --entrypoint bash svalbard/librelane-gf180-guarded:2026.11 -lc "sta -no_init -exit /o/$C.tcl" > $O/$C.log 2>&1
grep -A8 "^Group" $O/$C.log; grep "^REGS" $O/$C.log | sort -k3 -n -r | head -20
