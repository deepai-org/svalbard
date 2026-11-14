`timescale 1ns/1ps
// Stub-level mixed boundary sim (pre-mortem item 6 / MW-0): SPI write -> register file -> macro port ->
// analog-top pin, through the generated behavioural stub of pt_analog_top (generated/pt_analog_top_stub.sv:
// island switch PG = EN, iso clamp Y = A & !ISO, POR released, every block input visible as p_<inst>__<pin>).
// It crosses the boundary with the REAL rtl/pt_digital_macro.sv; nothing inside the macro is forced.
//
// Until the digital owner adds the c_* ports of integration/top/ctl_ports.txt (rows TOP-* in
// interface-changes.md), the macro only has analog_cfg / debug_cfg / en_eff. The INTERIM block below maps the
// handful of ports this bench checks from those buses (positions from rtl/pt_regmap_defs.svh); every other
// c_* port is held at 0. Compile with +define+PT_MACRO_HAS_CTL once the macro has the ports: the interim map
// disappears and all 215 ports connect by name.
// Negative controls: (1) in-test: an unrelated write must change no control pin; an enable with its island
// off must stay 0. (2) +define+NEG_MISBIND shifts one interim binding by one bit: the bench must FAIL.
// (3) run.sh regenerates the stub from a copy of pt_chip.conn with two LNA trim pins swapped: the bench must FAIL
// (this one is on the connectivity itself, not on the interim map). run.sh requires (2) and (3).
// Limits: 5 of the control ports are exercised (all through the interim map until the macro has the ports);
// analog -> macro is covered only by the island power-good path.
`include "pt_regmap_defs.svh"
module tb_top_boundary;
 reg rst_pad = 0, sclk = 0, cs_n = 1, mosi = 0; wire miso, miso_oe;
 supply1 VDD; supply0 VSS;
