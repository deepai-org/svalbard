`timescale 1ns/1ps
`include "pt_regmap_defs.svh"
// pt_digital-level test of the P2-6 integration. wire_tx_data is looped to wire_rx_data
// (taken words only, random request stalls). ENABLE, wire_trim and debug_cfg (the
// debug.pattern fields) are forced directly; the checker status is read at the pt_mgmt
// ports (pattern_locked, pattern_lost_lock, pattern_errors_gray).
//  1 legacy: fields 0, wire_trim[15]=1 -> PRBS31, one line error counted
//  2 tx_mode PRBS7 + check_enable, check_mode 0 (= TX mode): lock, three inject 0->1
//    transitions (live level) count 3, check_clear 0->1 clears
//  3 tx_invert with check_invert locks; without check_invert never locks
//  4 user mode sends user_word; the checker (following a non-PRBS mode) stays unlocked
//  5 PRBS15 sent, check_mode PRBS15 explicitly; check_enable 0 and wire_trim 0: checker off
module tb_digital_prbs;
 reg rst_n=0,ref_clk=0,host_sclk=0,host_cs_n=1,host_mosi=0,host_tx_clk=0,host_rx_clk=0,wire_rx_clk=0,wire_tx_clk=0,rf_rx_clk=0,rf_tx_clk=0;
 reg [9:0] h2d_word=0; wire [9:0] d2h_word; reg [19:0] wire_rx_data=0; reg wire_rx_valid=0; wire [19:0] wire_tx_data;
 wire wire_tx_valid,wire_idle; reg wire_tx_request=0; reg [23:0] rf_rx_sample=0; reg rf_rx_valid=0; wire [23:0] rf_tx_sample;
 wire rf_tx_valid,rf_mute; reg rf_tx_request=0; wire enable,mode8; wire [15:0] rf_trim,wire_trim,clock_trim; reg calibration_above_target=0;
 wire [11:0] calibration_trial; wire [15:0] status; reg por_n=0,fault=0; reg [`PT_ISLAND_W-1:0] island_pgood=0; reg [11:0] analog_status=0; reg [12:0] wire_analog_status=0; reg [5:0] fc_src=0; wire cdr_freq_locked;
 wire [`PT_ANALOG_CFG_W-1:0] analog_cfg; wire [`PT_DEBUG_CFG_W-1:0] debug_cfg; wire [`PT_ISLAND_W-1:0] island_en,island_on; wire [`PT_ATB0_GRP_W-1:0] atb0_grp; wire [`PT_ATB1_GRP_W-1:0] atb1_grp; wire atb0_en,atb1_en; wire [`PT_ATB_W-1:0] atb0_sw,atb1_sw;
 wire rx_en_aux,rx_en_wclk,rx_en_wtx_ext,clk_obs_oe,wclk_obs_oe,dbg_obs0,dbg_obs0_oe,dbg_obs1,dbg_obs1_oe,wdbg_obs,wdbg_obs_oe,commit_toggle,host_miso,host_miso_oe;
 pt_digital dut(.*);
 always #4 begin wire_tx_clk=~wire_tx_clk; wire_rx_clk=~wire_rx_clk; end
 always #10 host_sclk=~host_sclk;

 reg en=0; reg [15:0] trim=0; reg [`PT_DEBUG_CFG_W-1:0] dbg=0; reg line_err=0;
 initial begin force dut.enable = en; force dut.wire_trim = trim; force dut.debug_cfg = dbg; end
 task field(input integer lsb, input integer w, input integer v); integer j; begin
  for (j=0;j<w;j=j+1) dbg[lsb+j] = (v>>j)&1; end endtask

 integer taken=0, errors=0, lockat;
 always @(posedge wire_tx_clk) begin
  wire_rx_valid <= wire_tx_valid && wire_tx_request; wire_rx_data <= wire_tx_data ^ (line_err ? 20'h00010 : 20'h00000);
  if (wire_tx_valid && wire_tx_request) taken <= taken + 1;
  if (wire_tx_valid && wire_tx_request && line_err) line_err <= 0;
 end
 task run(input integer cycles); integer k; begin
  lockat=-1;
  for (k=0;k<cycles;k=k+1) begin @(negedge wire_tx_clk); wire_tx_request = ($random % 4) != 0; if (lockat<0 && dut.pattern_locked) lockat=k; end
  @(negedge wire_tx_clk); wire_tx_request=0; repeat (300) @(negedge wire_tx_clk);
 end endtask
 task stop; begin en=0; repeat (20) @(negedge wire_tx_clk); end endtask          // quasi-static fields change only here
 task start; begin en=1; repeat (10) @(negedge wire_tx_clk); end endtask
 task chk_status(input [8*48-1:0] what, input l, input lost, input [15:0] gray); begin
  if (dut.pattern_locked!==l || dut.pattern_lost_lock!==lost || dut.pattern_errors_gray!==gray) begin errors=errors+1;
   $display("FAIL %0s: locked %b lost %b gray %h (expected %b %b %h)", what, dut.pattern_locked, dut.pattern_lost_lock, dut.pattern_errors_gray, l, lost, gray); end
  else $display("ok   %0s: locked %b lost %b gray %h, lock after %0d clocks", what, l, lost, gray, lockat);
 end endtask
 task pulse_field(input integer lsb); begin
  field(lsb,1,1); repeat (30) @(negedge wire_tx_clk); field(lsb,1,0); repeat (30) @(negedge wire_tx_clk); end endtask

 integer k; reg seen_user, other;
 initial begin
  #20 rst_n=1; por_n=1;
  // 1 legacy
  trim=16'h8000; start; run(3000); line_err=1; run(3000);
  chk_status("legacy wire_trim[15] PRBS31, 1 line error", 1, 0, 16'h0001);
  // 2 fields: PRBS7, checker follows the TX mode, inject and clear
  stop; trim=0; dbg=0; field(`PT_D_DEBUG_PATTERN__TX_MODE_LSB,3,1); field(`PT_D_DEBUG_PATTERN__CHECK_ENABLE_LSB,1,1); start;
  run(2000); chk_status("tx_mode PRBS7, check_mode follow", 1, 0, 16'h0000);
  wire_tx_request=1; pulse_field(`PT_D_DEBUG_PATTERN__INJECT_LSB); pulse_field(`PT_D_DEBUG_PATTERN__INJECT_LSB);
  pulse_field(`PT_D_DEBUG_PATTERN__INJECT_LSB); run(500);
  chk_status("3 inject transitions", 1, 0, 16'h0002);   // Gray of 3
  pulse_field(`PT_D_DEBUG_PATTERN__CHECK_CLEAR_LSB); run(200);
  chk_status("check_clear transition", 1, 0, 16'h0000);
  // 3 polarity
  stop; field(`PT_D_DEBUG_PATTERN__TX_INVERT_LSB,1,1); start; run(2000);
  chk_status("tx_invert without check_invert", 0, 0, 16'h0000);
  stop; field(`PT_D_DEBUG_PATTERN__CHECK_INVERT_LSB,1,1); start; run(2000);
  chk_status("tx_invert with check_invert", 1, 0, 16'h0000);
  // 4 user word
  stop; dbg=0; field(`PT_D_DEBUG_PATTERN__TX_MODE_LSB,3,6); field(`PT_D_DEBUG_PATTERN__USER_WORD_LSB,10,10'h2A5);
  field(`PT_D_DEBUG_PATTERN__CHECK_ENABLE_LSB,1,1); start; seen_user=0; other=0;
  for (k=0;k<400;k=k+1) begin @(negedge wire_tx_clk); wire_tx_request=1;
   if (wire_tx_valid) begin if (wire_tx_data=={10'h2A5,10'h2A5}) seen_user=1; else other=1; end end
  run(200);
  if (!seen_user || other) begin errors=errors+1; $display("FAIL user mode word: seen %b other %b", seen_user, other); end
  else $display("ok   user mode: wire_tx_data = {2A5,2A5} on every valid double word");
  chk_status("checker following user mode", 0, 0, 16'h0000);
  // 5 explicit check_mode; then everything off
  stop; dbg=0; field(`PT_D_DEBUG_PATTERN__TX_MODE_LSB,3,2); field(`PT_D_DEBUG_PATTERN__CHECK_ENABLE_LSB,1,1);
  field(`PT_D_DEBUG_PATTERN__CHECK_MODE_LSB,3,2); start; run(2000);
  chk_status("tx PRBS15, check_mode PRBS15", 1, 0, 16'h0000);
  stop; field(`PT_D_DEBUG_PATTERN__CHECK_MODE_LSB,3,1); start; run(2000);
  chk_status("tx PRBS15, check_mode PRBS7", 0, 0, 16'h0000);
  stop; field(`PT_D_DEBUG_PATTERN__CHECK_ENABLE_LSB,1,0); field(`PT_D_DEBUG_PATTERN__CHECK_MODE_LSB,3,0); start; run(1000);
  chk_status("check_enable 0, wire_trim 0", 0, 0, 16'h0000);
  if (errors==0) $display("DIGITAL_PRBS_PASS"); else $display("DIGITAL_PRBS_FAIL %0d", errors);
  $finish;
 end
 initial begin #20000000; $display("DIGITAL_PRBS_FAIL timeout"); $finish; end
endmodule
