#!/bin/sh
set -eu
LIB=/pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.lib
DELAY_OPTION=
DELAY_JSON=null
if [ -n "${PT_ABC_DELAY_PS:-}" ]; then
 case "$PT_ABC_DELAY_PS" in *[!0-9]*|0) echo 'Invalid ABC delay target' >&2; exit 2;; esac
 DELAY_OPTION="-D $PT_ABC_DELAY_PS"
 DELAY_JSON="$PT_ABC_DELAY_PS"
fi
SIZING_JSON=false
if [ "${PT_ABC_SIZING:-0}" = 1 ]; then
 printf 'set_driving_cell gf180mcu_fd_sc_mcu7t5v0__buf_1\nset_load 5\n' > /out/abc-boundary.constr
 DELAY_OPTION="$DELAY_OPTION -constr /out/abc-boundary.constr"
 SIZING_JSON=true
fi
printf '{"abc_delay_target_ps": %s, "abc_sizing": %s, "sizing_boundary_model": "buf_1 driver and 5 fF load; illustrative, not physical IO constraints"}\n' "$DELAY_JSON" "$SIZING_JSON" > /out/mapping-options.json
sha256sum "$LIB" > /out/library.sha256
yosys -Q -T -p "read_verilog -sv -I/src/rtl /src/rtl/*.sv; synth -top pt_digital -flatten; dfflibmap -liberty $LIB; abc -liberty $LIB $DELAY_OPTION; read_liberty -lib $LIB; clean; check -assert; tee -o /out/mapped-stat.json stat -json -liberty $LIB; write_verilog -noattr /out/pt_digital_mapped.v; write_json /out/pt_digital_mapped.json" > /out/synthesis.log