`include "tb_ctl.svh"
`include "tb_regs.svh"
 wire [5:0] island_en, island_on, island_off;
 wire [57:0] atb0_sw, atb1_sw; wire [1:0] atb0_grp; wire [4:0] atb1_grp; wire atb0_en, atb1_en;
 wire por_n, wired_on_ext, wire_rx_ptrim_en;
 // Per-switch power-good from the ten island switches (the macro ANDs each enable group, PD2-2).
 wire s_pg_wired_rx, s_pg_wired_cap, s_pg_wired_tx, s_pg_rf_rx, s_pg_rf_tx, s_pg_lod, s_pg_lo, s_pg_pll, s_pg_conv, s_pg_debug;
 // The real macro (TOP-1 done 2026-11-14): every c_* port connects by name. Inputs this bench does not exercise are 0.
 pt_digital_macro dut(.reset_n_pad(rst_pad), .por_n(por_n), .por_bypass(1'b0), .spi_sclk(sclk), .spi_cs_n(cs_n), .spi_mosi(mosi),
  .spi_miso(miso), .spi_miso_oe(miso_oe), .island_en(island_en), .island_on(island_on), .island_off(island_off),
  .s_pg_wired_rx(s_pg_wired_rx), .s_pg_wired_cap(s_pg_wired_cap), .s_pg_wired_tx(s_pg_wired_tx), .s_pg_rf_rx(s_pg_rf_rx),
  .s_pg_rf_tx(s_pg_rf_tx), .s_pg_lod(s_pg_lod), .s_pg_lo(s_pg_lo), .s_pg_pll(s_pg_pll), .s_pg_conv(s_pg_conv), .s_pg_debug(s_pg_debug),
  .wired_on_ext(wired_on_ext), .atb0_sw(atb0_sw), .atb1_sw(atb1_sw), .atb0_grp(atb0_grp),
  .atb1_grp(atb1_grp), .atb0_en(atb0_en), .atb1_en(atb1_en), .wire_rx_ptrim_en(wire_rx_ptrim_en), .fault(1'b0),
  .host_word_clk(1'b0), .h2d_clk(1'b0), .h2d_pin(10'b0), .ref_clk(1'b0), .wire_rx_clk(1'b0), .wire_tx_clk(1'b0),
  .rf_rx_clk(1'b0), .rf_tx_clk(1'b0), .ct_wclk(1'b0), .fc_src(6'b0), .wire_rx_data(40'b0), .wire_rx_edge(20'b0),
  .rf_rx_sample(24'b0), .rf_rx_sample_b(24'b0), .rf_rx_ph_i(1'b0), .rf_rx_ph_q(1'b0),
  .s_pll_tx_lock(1'b0), .s_pll_cdr_lock(1'b0), .s_ref_present(1'b0), .s_refbuf_ready(1'b0), .s_adc_i_ovl(1'b0), .s_adc_i_b_ovl(1'b0),
  .s_adc_q_ovl(1'b0), .s_adc_q_b_ovl(1'b0), .s_adc_i_done(1'b0), .s_adc_i_b_done(1'b0), .s_adc_q_done(1'b0), .s_adc_q_b_done(1'b0),
  .s_detect_diff_pos(1'b0), .s_detect_diff_neg(1'b0), .s_detect_se_p(1'b0), .s_detect_se_n(1'b0), .s_wrx_slp(1'b0), .s_wrx_slm(1'b0),
  .s_wtx_ext_data(1'b0), .s_aux_present(1'b0), .s_wtx_ext_present(1'b0), `PT_CTL_CONNECT);
`ifdef NEG_MISBIND
 // negative control: rotate the LNA trim bus between the macro and the analog top; the bench must FAIL
 initial force c_lna_ct = {dut.c_lna_ct[2:0], dut.c_lna_ct[3]};
`endif
 pt_analog_top_stub analog(.VDD(VDD), .VSS(VSS), .island_en(island_en), .island_on(island_on), .island_off(island_off),
  .s_pg_wired_rx(s_pg_wired_rx), .s_pg_wired_cap(s_pg_wired_cap), .s_pg_wired_tx(s_pg_wired_tx), .s_pg_rf_rx(s_pg_rf_rx),
  .s_pg_rf_tx(s_pg_rf_tx), .s_pg_lod(s_pg_lod), .s_pg_lo(s_pg_lo), .s_pg_pll(s_pg_pll), .s_pg_conv(s_pg_conv), .s_pg_debug(s_pg_debug),
  .wired_on_ext(wired_on_ext), .atb0_sw(atb0_sw), .atb1_sw(atb1_sw), .atb0_grp(atb0_grp),
  .atb1_grp(atb1_grp), .atb0_en(atb0_en), .atb1_en(atb1_en), .wire_rx_ptrim_en(wire_rx_ptrim_en), .por_n(por_n), `PT_CTL_CONNECT);

 integer errors = 0;
 task fail(input [639:0] msg); begin $display("FAIL: %0s", msg); errors = errors+1; end endtask
 task spi(input [7:0] command, address, input [15:0] value, output [15:0] result);
  reg [31:0] tx; integer i;
  begin
   tx = {command, address, value}; result = 0; cs_n = 0; #100;
   for (i = 31; i >= 0; i = i-1) begin mosi = tx[i]; #200; sclk = 1; #200; if (i < 16) result[i] = miso; sclk = 0; #100; end
   cs_n = 1; #100;
  end
 endtask
 reg [15:0] r;
 task wr(input [7:0] a, input [15:0] v); spi(8'h80, a, v, r); endtask
 task commit; begin wr(8'h06, 16'h1); #50; end endtask
 function integer ones(input [$bits(ctl_all)-1:0] v); integer k; begin ones = 0; for (k = 0; k < $bits(ctl_all); k = k+1) ones = ones+v[k]; end endfunction
 reg [$bits(ctl_all)-1:0] snap;
 wire [3:0] lna_ct = {analog.p_lna__ct3, analog.p_lna__ct2, analog.p_lna__ct1, analog.p_lna__ct0};
 initial begin
  #20; rst_pad = 1; #20; rst_pad = 0; #50; rst_pad = 1; #200;     // explicit reset pulse (async assert needs an edge)
  // 1. reset values at the analog pins. Island fields are forced 0 while their island is off (regfile gating rule).
  if (lna_ct !== 4'h0) fail("lna ct pins not 0 with the rf island off");
  if (analog.p_lna__en !== 1'b0) fail("lna en not 0 after reset");
  if (analog.p_aosc__EN !== 1'b0) fail("aosc EN not 0 after reset (DT-11: reset off)");
  if (analog.p_pll_vreg2__BYP_TX !== 1'b0) fail("pll_vreg2 BYP_TX not 0 with the pll island off");
  if (atb1_sw !== 0 || analog.p_atb1_pad__SEL !== 1'b0) fail("ATB1 not open after reset");
  if (analog.p_lna__island_off !== 1'b1) fail("lna island_off not 1 with the rf island off");
  // 2. negative control: lna.state = active with the rf island OFF must not enable the LNA
  wr(`PT_REG_LNA_STATE_ADDR, 16'h0002); commit;
  if (analog.p_lna__en !== 1'b0) fail("lna en rose with its island off");
  wr(`PT_REG_LNA_STATE_ADDR, 16'h0000); commit;
  // 3. islands on through the stub switches (PG = EN): rf and pll. Field resets appear at the pins.
  wr(8'h40, 16'h0006); commit;
  if (island_on[2:1] !== 2'b11) fail("rf/pll islands did not come on through the stub switches");
  if (analog.p_lna__island_off !== 1'b0) fail("lna island_off did not drop");
  if (lna_ct !== `PT_REG_LNA_CT_RESET) fail("lna ct pins != field reset with the island on");
  if (analog.p_pll_vreg2__BYP_TX !== 1'b1) fail("pll_vreg2 BYP_TX not 1 (reset = bypass) with the pll island on");
  // analog -> macro direction: the stub switches' PG outputs are read back over SPI (island power-good status)
  spi(8'h00, 8'h0A, 16'h0, r);
  if (r[2:1] !== 2'b11 || r[0] !== 1'b0) fail("island power-good status read over SPI does not show rf and pll only");
  if (analog.p_lna__en !== 1'b0) fail("lna en high with state off");
  // 4. direct multi-bit field: lna.match.ctrim = 0xA -> ct3..0 = 1010, and nothing else moves
  snap = ctl_all; wr(`PT_REG_LNA_MATCH_ADDR, 16'h000A); commit;
  if (lna_ct !== 4'hA) fail("lna ct pins did not follow lna.match.ctrim");
  if (ones(ctl_all ^ snap) != 3) fail("ctrim write changed a number of control pins other than 3 (7 -> A)");
  // 5. negative control: an unrelated register (pattern user word) changes no control pin
  snap = ctl_all; wr(`PT_REG_PATTERN_ADDR, 16'h0155); commit;
  if (ctl_all !== snap) fail("unrelated write changed a control pin");
  // 6. enable: lna.state = active -> lna en and its bias-bank enable, and no other block enable
  snap = ctl_all; wr(`PT_REG_LNA_STATE_ADDR, 16'h0002); commit;
  if (analog.p_lna__en !== 1'b1) fail("lna en did not rise (state active, island on)");
  if (analog.p_core_bias__EN_lna !== 1'b1) fail("core_bias EN_lna did not follow the lna enable");
  if (ones(ctl_all ^ snap) != 1) fail("lna enable changed more than one control pin");
  // 7. one-hot select: ATB1 code 5 (core_vdd_sense) -> exactly leaf 5, its group and the pad switch
  wr(8'h4A, `PT_REG_ATB1_CODE5); commit;
  if (analog.p_atb1_leaf5__SEL !== 1'b1 || ones(atb1_sw) != 1) fail("ATB1 one-hot: leaf 5 not the only closed leaf");
  if (analog.p_atb1_grp0__SEL !== 1'b1 || analog.p_atb1_pad__SEL !== 1'b1) fail("ATB1 group / pad switch not closed");
  if (atb0_sw !== 0) fail("ATB0 moved");
  // 8. always-on live field: core.aosc.enable = 1 reaches the oscillator pin
  wr(`PT_REG_AOSC_ADDR, 16'h0001); commit;
  if (analog.p_aosc__EN !== 1'b1) fail("aosc EN did not follow core.aosc.enable");
  // 9. reset returns every checked pin to its safe value
  rst_pad = 0; #100;
  if (analog.p_lna__en !== 1'b0 || analog.p_aosc__EN !== 1'b0 || atb1_sw !== 0 || island_en !== 0) fail("reset did not restore safe values");
  if (errors == 0) $display("TOP_BOUNDARY_PASS"); else $display("TOP_BOUNDARY_FAIL %0d", errors);
  $finish;
 end
 initial begin #2000000; $display("TOP_BOUNDARY_FAIL timeout"); $finish; end
endmodule
