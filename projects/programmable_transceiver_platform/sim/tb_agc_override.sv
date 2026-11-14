`timescale 1ns/1ps
`include "pt_regmap_defs.svh"
// Direct check of the RXR-D2 fast-gain override in rtl/pt_ctl_decode.sv (mode-walk rework 2026-11-14, RC-16p):
// with rx_gain_active the LNA index k selects the programmable attenuator code lna.agc.code<k> = {gain_lo, att[4:0]}
// and the PGA index (0..16, clamped) selects the bbfilter LUT entry on BOTH channels; without it the pins follow
// lna.match.{gain_lo, att} and bbfilter_x.trim.gain. Neighbouring LNA / filter pins must not move with the override,
// and everything is 0 with the rf island off. Random register contents, all 128 rx_gain values, both states.
// Also the SLI7-R interlock: wire_rx_ptrim_en only with slicer.state active and the wired and pll islands on.
module tb_agc_override;
 localparam AW=`PT_ANALOG_CFG_W, DW=`PT_DEBUG_CFG_W;
 reg[AW-1:0] areg; reg[DW-1:0] dreg; reg[6:0] g; reg act; reg[5:0] ion;
 wire c_lna_gain_lo; wire[4:0] c_lna_att; wire[3:0] c_lna_ct; wire[5:0] gi, gq; wire[1:0] ci, cq; wire[6:0] cut_i; wire ptrim;
 pt_ctl_decode dut(.analog_cfg(areg), .debug_cfg(dreg), .island_on(ion), .vreg_rx_ok(1'b1), .bg_ok(1'b1), .reset_seen(1'b1),
  .rx_gain(g), .rx_gain_active(act), .rf_mute(1'b0), .rx_en_aux_reg(1'b0), .rx_en_wclk_reg(1'b0), .vth_fast(2'b0), .vth_fast_a(8'd0), .vth_fast_b(8'd0),
  .c_lna_gain_lo(c_lna_gain_lo), .c_lna_att(c_lna_att), .c_lna_ct(c_lna_ct), .c_bbfilter_i_gain(gi), .c_bbfilter_q_gain(gq),
  .c_bbfilter_i_gainc(ci), .c_bbfilter_q_gainc(cq), .c_bbfilter_i_cut(cut_i), .wire_rx_ptrim_en(ptrim));
 integer i, k, errors=0, checks=0;
 // analog/rf_rx netlists.GAIN_TABLE: (k, gainc0, gainc1) per dB index
 function automatic [7:0] lut(input integer idx);
  case (idx)
   0: lut={2'b00,6'd2}; 1: lut={2'b00,6'd3}; 2: lut={2'b00,6'd4}; 3: lut={2'b00,6'd6}; 4: lut={2'b00,6'd8}; 5: lut={2'b00,6'd12};
   6: lut={2'b00,6'd17}; 7: lut={2'b00,6'd24}; 8: lut={2'b00,6'd35}; 9: lut={2'b01,6'd12}; 10: lut={2'b01,6'd17}; 11: lut={2'b01,6'd24};
   12: lut={2'b01,6'd35}; 13: lut={2'b11,6'd12}; 14: lut={2'b11,6'd17}; 15: lut={2'b11,6'd25}; default: lut={2'b11,6'd36};
  endcase
 endfunction
 reg[5:0] code_exp; reg[7:0] pi_exp, pq_exp; reg[4:0] idx_i, idx_q; reg[5:0] agc[0:3];
 initial begin
  if (`PT_A_LNA_MATCH__ATT_W != 5 || `PT_A_LNA_AGC__CODE0_W != 6 || `PT_A_BBFILTER_I_TRIM__GAIN_W != 5)
   $fatal(1, "field widths changed");
  for (i = 0; i < 64; i = i + 1) begin
   for (k = 0; k < AW; k = k + 32) areg[k +: 32] = $random; for (k = 0; k < DW; k = k + 32) dreg[k +: 32] = $random;
   if (i == 0) begin areg = '0; dreg = '0; end
   if (i == 1) begin areg = '1; dreg = '1; end
   ion = (i % 5 == 4) ? 6'b111101 : 6'b111111;      // every fifth pattern: rf island off
   if (!ion[1]) begin   // the register file gates rf-island fields to 0 while the island is off
    areg[`PT_A_LNA_MATCH__ATT_LSB +: 5] = 0; areg[`PT_A_LNA_MATCH__GAIN_LO_LSB] = 0; areg[`PT_A_LNA_MATCH__CTRIM_LSB +: 4] = 0;
    areg[`PT_A_LNA_AGC__CODE0_LSB +: 6] = 0; areg[`PT_A_LNA_AGC__CODE1_LSB +: 6] = 0; areg[`PT_A_LNA_AGC__CODE2_LSB +: 6] = 0; areg[`PT_A_LNA_AGC__CODE3_LSB +: 6] = 0;
    areg[`PT_A_BBFILTER_I_TRIM__GAIN_LSB +: 5] = 0; areg[`PT_A_BBFILTER_Q_TRIM__GAIN_LSB +: 5] = 0; areg[`PT_A_BBFILTER_I_TRIM__CUT_LSB +: 7] = 0;
   end
   agc[0] = areg[`PT_A_LNA_AGC__CODE0_LSB +: 6]; agc[1] = areg[`PT_A_LNA_AGC__CODE1_LSB +: 6];
   agc[2] = areg[`PT_A_LNA_AGC__CODE2_LSB +: 6]; agc[3] = areg[`PT_A_LNA_AGC__CODE3_LSB +: 6];
   for (k = 0; k < 256; k = k + 1) begin
    {act, g} = k[7:0]; #1;
    code_exp = act ? agc[g[6:5]] : {areg[`PT_A_LNA_MATCH__GAIN_LO_LSB], areg[`PT_A_LNA_MATCH__ATT_LSB +: 5]};
    idx_i = act ? (g[4:0] > 16 ? 5'd16 : g[4:0]) : areg[`PT_A_BBFILTER_I_TRIM__GAIN_LSB +: 5];
    idx_q = act ? (g[4:0] > 16 ? 5'd16 : g[4:0]) : areg[`PT_A_BBFILTER_Q_TRIM__GAIN_LSB +: 5];
    pi_exp = ion[1] ? lut(idx_i) : 8'd0; pq_exp = ion[1] ? lut(idx_q) : 8'd0;
    checks = checks + 1;
    if ({c_lna_gain_lo, c_lna_att} !== code_exp) begin errors = errors + 1; if (errors < 8) $display("FAIL lna code act=%b g=%h got %h exp %h", act, g, {c_lna_gain_lo, c_lna_att}, code_exp); end
    if ({ci, gi} !== pi_exp || {cq, gq} !== pq_exp) begin errors = errors + 1; if (errors < 8) $display("FAIL pga act=%b g=%h got %h %h exp %h %h", act, g, {ci, gi}, {cq, gq}, pi_exp, pq_exp); end
    if (ion[1] && gi == 6'd0) begin errors = errors + 1; $display("FAIL PGA muted (k = 0) with the rf island on"); end
    if (c_lna_ct !== areg[`PT_A_LNA_MATCH__CTRIM_LSB +: 4] || cut_i !== areg[`PT_A_BBFILTER_I_TRIM__CUT_LSB +: 7]) begin
     errors = errors + 1; if (errors < 8) $display("FAIL neighbouring pin moved with the override"); end
   end
  end
  // SLI7-R interlock
  for (k = 0; k < 32; k = k + 1) begin
   areg = '0; dreg = '0; act = 0; ion = {k[4], 2'b11, k[3], 1'b1, k[2]}; areg[`PT_A_SLICER_STATE__STATE_LSB +: 2] = k[1:0]; #1;
   checks = checks + 1;
   if (ptrim !== ((k[1:0] == 2) && k[2] && k[3])) begin errors = errors + 1; $display("FAIL ptrim_en state=%0d ion=%b got %b", k[1:0], ion, ptrim); end
  end
  if (errors) $fatal(1, "AGC override: %0d mismatches in %0d checks", errors, checks);
  $display("AGC_OVERRIDE_PASS %0d checks: programmable LNA table, PGA LUT on both channels, island gating, neighbours fixed, SLI7-R ptrim interlock", checks);
  $finish;
 end
endmodule
