// Analog data-boundary glue inside pt_digital_macro (mode-walk rework, rows TOP-3, D-CONV, D-VALID, IX-12).
`default_nettype none

// ADC sample handshake (analog/converters/INTEGRATION.md section 2, staged AP4 contract). The converters produce
// no valid and no clock: rf_rx_clk = CONV_CLK. One flop stage on rising rf_rx_clk:
//   ilen = 1 (two interleaved cores): at every edge read the ADC's own phase output PH; PH = 0 registers core
//   A's word, PH = 1 core B's (per channel: I and Q each have a PH). ilen = 0: core A only.
//   valid = ADC enabled AND 4 edges counted since the enable / clock start (the enable is a static level that
//   only changes while the clock is stopped, so the asynchronous release is safe).
// sample / valid are rf_rx_clk registers (one clock of latency ahead of the transport packer).
module pt_adc_merge(input wire clk, rst_n, adc_en, ilen, ph_i, ph_q, input wire[23:0] sample_a, sample_b,
 output reg[23:0] sample, output reg valid);
 wire run_n = rst_n & adc_en;
 reg[2:0] seen;                 // edges so far, saturating at 4
 always @(posedge clk or negedge run_n)
  if (!run_n) begin seen <= 3'd0; sample <= 24'd0; valid <= 1'b0; end
  else begin
   if (!seen[2]) seen <= seen + 3'd1;
   sample[11:0]  <= (ilen & ph_i) ? sample_b[11:0]  : sample_a[11:0];
   sample[23:12] <= (ilen & ph_q) ? sample_b[23:12] : sample_a[23:12];
   valid <= seen[2];
  end
endmodule

// Wired detector clock (the only part of pt_clocktree_slow with an analog consumer, pt_detect.det_clk; D-CT):
// det_clk = clk / ceil(f_wire / 500 MHz) from cdr.config.nominal_rate_khz, enabled with the detector.
module pt_det_clk(input wire clk, rst_n, en, input wire[21:0] cfg_rate_khz, output wire det_clk);
 reg[1:0] dr, den_s, den_f; wire[2:0] det_div;
 always @(posedge clk or negedge rst_n) if (!rst_n) dr <= 2'd0; else dr <= {dr[0], 1'b1};
 always @(posedge clk or negedge dr[1]) if (!dr[1]) den_s <= 2'd0; else den_s <= {den_s[0], en};
 always @(negedge clk or negedge dr[1]) if (!dr[1]) den_f <= 2'd0; else den_f <= {den_f[0], en};
 pt_ct_detect_div detect(.clk(clk), .rst_n(dr[1]), .en(den_s[1]), .en_fall(den_f[1]), .cfg_div(3'd0),
  .cfg_rate_khz(cfg_rate_khz), .div(det_div), .det_clk(det_clk));
endmodule

// CP4-1 island isolation inside the macro: every input that comes from a switched island is ANDed with that
// island's island_on on the FIRST gate after the pin (integration/chips/<chip>/generated/macro_clamps.txt). A kept
// and2 cell. OPEN for the hardening flow (review finding 1): the 130 pin nets must be excluded from input-port
// buffering and hold repair, and the routed netlist checked (only load of each pin = its iso_and).
// PRESENT = 0 (split, D4): the pin belongs to the other chip's blocks; no clamp cell, the output is constant 0, so the
// logic behind it synthesizes away (a kept AND2 would hide the constant from synthesis).
module pt_iso_and #(parameter W = 1, CLK = 0, PRESENT = 1)(input wire[W-1:0] a, input wire on, output wire[W-1:0] y);
 genvar i;
 generate for (i = 0; i < W; i = i + 1) begin : g
  if (!PRESENT) begin : z
   assign y[i] = 1'b0;
  end else begin : p
`ifdef SYNTHESIS
  // CLK = 1: clock clamp. The cell drives the root of a clock net, which the resizer steps do not repair
  // (r7c post-CTS at ss_032C_3v15: an and2_1 on 0.09 pF gave a 3.05 ns edge and 2.4 ns of delay on wire_tx_clk),
  // so it is a drive-4 cell from the start. A1 pin load 8.8 fF instead of 2.8 fF (interface row DG8-3).
  if (CLK) begin : c
   (* keep=1,dont_touch=1 *) gf180mcu_fd_sc_mcu7t5v0__and2_4 iso_and(.A1(a[i]), .A2(on), .Z(y[i]));
  end else begin : d
   (* keep=1,dont_touch=1 *) gf180mcu_fd_sc_mcu7t5v0__and2_1 iso_and(.A1(a[i]), .A2(on), .Z(y[i]));
  end
