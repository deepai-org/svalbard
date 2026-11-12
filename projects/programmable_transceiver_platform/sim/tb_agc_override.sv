`timescale 1ns/1ps
`include "pt_regmap_defs.svh"
// Direct check of the RXR-D2 fast-gain override in pt_digital_macro (coordinator request, TC13 r4):
// with rx_gain_active the LNA index selects lna.match.att (index 0 = -6 dB -> att 2, 1..3 -> att 0) and
// forces lna.gain.gain_db = 1 (gain_lo off); the PGA index selects bbfilter gain via pga_code. Every
// other analog_cfg / debug_cfg bit must pass through unchanged, and with rx_gain_active = 0 both
// vectors must equal the register file exactly. Random register contents, all 128 rx_gain values.
module tb_agc_override;
 pt_digital_macro dut();
 localparam AW=`PT_ANALOG_CFG_W, DW=`PT_DEBUG_CFG_W;
 localparam ATT=`PT_A_LNA_MATCH__ATT_LSB, GDB=`PT_A_LNA_GAIN__GAIN_DB_LSB, PGA=`PT_D_CONSOLIDATION_BBFILTER__GAIN_LSB;
 reg[AW-1:0] areg, aexp; reg[DW-1:0] dreg, dexp; reg[6:0] g; reg act;
 integer i, k, errors=0, checks=0;
 function automatic [3:0] pga(input [4:0] k);
  case (k) 0,1,2,3: pga=0; 4: pga=1; 5: pga=2; 6: pga=3; 7: pga=5; 8: pga=7; 9: pga=10; default: pga=15; endcase
 endfunction
 initial begin
  if (`PT_A_LNA_MATCH__ATT_W != 5 || `PT_A_LNA_GAIN__GAIN_DB_W != 2 || `PT_A_LNA_MATCH__CTRIM_W != 4)
   $fatal(1, "field widths changed: att %0d gain_db %0d ctrim %0d", `PT_A_LNA_MATCH__ATT_W, `PT_A_LNA_GAIN__GAIN_DB_W, `PT_A_LNA_MATCH__CTRIM_W);
  for (i = 0; i < 64; i = i + 1) begin
   for (k = 0; k < AW; k = k + 32) areg[k +: 32] = $random; for (k = 0; k < DW; k = k + 32) dreg[k +: 32] = $random;
   if (i == 0) begin areg = '0; dreg = '0; end
   if (i == 1) begin areg = '1; dreg = '1; end
   force dut.analog_cfg_reg = areg; force dut.debug_cfg_reg = dreg;
   for (k = 0; k < 256; k = k + 1) begin
    {act, g} = k[7:0];
    force dut.rx_gain = g; force dut.rx_gain_active = act; #1;
    aexp = areg; dexp = dreg;
    if (act) begin
     aexp[ATT +: 5] = (g[6:5] == 2'd0) ? 5'd2 : 5'd0;
     aexp[GDB +: 2] = 2'd1;
     dexp[PGA +: 4] = pga(g[4:0]);
    end
    checks = checks + 1;
    if (dut.analog_cfg !== aexp) begin errors = errors + 1;
     if (errors < 8) $display("FAIL analog act=%b g=%h diff=%h", act, g, dut.analog_cfg ^ aexp); end
    if (dut.debug_cfg !== dexp) begin errors = errors + 1;
     if (errors < 8) $display("FAIL debug act=%b g=%h diff=%h", act, g, dut.debug_cfg ^ dexp); end
   end
  end
  // SLI7-R interlock: ptrim_en only with slicer.state active
  for (k = 0; k < 4; k = k + 1) begin
   areg = '0; areg[`PT_A_SLICER_STATE__STATE_LSB +: 2] = k[1:0]; force dut.analog_cfg_reg = areg; force dut.rx_gain_active = 1'b0; #1;
   checks = checks + 1;
   if (dut.wire_rx_ptrim_en !== (k == 2)) begin errors = errors + 1; $display("FAIL ptrim_en state=%0d got %b", k, dut.wire_rx_ptrim_en); end
  end
  if (errors) $fatal(1, "AGC override: %0d mismatches in %0d checks", errors, checks);
  $display("AGC_OVERRIDE_PASS %0d checks: -6 dB -> att 2 / gain_db 1, other LNA indices att 0, PGA codes, passthrough, SLI7-R ptrim interlock", checks);
  $finish;
 end
endmodule
