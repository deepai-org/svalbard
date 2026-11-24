// W7-GEAR word front end (rows W7-GEAR, W7-GEAR-T, DG9-W7GEAR): a behavioural model of pt_wrx_cap r7e drives the
// pt_wired macro (PT_CHIP = 2) through the new pins wire_rx_word / wire_rx_edge / wire_rx_wstb, and the 40-bit words are
// checked at the macro -> core boundary (pt_digital wire_rx_data / wire_rx_valid = core_rx_quad / core_rx_valid, wrx
// domain) against a reference built from the words the model presented.
// Capture model (r7e contract): one WSTB rise per 20-bit word, period T (8.0 ns = ring 625 MHz quarter rate, 6.0 ns =
// 834 MHz), high time T/2 + 0.2 ns; at every rise each DW / EW bit changes to the next word 0.75 .. 1.07 ns later (per
// word base 0.75 .. 0.95 ns, per-bit skew <= 0.12 ns), i.e. near the WSTB fall. cap_en = 0 (capture EN and word
// divider off) holds WSTB, DW, EW low; after cap_en rises WSTB starts a few word times later (LDE restart) and the first
// two words are stale (random here). W(s) = the word on the bus after strobe s of an epoch (W(0) = 0).
// Reference: the gear must deliver, in order, E_k = {W(2k-1), W(2k-2)} (k = 1, 2, ...; earlier word in [19:0]) at
// consecutive rises of the wrx clock (= WSTB / 2), with the pairing re-zeroed at every restart. At the core boundary,
// per epoch: words before the first valid nonzero quad may be 0 or not valid (reset / qualification); from the first
// valid nonzero quad on, every wrx edge must carry the next E_k with no gap and no repeat, and that first quad must be
// an E_k (even pairing). The edge words are checked at the same time: pt_wrx_ctl's 20-bit edge word = the earlier
// (edge_half 0) or later (1) EW of the pair; raw lane 1 at the core boundary = {EW later, EW earlier}, lane 2 = {EW earlier, DW earlier}.
// Epochs: both periods, restarts after an even and an odd number of strobes, short stops (wrx domain stays qualified)
// and long stops (> 64 REF_CLK: the word domain is reset and re-qualifies). Fields are forced hierarchically (no SPI):
// pt_wrx_ctl enable and valid_mode = forced 1, edge_half, raw_lane; island_on[0] via wired_on_ext.
// Pass: WRX_GEAR_PASS. check_wrx_gear.py runs this and mutated gears that must fail.
`timescale 1ns/1ps
`include "pt_regmap_defs.svh"
module tb_wrx_gear;
 reg reset_n_pad=1, por_n=1, ref_clk=0, hclk=0;
 always #5 ref_clk = ~ref_clk;
 always #3.2 hclk = ~hclk;
 reg wstb=0; reg[19:0] dw=0, ew=0;
 wire[`PT_ISLAND_W-1:0] island_en, island_on;
 pt_digital_macro #(.PT_CHIP(2)) dut(.reset_n_pad(reset_n_pad),.por_n(por_n),.por_bypass(1'b0),
  .spi_sclk(1'b0),.spi_cs_n(1'b1),.spi_mosi(1'b0),.spi_miso(),.spi_miso_oe(),
  .host_word_clk(hclk),.h2d_clk(1'b0),.h2d_pin(10'h0),.d2h_oe(),
  .ref_clk(ref_clk),.wire_rx_wstb(wstb),.wire_tx_clk(1'b0),.rf_rx_clk(1'b0),.rf_tx_clk(1'b0),
  .wire_rx_word(dw),.wire_rx_edge(ew),.rf_rx_sample(24'h0),.rf_rx_sample_b(24'h0),.rf_rx_ph_i(1'b0),.rf_rx_ph_q(1'b0),
  .fault(1'b0),.s_pg_wired_rx(1'b1),.s_pg_wired_cap(1'b1),.s_pg_wired_tx(1'b1),.s_pg_rf_rx(1'b0),.s_pg_rf_tx(1'b0),.s_pg_lod(1'b0),
  .s_pg_lo(1'b0),.s_pg_pll(1'b1),.s_pg_conv(1'b0),.s_pg_debug(1'b1),
  .island_en(island_en),.island_on(island_on),.wired_on_ext(1'b1),.ct_wclk(1'b0),.fc_src(6'h0),
  .s_pll_tx_lock(1'b0),.s_pll_cdr_lock(1'b0),.s_ref_present(1'b0),.s_refbuf_ready(1'b0),.s_adc_i_ovl(1'b0),.s_adc_i_b_ovl(1'b0),
  .s_adc_q_ovl(1'b0),.s_adc_q_b_ovl(1'b0),.s_adc_i_done(1'b0),.s_adc_i_b_done(1'b0),.s_adc_q_done(1'b0),.s_adc_q_b_done(1'b0),
  .s_detect_diff_pos(1'b0),.s_detect_diff_neg(1'b0),.s_detect_se_p(1'b0),.s_detect_se_n(1'b0),.s_wrx_slp(1'b0),.s_wrx_slm(1'b0),
  .s_wtx_ext_data(1'b0),.s_aux_present(1'b0),.s_wtx_ext_present(1'b0),.s_wtx_run(1'b0),.s_lo_vtdet(1'b0));

 // ---------------- forced configuration
 reg cap_en=0, edge_half=0; reg[1:0] lane=0;
 initial begin
  force dut.c_wrx_cap_en = cap_en; force dut.c_wordclk_en = cap_en;
  force dut.wrx_en = 1'b1; force dut.f_wrx_picker__valid_mode = 2'd2;
  force dut.f_wrx_picker__edge_half = edge_half; force dut.f_slicer_capture__raw_lane = lane;
  force dut.f_digital_transport_config__direct_stream_enable = 1'b0;
 end

 // ---------------- capture model
 localparam integer NW = 4096;
 reg[19:0] Wd[0:NW-1], We[0:NW-1];
 integer s=0, epoch=0, errors=0, checks=0, nq=0;
 real T=8.0;
 integer seed=7;
 task strobe;   // one WSTB period: rise, words change 0.75..1.07 ns later, fall at T/2 + 0.2
  integer i; real base, d; reg[19:0] nd, ne;
  begin
   s = s + 1;
   nd = $random(seed); ne = $random(seed);
   Wd[s] = nd; We[s] = ne;
   wstb = 1;
   base = 0.75 + 0.20 * (($random(seed) & 255) / 255.0);
   for (i = 0; i < 20; i = i + 1) begin
    d = base + 0.12 * (($random(seed) & 255) / 255.0);
    dw[i] <= #(d) nd[i];
    ew[i] <= #(d) ne[i];
   end
   #(T/2.0 + 0.2) wstb = 0;
   #(T/2.0 - 0.2);
  end
 endtask
 // one epoch: cap_en rises, WSTB starts after `lead` word times, n strobes, then cap_en falls for `gap` ns
 task run_epoch(input integer n, input integer lead, input real gap);
  integer k;
  begin
   epoch = epoch + 1; s = 0; Wd[0] = 20'd0; We[0] = 20'd0;
   cap_en = 1;
   #(lead * T + 1.3);
   for (k = 0; k < n; k = k + 1) strobe;
   cap_en = 0; #0.4; dw = 20'd0; ew = 20'd0;   // EN = 0 holds the word outputs low
   #(gap);
  end
 endtask

 // ---------------- checker (wrx domain = dut.wire_rx_clk_c)
 // expected quad at the core boundary for pair k: lane 0 data, lane 1 {EW later, EW earlier}, lane 2 {EW earlier, DW earlier}
 function [39:0] exp_q(input integer k);
  exp_q = lane == 2'd1 ? {We[2*k-1], We[2*k-2]} : lane == 2'd2 ? {We[2*k-2], Wd[2*k-2]} : {Wd[2*k-1], Wd[2*k-2]};
 endfunction
 integer ep_seen=-1, next_k=0, first_k=0, nvalid=0;
 real t_last=0, wper=0; integer nper=0, bad_per=0;
 integer m; reg found;
 always @(posedge dut.wire_rx_clk_c) begin
  // wrx period = 2 WSTB periods (valid every second WSTB)
  if (t_last > 0 && $realtime - t_last < 3.0 * T) begin
   nper = nper + 1;
   if ($realtime - t_last < 2.0 * T - 0.01 || $realtime - t_last > 2.0 * T + 0.01) bad_per = bad_per + 1;
  end
  t_last = $realtime;
  // gear outputs into pt_wrx_ctl: dx / the selected edge word belong to the same pair
  if (dut.wrx_dx !== 40'd0) begin
   found = 0;
   for (m = 1; 2 * m - 1 <= s && !found; m = m + 1)
    if (dut.wrx_dx === {Wd[2*m-1], Wd[2*m-2]}) begin
     found = 1; checks = checks + 1;
     if (dut.wrx_ew !== (edge_half ? We[2*m-1] : We[2*m-2])) begin
      errors = errors + 1; $display("FAIL epoch %0d pair %0d: edge word %h, expected %h (edge_half %0d)", epoch, m, dut.wrx_ew,
       edge_half ? We[2*m-1] : We[2*m-2], edge_half);
     end
    end
   if (!found) begin errors = errors + 1; $display("FAIL epoch %0d t=%0t: gear word %h is no even pair of this epoch", epoch, $time, dut.wrx_dx); end
  end
 end
 // core boundary: pt_wrx_lane's output register is updated at the wrx rise, so it is read half a wrx period later, at
 // the wrx fall of a running gear (the asynchronous fall when cap_en drops resets the gear and is not a word edge)
 always @(negedge dut.wire_rx_clk_c) if (cap_en) begin
  if (ep_seen != epoch) begin ep_seen = epoch; next_k = 0; end
  if (dut.core_rx_valid === 1'b1 && dut.core_rx_quad !== 40'd0) begin
   nq = nq + 1;
   if (next_k == 0) begin
    found = 0;
    for (m = 1; 2 * m - 1 <= s && !found; m = m + 1)
     if (dut.core_rx_quad === exp_q(m)) begin found = 1; next_k = m; end
    if (!found) begin errors = errors + 1; $display("FAIL epoch %0d t=%0t: first quad %h is no even pair {W(2k-1), W(2k-2)}", epoch, $time, dut.core_rx_quad); end
   end
   if (next_k != 0) begin
    checks = checks + 1;
    if (dut.core_rx_quad !== exp_q(next_k)) begin
     errors = errors + 1;
     $display("FAIL epoch %0d t=%0t: quad %h, expected E_%0d = %h", epoch, $time, dut.core_rx_quad, next_k,
      exp_q(next_k));
    end
    next_k = next_k + 1;
   end
  end else if (next_k != 0 && dut.core_rx_valid === 1'b1) begin
   errors = errors + 1; $display("FAIL epoch %0d t=%0t: zero quad inside the stream (gap)", epoch, $time);
  end
 end

 integer ep_q;
 task expect_quads(input integer want, input[8*24-1:0] what);
  begin
   checks = checks + 1;
   if (nq - ep_q < want) begin errors = errors + 1; $display("FAIL %0s: %0d quads at the core boundary, expected >= %0d", what, nq - ep_q, want); end
   ep_q = nq;
  end
 endtask

 initial begin
  ep_q = 0;
  #20 reset_n_pad = 0; #200 reset_n_pad = 1; #500;
  // 625 MHz ring (T = 8.0 ns): first epoch long enough to qualify the word domain; restarts after odd / even counts
  T = 8.0;
  run_epoch(200, 3, 30.0);  expect_quads(60, "T8 first epoch");
  run_epoch(77, 4, 25.0);   expect_quads(30, "T8 odd restart");     // short stop: wrx domain stays qualified
  run_epoch(64, 3, 40.0);   expect_quads(25, "T8 even restart");
  run_epoch(51, 5, 1500.0); expect_quads(15, "T8 odd, long stop");
  edge_half = 1;
  run_epoch(150, 3, 30.0);  expect_quads(40, "T8 edge_half 1");
  lane = 2'd1;
  run_epoch(121, 3, 30.0);  expect_quads(40, "T8 raw lane 1 (edges)");
  lane = 2'd2;
  run_epoch(101, 3, 30.0);  expect_quads(30, "T8 raw lane 2");
  lane = 2'd0; edge_half = 0;
  // 834 MHz ring (T = 6.0 ns)
  T = 6.0;
  run_epoch(201, 3, 20.0);  expect_quads(70, "T6 odd");
  run_epoch(160, 4, 1500.0); expect_quads(30, "T6 long stop");
  run_epoch(99, 3, 20.0);   expect_quads(30, "T6 odd, after long stop");
  #200;
  checks = checks + 1;
  if (bad_per != 0 || nper < 100) begin errors = errors + 1; $display("FAIL wrx period: %0d of %0d periods not 2 x WSTB", bad_per, nper); end
  $display("tb_wrx_gear: %0d epochs, %0d quads at the core boundary, %0d checks, %0d errors", epoch, nq, checks, errors);
  if (errors == 0) $display("WRX_GEAR_PASS"); else $display("WRX_GEAR_FAIL");
  $finish;
 end
endmodule