`else
  assign y[i] = a[i] & on;
`endif
  end
 end endgenerate
endmodule

// W7-GEAR word front end of the wired RX (pt_wrx_cap r7: DW / EW / WSTB; interface rows W7-GEAR, W7-GEAR-T, DG9-W7GEAR).
// WSTB domain (clock wstb, the capture's word strobe, rising edge only: DW / EW change ~0.6-1.7 ns after the rise,
// at about the WSTB fall, so the fall is never used):
//   front register   dw_q / ew_q <= DW / EW at every WSTB rise (captures the word loaded at the previous strobe);
//   second EW flop   ew_q2 <= ew_q (slicer r7 metastability request: E samplers are metastable by design); dw_q2
//                    keeps DW aligned with it;
//   gear             toggle T (te, and its kept clock copy t_ff): T = 0 stores the earlier word (lo), T = 1 loads
//                    dx / ewx = {this (later) word, earlier word}, earlier word in [19:0] (AC3-W5 convention).
// wclk = T through a kept buffer = WSTB / 2: it rises at the strobes with T = 0 -> 1, one WSTB period after dx / ewx
// were loaded into dx_s / ewx_s, which are then registered on wclk (dx / ewx, wrx domain) (SDC: generated clock wrx,
// divide_by 2; dx_s / ewx_s only change at the strobes where wclk falls: multicycle hold 1 from them into wrx).
// Reset / restart: run = 0 (capture or word divider off, or reset) clears the two-flop release synchronizer grs
// asynchronously (WSTB is stopped then: capture EN = 0 holds it low); T and every register here are reset from
// grs[1], released two WSTB rises after run rises. The first word after the release is therefore always an earlier
// word: the pairing is re-zeroed at every LDE word restart. The first strobes after EN carry stale words (contract);
// the word qualification of pt_wrx_ctl discards them.
module pt_wrx_gear(input wire wstb, run, input wire[19:0] dw, ew, output wire wclk, output reg[39:0] dx, ewx);
 reg[39:0] dx_s, ewx_s;   // WSTB-domain pair registers (loaded with te = 1)
 reg[1:0] grs;
 always @(posedge wstb or negedge run) if (!run) grs <= 2'd0; else grs <= {grs[0], 1'b1};
 wire g_rn = grs[1];
 reg[19:0] dw_q, ew_q, dw_q2, ew_q2, lo_d, lo_e;
 reg te;
