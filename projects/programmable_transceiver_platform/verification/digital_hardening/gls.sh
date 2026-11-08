#!/bin/sh
# Gate-level simulation of the post-route netlist (canary image). Runs sim/tb_digital_gl.sv on
# the RTL macro and on the powered post-route netlist ($1) with the same commands.txt, twice:
# the register-file stream (fast clocks stopped) and the host-link loopback (PT_LOOPBACK).
set -u
NL="$1"
SC=/pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/verilog
RTL="/src/rtl/pt_digital_macro.sv /src/rtl/pt_host_link.sv /src/rtl/pt_digital.sv /src/rtl/pt_regfile.sv /src/rtl/pt_spi.sv
 /src/rtl/pt_core.sv /src/rtl/pt_fifo.sv /src/rtl/pt_pack.sv /src/rtl/pt_stream_link.sv /src/rtl/pt_stream_tx.sv
 /src/rtl/pt_stream_rx.sv /src/rtl/pt_frame.sv /src/rtl/pt_memory.sv /src/rtl/pt_pattern.sv /src/rtl/pt_helpers.sv
 /src/rtl/pt_clocktree_slow.sv /src/rtl/pt_freq_count.sv"
iverilog -V 2>&1 | head -1 > iverilog-version.txt
sha256sum "$NL" > netlist.sha256
for t in regfile loopback; do
  D=""; src=commands.txt
  [ $t = loopback ] && D="-DPT_LOOPBACK" && src=loopback/commands.txt
  for k in rtl gl; do
    mkdir -p $t/$k; cp $src $t/$k/commands.txt
  done
  iverilog -g2012 $D -I /src/rtl -s tb_digital_gl -o $t/rtl/tb.vvp /src/sim/tb_digital_gl.sv $RTL > $t/rtl/compile.log 2>&1
  echo "${t}_rtl_compile_rc=$?"
  (cd $t/rtl && vvp -n tb.vvp > run.log 2>&1); echo "${t}_rtl_run_rc=$?"
  iverilog -g2012 $D -DFUNCTIONAL -DUSE_POWER_PINS -I /src/rtl -s tb_digital_gl -o $t/gl/tb.vvp \
    $SC/primitives.v $SC/gf180mcu_fd_sc_mcu7t5v0.v "$NL" /src/sim/tb_digital_gl.sv > $t/gl/compile.log 2>&1
  echo "${t}_gl_compile_rc=$?"
  (cd $t/gl && vvp -n tb.vvp > run.log 2>&1); echo "${t}_gl_run_rc=$?"
done
