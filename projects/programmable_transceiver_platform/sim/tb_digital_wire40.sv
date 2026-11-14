// End-to-end test of the AC-1 40-bit wired boundary (S3) through pt_host_link (pad-edge DDR and
// gearboxes) and pt_digital / pt_core (40-bit core on host word clock / 4):
//   H2D: a testbench pt_dense_link_tx ("FPGA") sends an incrementing 10-bit wired payload on DDR pins;
//        pt_digital must emit it on wire_tx_data as 40-bit quads (word 0 in [9:0]), in order. The low
//        half is launched on the falling quad-clock edge before the taking rising edge, the high half
//        on that rising edge (pt_wiredtx WORD_CLK40 load timing).
//   D2H: the testbench drives wire_rx_data with an incrementing sequence of quads; a testbench
//        pt_dense_link_rx decodes the D2H frames (pins sampled mid-word) and checks the payload order.
// Clocks share one timebase (host word clock 100 MHz, wire quad clock 25 MHz) and the wired rate is
// 50 Mword/s in both directions, so the FIFOs neither overflow nor starve. Prints WIRE40_PASS.
`timescale 1ns/1ps
`include "pt_regmap_defs.svh"
module tb_digital_wire40;
 reg rst_n=1,por_n=1,hclk=0,wclk=0,sclk=0;
 always #5 hclk=~hclk;
 reg wdiv=0;
 always @(posedge hclk) begin wdiv<=!wdiv; if(wdiv) wclk<=~wclk; end  // 25 MHz, phase-locked
 // ---- FPGA side
 reg ftx_rst=1,frx_rst=1;
 reg[9:0]src=0;reg[6:0]src_count=0;wire src_pop,iq_pop;wire[9:0]h2d;
 pt_dense_link_tx fpga_tx(hclk,ftx_rst,1'b0,src,10'h000,src_count,6'd0,4'd0,8'd0,src_pop,iq_pop,h2d);
 // source produces one new word every other host clock (50 Mword/s), up to 64 buffered
 reg ph=0;
 always @(posedge hclk) begin
  ph<=~ph;
  case({ph&&src_count<64, src_pop})
   2'b10: src_count<=src_count+1'b1;
   2'b01: begin src_count<=src_count-1'b1; src<=src+1'b1; end
   default: if(src_pop) src<=src+1'b1;
  endcase
 end
 reg[9:0]d2h;wire[9:0]fdata;wire fwv,fqv,fcv,ffault,flocked;wire[3:0]fop;wire[7:0]farg;
 pt_dense_link_rx fpga_rx(hclk,frx_rst,1'b0,d2h,1'b1,1'b1,fdata,fwv,fqv,fcv,ffault,flocked,fop,farg);
 // ---- DUT
 reg[39:0]wire_rx_data=0;reg wire_rx_valid=0;reg wire_tx_request=0;
 wire[39:0]wire_tx_data;wire wire_tx_valid,wire_idle,rf_tx_valid,rf_mute,enable,mode8,host_miso,host_miso_oe;
 wire[23:0]rf_tx_sample;wire[15:0]rf_trim,wire_trim,clock_trim,status;wire[11:0]calibration_trial;
 wire[`PT_ANALOG_CFG_W-1:0]analog_cfg;wire[`PT_DEBUG_CFG_W-1:0]debug_cfg;wire[`PT_ISLAND_W-1:0]island_en,island_on;
 wire[`PT_ATB_W-1:0]atb0_sw,atb1_sw;
 wire rx_en_aux,rx_en_wclk,rx_en_wtx_ext,clk_obs_oe,wclk_obs_oe,dbg_obs0,dbg_obs0_oe,dbg_obs1,dbg_obs1_oe,wdbg_obs,wdbg_obs_oe,commit_toggle;
 // Pad-edge host link (DDR mode): forwarded H2D clock = hclk/2 centred on the FPGA words; D2H pins
 // sampled on the hclk falling edge.
 reg h2d_clk=0;always @(negedge hclk)h2d_clk<=!h2d_clk;
 wire core_clk,core_rst_n;wire[39:0]h2d_quad,d2h_quad;wire[9:0]d2h_pin;
 reg hddr=0;always @(posedge hclk)hddr<=!hddr;   // host DDR clock = word clock / 2
 pt_host_link link(.rst_n(rst_n),.mode(2'd0),.d2h_enable(1'b1),.h2d_clk(h2d_clk),.h2d_pin(h2d),.link_clk(hddr),.word_clk(hclk),
  .core_clk(core_clk),.core_rst_n(core_rst_n),.h2d_quad(h2d_quad),.d2h_quad(d2h_quad),.d2h_pin(d2h_pin),.d2h_clk_pin(),.d2h_stagger(1'b0),.d2h_oe(),
  .h2d_overflow(),.h2d_underflow());
 always @(negedge hclk)d2h<=d2h_pin;
 pt_digital dut(.rst_n(rst_n),.core_rst_n(core_rst_n),.ref_clk(1'b0),.host_sclk(sclk),.host_cs_n(1'b1),.host_mosi(1'b0),.host_miso(host_miso),
  .host_miso_oe(host_miso_oe),.host_tx_clk(core_clk),.host_rx_clk(core_clk),.wire_rx_clk(wclk),.wire_tx_clk(wclk),
  .rf_rx_clk(1'b0),.rf_tx_clk(1'b0),.h2d_quad(h2d_quad),.d2h_quad(d2h_quad),.wire_rx_data(wire_rx_data),.wire_rx_valid(wire_rx_valid),
  .wire_tx_data(wire_tx_data),.wire_tx_valid(wire_tx_valid),.wire_idle(wire_idle),.wire_tx_request(wire_tx_request),
  .rf_rx_sample(24'd0),.rf_rx_valid(1'b0),.rf_tx_sample(rf_tx_sample),.rf_tx_valid(rf_tx_valid),.rf_mute(rf_mute),
  .rf_tx_request(1'b0),.enable(enable),.mode8(mode8),.rf_trim(rf_trim),.wire_trim(wire_trim),.clock_trim(clock_trim),
  .calibration_above_target(1'b0),.calibration_trial(calibration_trial),.status(status),.por_n(por_n),.por_path(3'b0),.fault(1'b0),
  .island_pgood(6'd0),.fc_src(6'd0),.cdr_freq_locked(),.analog_status(12'd0),.wire_analog_status(13'd0),.analog_cfg(analog_cfg),
  .debug_cfg(debug_cfg),.island_en(island_en),.island_on(island_on),.atb0_sw(atb0_sw),.atb1_sw(atb1_sw),.rx_en_aux(rx_en_aux),
  .rx_en_wclk(rx_en_wclk),.rx_en_wtx_ext(rx_en_wtx_ext),.clk_obs_oe(clk_obs_oe),
  .dbg_obs0(dbg_obs0),.dbg_obs0_oe(dbg_obs0_oe),.dbg_obs1(dbg_obs1),.dbg_obs1_oe(dbg_obs1_oe),
  .commit_toggle(commit_toggle),
  .linecode(1'b0),.rx_gain(),.rx_gain_active());
 reg en=0;initial force dut.enable=en;
 // ---- wired consumer: one quad every other quad clock (50 Mword/s); check order
 integer ntx=0,nrx=0,errs=0;reg[9:0]exp_tx=0,exp_rx=0,rxw=0;
 reg tx_take=0;reg[19:0]tx_low;
 always @(posedge wclk) begin
  wire_tx_request<=en&&!wire_tx_request;
  tx_take<=wire_tx_valid&&wire_tx_request;tx_low<=wire_tx_data[19:0];
  // wired RX source: one quad every other quad clock
  wire_rx_valid<=en&&!wire_rx_valid;
  if(en&&!wire_rx_valid)begin wire_rx_data<={rxw+10'd3,rxw+10'd2,rxw+10'd1,rxw};rxw<=rxw+10'd4;end
 end
 always @(negedge wclk) if(tx_take)begin
  if({wire_tx_data[39:20],tx_low}!=={exp_tx+10'd3,exp_tx+10'd2,exp_tx+10'd1,exp_tx})begin
   errs=errs+1;if(errs<5)$display("TX quad %h expected %h",{wire_tx_data[39:20],tx_low},{exp_tx+10'd3,exp_tx+10'd2,exp_tx+10'd1,exp_tx});end
  exp_tx<=exp_tx+10'd4;ntx=ntx+1;
 end
 // The chip drops wired words that arrive before its synchronized ENABLE: the first received word
 // sets the reference, every later one must follow without gaps.
 always @(posedge hclk) if(fwv)begin
  if(nrx!=0&&fdata!==exp_rx)begin errs=errs+1;if(errs<5)$display("RX word %h expected %h",fdata,exp_rx);end
  exp_rx<=fdata+10'd1;nrx=nrx+1;
 end
 initial begin
  #1 rst_n=0;por_n=0;ftx_rst=1;frx_rst=1;#1 ftx_rst=0;frx_rst=0;#100 rst_n=1;por_n=1;#100;
  frx_rst=1;                                 // FPGA RX armed before chip TX
  @(negedge hclk) en=1;#500;                 // chip RX armed (ENABLE synchronized) before FPGA TX
  @(negedge hclk) ftx_rst=1;
  #60000;
  $display("tx quads %0d rx words %0d errs %0d fpga_locked %b fpga_fault %b core status %h",ntx,nrx,errs,flocked,ffault,dut.core_status);
  if(errs==0&&ntx>600&&nrx>2000&&flocked&&!ffault&&!dut.core_status[8]&&dut.core_status[9]&&dut.core_status[7:1]==0)
   $display("WIRE40_PASS");else $display("WIRE40_FAIL");
  $finish;
 end
endmodule
