// POR override strap (integration-plan G3, interface row DT-10): pt_digital_macro's rst_n is
// reset_n_pad AND (por_n OR por_bypass). Driven through the macro's real reset and SPI pins.
//  A  POR stuck low, strap low (unbonded default): the die stays in reset (MISO tristated, ID unreadable,
//     writes lost) -- the negative case, which is also the must-fail case of today's netlist.
//  B  POR stuck low, strap high: RESET_N alone releases the die; ID 0x5356, write/readback, por_flag
//     stuck set (visible), rst_flag clearable, RESET_N still resets, RESET_N low still blocks SPI.
//  C  healthy POR, strap low: unchanged behaviour (a POR pulse resets the die).
//  D  healthy POR, strap high: a POR pulse no longer resets, only flags (documented cost of the strap).
//  E  strap toggled while RESET_N is low: no effect; the strap alone never releases reset.
// RESET_STATUS b2 reads the strap. Every macro output is also compared against reset values while reset must hold.
// check_por_bypass.py runs this on the RTL and on mutated copies that must fail.
`timescale 1ns/1ps
`include "pt_regmap_defs.svh"
module tb_por_bypass;
 reg reset_n_pad=1,por_n=1,por_bypass=0,sclk=0,cs_n=1,mosi=0,hclk=0;
 always #3.2 hclk=~hclk;   // host word clock runs throughout: the host / core reset domains are checked too
 wire spi_miso,spi_miso_oe,d2h_oe,enable;wire[15:0]rf_trim;
 wire[`PT_ISLAND_W-1:0]island_en,island_on;
 pt_digital_macro dut(.reset_n_pad(reset_n_pad),.por_n(por_n),.por_bypass(por_bypass),.wire_linecode(1'b0),
  .spi_sclk(sclk),.spi_cs_n(cs_n),.spi_mosi(mosi),.spi_miso(spi_miso),.spi_miso_oe(spi_miso_oe),
  .host_word_clk(hclk),.h2d_clk(1'b0),.h2d_pin(10'h0),.d2h_oe(d2h_oe),
  .ref_clk(1'b0),.wire_rx_clk(1'b0),.wire_tx_clk(1'b0),.rf_rx_clk(1'b0),.rf_tx_clk(1'b0),
  .wire_rx_data(40'h0),.wire_rx_valid(1'b0),.wire_tx_request(1'b0),.rf_rx_sample(24'h0),.rf_rx_valid(1'b0),
  .rf_tx_request(1'b0),.enable(enable),.rf_trim(rf_trim),.calibration_above_target(1'b0),
  .fault(1'b0),.island_pgood(6'h0),.analog_status(12'h0),.wire_analog_status(13'h0),
  .island_en(island_en),.island_on(island_on),.wired_on_ext(1'b0),
  .ct_wclk(1'b0),.ct_ref_clk(1'b0),.ct_det_clk_in(1'b0),.ct_pll_lock(1'b0),.ct_marker(1'b0),
  .ct_cfg_det_en(1'b0),.ct_cfg_det_div(3'd0),.fc_src(6'h0));
 integer i,errors=0,checks=0;reg[31:0]frame;reg[15:0]rd;reg oe_seen;
 // Mode-0 SPI; oe_seen = MISO driven at any sampled bit of the response
 task spi(input[7:0]cmd,input[7:0]addr,input[15:0]data,output[15:0]q);
  begin
   frame={cmd,addr,data};q=0;oe_seen=0;cs_n=0;#50;
   for(i=31;i>=0;i=i-1)begin
    mosi=frame[i];#50;sclk=1;if(i<16)begin q[i]=spi_miso_oe?spi_miso:1'b0;oe_seen=oe_seen|spi_miso_oe;end #50;sclk=0;
   end
   #50;cs_n=1;mosi=0;#100;
  end
 endtask
 task expect_read(input[7:0]addr,input[15:0]want,input[8*40-1:0]what);
  begin
   spi(8'h00,addr,16'h0,rd);checks=checks+1;
   if(rd!==want||!oe_seen)begin errors=errors+1;$display("FAIL %0s: read %h = %h (oe %b), expected %h",what,addr,rd,oe_seen,want);end
  end
 endtask
 // held in reset: SPI gets no answer (MISO never driven) and every control output is at its reset level
 task expect_dead(input[8*40-1:0]what);
  begin
   spi(8'h80,8'h10,16'hBEEF,rd);                 // a write that must be lost
   spi(8'h00,8'h00,16'h0,rd);checks=checks+1;
   if(oe_seen||rd!==16'h0||spi_miso_oe||rf_trim!==16'h0||enable!==1'b0||island_en!=={`PT_ISLAND_W{1'b0}}||
      island_on!=={`PT_ISLAND_W{1'b0}}||d2h_oe!==1'b0||dut.host_rst_n!==1'b0||dut.core_rst_n!==1'b0)begin
    errors=errors+1;$display("FAIL %0s: die not held in reset (id %h oe %b rf_trim %h)",what,rd,oe_seen,rf_trim);end
  end
 endtask
 task pulse_reset;begin reset_n_pad=0;#200;reset_n_pad=1;#200;end endtask
 initial begin
  // ---- A: POR stuck low, strap low (default). RESET_N released: still in reset.
  #20;reset_n_pad=0;por_n=0;   // simulator only: give the asynchronous resets their falling edge
  #100;reset_n_pad=1;#200;
  expect_dead("A por stuck, strap low");
  pulse_reset;expect_dead("A after RESET_N pulse");
  // ---- E: strap changes while RESET_N is low do nothing; strap high with RESET_N low is still reset
  reset_n_pad=0;#100;por_bypass=1;#100;expect_dead("E strap high, RESET_N low");
  por_bypass=0;#100;por_bypass=1;#100;
  // ---- B: POR stuck low, strap high, RESET_N released
  reset_n_pad=1;#200;
  expect_read(8'h00,16'h5356,"B ID");
  // the host-link and transport-core reset domains (own synchronizers on the running host clock) are out of reset too
  checks=checks+1;if(dut.host_rst_n!==1'b1||dut.core_rst_n!==1'b1)begin errors=errors+1;$display("FAIL B host/core reset domains still held (%b %b)",dut.host_rst_n,dut.core_rst_n);end
  expect_read(8'h10,16'h0000,"B rf_trim reset value");
  spi(8'h80,8'h10,16'hA5C3,rd);expect_read(8'h10,16'hA5C3,"B rf_trim readback");
  checks=checks+1;if(rf_trim!==16'hA5C3)begin errors=errors+1;$display("FAIL B rf_trim output %h",rf_trim);end
  expect_read(8'h0D,16'h0007,"B RESET_STATUS both flags + strap bit");
  spi(8'h80,8'h0D,16'h0007,rd);expect_read(8'h0D,16'h0005,"B por_flag stuck (POR low), rst_flag cleared, strap bit read-only");
  pulse_reset;
  expect_read(8'h10,16'h0000,"B RESET_N resets with strap high");
  expect_read(8'h0D,16'h0007,"B rst_flag set again");
  reset_n_pad=0;#100;expect_dead("B RESET_N low blocks SPI");reset_n_pad=1;#200;
  // strap removed with POR still low: back in reset (level, no latch)
  spi(8'h80,8'h10,16'h1234,rd);por_bypass=0;#100;expect_dead("B strap removed");
  // ---- C: healthy POR, strap low: normal operation, POR pulse resets
  por_n=1;#200;
  expect_read(8'h00,16'h5356,"C ID");
  spi(8'h80,8'h0D,16'h0003,rd);expect_read(8'h0D,16'h0000,"C flags cleared");
  spi(8'h80,8'h10,16'h0F0F,rd);expect_read(8'h10,16'h0F0F,"C rf_trim readback");
  por_n=0;#100;por_n=1;#200;
  expect_read(8'h10,16'h0000,"C POR pulse resets");
  expect_read(8'h0D,16'h0003,"C POR pulse sets both flags");
  // ---- D: healthy POR, strap high: POR pulse flags but does not reset
  por_bypass=1;#100;
  spi(8'h80,8'h0D,16'h0003,rd);
  spi(8'h80,8'h10,16'h3C3C,rd);
  por_n=0;#100;por_n=1;#200;
  expect_read(8'h10,16'h3C3C,"D POR pulse ignored with strap high");
  expect_read(8'h0D,16'h0005,"D por_flag only (+ strap bit)");
  pulse_reset;expect_read(8'h10,16'h0000,"D RESET_N resets");
  if(errors==0&&checks==22)$display("POR_BYPASS_PASS %0d checks",checks);
  else $display("POR_BYPASS_FAIL %0d errors, %0d checks",errors,checks);
  $finish;
 end
endmodule
