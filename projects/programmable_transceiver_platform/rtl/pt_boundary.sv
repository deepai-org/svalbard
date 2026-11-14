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
// island's island_on on the FIRST gate after the pin (integration/top/generated/macro_clamps.txt). A kept
// and2 cell: the flow must not buffer or hold-fix between the pin and this gate (config dont_touch iso_*).
module pt_iso_and #(parameter W = 1)(input wire[W-1:0] a, input wire on, output wire[W-1:0] y);
 genvar i;
 generate for (i = 0; i < W; i = i + 1) begin : g
`ifdef SYNTHESIS
  (* keep=1,dont_touch=1 *) gf180mcu_fd_sc_mcu7t5v0__and2_1 iso_and(.A1(a[i]), .A2(on), .Z(y[i]));
`else
  assign y[i] = a[i] & on;
`endif
 end endgenerate
endmodule

// IX-12 raw lane select at the wired ingress. The published capture (pt_wrx_cap r6) gives the 40-bit data
// quad DX on WCLK40 and a 20-bit edge word EW per 20-bit word, i.e. two edge words per WCLK40 period with no
// strobe of their own: the first is registered on the falling WCLK40 edge, the second on the rising edge
// together with DX (the wired RX owner must confirm this alignment: row DIG-EW).
//   lane 0: data quad (mission mode)            {DX[39:0]}
//   lane 1: edge quad                           {EW second word, EW first word}
//   lane 2: first half word of both lanes       {EW first word, DX[19:0]}   (half the line time, both lanes)
// Continuous export of BOTH full lanes needs 80 bits per WCLK40 period, which the 40-bit ingress cannot
// carry: not implemented (see NOTES r6, what remains).
module pt_wrx_lane(input wire clk, rst_n, input wire[1:0] lane, input wire[39:0] dx, input wire[19:0] ew,
 output wire[39:0] quad);
 reg[19:0] ew_f;
 always @(negedge clk or negedge rst_n) if (!rst_n) ew_f <= 20'd0; else ew_f <= ew;
 assign quad = (lane == 2'd1) ? {ew, ew_f} : (lane == 2'd2) ? {ew_f, dx[19:0]} : dx;
endmodule
`default_nettype wire
