#!/bin/sh
# Gate-level simulation of the post-route netlist. Runs sim/tb_digital_gl.sv on
# the RTL macro and on the powered post-route netlist ($1) with the same commands.txt, twice:
# the register-file stream (fast clocks stopped) and the host-link loopback (PT_LOOPBACK).
# RTL file list = VERILOG_FILES of the hardening config; port glue = gls_ports.py (r7).
set -u
NL="$1"
SC=/pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/verilog
H=/src/verification/digital_hardening
RTL=$(python3 -c "import json;print(' '.join(f.replace('dir::','/src/') for f in json.load(open('$H/config.json'))['VERILOG_FILES']))")
DRIVEN=reset_n_pad,por_n,spi_sclk,spi_cs_n,spi_mosi,host_word_clk,h2d_clk,h2d_pin,ref_clk,wire_rx_clk,wire_tx_clk,rf_rx_clk,rf_tx_clk,ct_wclk,fc_src,fault,s_pg_wired_rx,s_pg_wired_cap,s_pg_wired_tx,s_pg_rf_rx,s_pg_rf_tx,s_pg_lod,s_pg_lo,s_pg_pll,s_pg_conv,s_pg_debug,s_pll_tx_lock,s_pll_cdr_lock,s_ref_present,s_refbuf_ready,s_adc_i_ovl,s_adc_i_b_ovl,s_adc_q_ovl,s_adc_q_b_ovl,s_adc_i_done,s_adc_i_b_done,s_adc_q_done,s_adc_q_b_done,s_detect_diff_pos,s_detect_diff_neg,s_detect_se_p,s_detect_se_n,s_wrx_slp,s_wrx_slm,s_wtx_ext_data,s_aux_present,s_wtx_ext_present
python3 $H/gls_ports.py --out . --driven $DRIVEN > ports.log 2>&1; echo "ports_rc=$?"
sha256sum $RTL /src/rtl/*.svh /src/rtl/*.vh /src/sim/tb_digital_gl.sv \
  $H/gls.sh $H/gls_check.py $H/gls_ports.py > sources.sha256
iverilog -V 2>&1 | head -1 > iverilog-version.txt
sha256sum "$NL" > netlist.sha256
for t in regfile loopback; do
  D=""; src=commands.txt
  [ $t = loopback ] && D="-DPT_LOOPBACK" && src=loopback/commands.txt
  for k in rtl gl; do
    mkdir -p $t/$k; cp $src $t/$k/commands.txt
  done
  iverilog -g2012 $D -I /src/rtl -I . -s tb_digital_gl -o $t/rtl/tb.vvp /src/sim/tb_digital_gl.sv $RTL > $t/rtl/compile.log 2>&1
  echo "${t}_rtl_compile_rc=$?"
  (cd $t/rtl && vvp -n tb.vvp > run.log 2>&1); echo "${t}_rtl_run_rc=$?"
  iverilog -g2012 $D -DFUNCTIONAL -DUSE_POWER_PINS -I /src/rtl -I . -s tb_digital_gl -o $t/gl/tb.vvp \
    $SC/primitives.v $SC/gf180mcu_fd_sc_mcu7t5v0.v "$NL" /src/sim/tb_digital_gl.sv > $t/gl/compile.log 2>&1
  echo "${t}_gl_compile_rc=$?"
  (cd $t/gl && vvp -n tb.vvp > run.log 2>&1); echo "${t}_gl_run_rc=$?"
done