// te fans out to 120 enable bits (lo_d / lo_e / dx_s / ewx_s): 12 kept copies (pt_dff_rep, same next value ~te), one per
 // 10-bit slice, so each copy drives 10 flops (routed pt_wired wstb te -> dx_s was -2.9 ns at ss 3.15 V). Exact.
 wire[11:0] tc;
 genvar gi;
 generate for (gi = 0; gi < 12; gi = gi + 1) begin : tcopy
  pt_dff_rep r(.clk(wstb), .rst_n(g_rn), .d(~te), .q(tc[gi]));
 end endgenerate
 always @(posedge wstb or negedge g_rn)
  if (!g_rn) begin dw_q <= 20'd0; ew_q <= 20'd0; dw_q2 <= 20'd0; ew_q2 <= 20'd0; te <= 1'b0; end
  else begin dw_q <= dw; ew_q <= ew; dw_q2 <= dw_q; ew_q2 <= ew_q; te <= ~te; end
 generate for (gi = 0; gi < 2; gi = gi + 1) begin : lo_sl
  always @(posedge wstb or negedge g_rn)
   if (!g_rn) begin lo_d[gi*10 +: 10] <= 10'd0; lo_e[gi*10 +: 10] <= 10'd0; end
   else begin
    if (!tc[gi]) lo_d[gi*10 +: 10] <= dw_q2[gi*10 +: 10];
    if (!tc[2+gi]) lo_e[gi*10 +: 10] <= ew_q2[gi*10 +: 10];
   end
 end endgenerate
 generate for (gi = 0; gi < 4; gi = gi + 1) begin : hi_sl
  wire[9:0] src_d, src_e;
  if (gi < 2) begin : l assign src_d = lo_d[gi*10 +: 10]; assign src_e = lo_e[gi*10 +: 10]; end
  else begin : h assign src_d = dw_q2[(gi-2)*10 +: 10]; assign src_e = ew_q2[(gi-2)*10 +: 10]; end
  always @(posedge wstb or negedge g_rn)
   if (!g_rn) begin dx_s[gi*10 +: 10] <= 10'd0; ewx_s[gi*10 +: 10] <= 10'd0; end
   else begin
    if (tc[4+gi]) dx_s[gi*10 +: 10] <= src_d;
    if (tc[8+gi]) ewx_s[gi*10 +: 10] <= src_e;
   end
 end endgenerate
`ifndef SYNTHESIS
 always @(posedge wstb) if (g_rn && tc !== {12{te}}) $fatal(1, "pt_wrx_gear: te copies differ from te");
`endif
 // clock copy of te: the toggle Q drives only its own inverter and the kept clock-root buffer (as fc_half2)
 wire t;
 pt_clock_dff t_ff(.clk(wstb), .rst_n(g_rn), .d(~t), .q(t));
 pt_clock_buf t_buf(.I(t), .Z(wclk));
 // wrx-domain output register: the only wstb -> wrx paths are dx_s / ewx_s -> D here (one WSTB period of setup), and every
 // wrx consumer gets a full wrx period from these flops (the pt_wrx_ctl stage-0 cone does not fit in one WSTB period).
 // Reset with the gear (g_rn): a restart never shows the last pair of the previous epoch. g_rn rises at a WSTB rise and
 // wclk rises one WSTB period later at the earliest, so the release is one WSTB period of recovery (timed, wstb -> wrx).
 always @(posedge wclk or negedge g_rn) if (!g_rn) begin dx <= 40'd0; ewx <= 40'd0; end else begin dx <= dx_s; ewx <= ewx_s; end
endmodule

// IX-12 raw lane select at the wired ingress (wrx domain, after the W7-GEAR gear): dx = the 40-bit data word,
// ew = the two 20-bit edge words of the same two line words, {later, earlier}.
//   lane 0: data quad (mission mode)            {DX[39:0]}   (one wrx register stage in all lanes)
//   lane 1: edge quad                           {EW later word, EW earlier word}
//   lane 2: earlier half word of both lanes     {EW earlier word, DX[19:0]}   (half the line time, both lanes)
// Continuous export of BOTH full lanes needs 80 bits per wrx period, which the 40-bit ingress cannot carry.
module pt_wrx_lane(input wire clk, rst_n, input wire[1:0] lane, input wire valid_in, input wire[39:0] dx, input wire[39:0] ew,
 output reg[39:0] quad, output reg valid);
 always @(posedge clk or negedge rst_n)
  if (!rst_n) begin quad <= 40'd0; valid <= 1'b0; end
  else begin quad <= (lane == 2'd1) ? ew : (lane == 2'd2) ? {ew[19:0], dx[19:0]} : dx; valid <= valid_in; end
endmodule
`default_nettype wire
