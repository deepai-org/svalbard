// Hardened core digital macro (freeze stage 1: control and digital).
// Contents: pt_digital (pt_mgmt = pt_spi + generated pt_regfile, pt_core transport and FIFOs,
// pt_memory capture/playback, pt_pattern generator/checker with ICG word clocks, calibrator),
// pt_clocktree_slow (P2-10 word divider / launch qualification / detector divider), the two
// frequency counters (pt_freq_count, inside pt_digital) and the
// clocked half of hostio (pt_host_link: DDR/SDR capture, launch and forwarded clock).
// Pad cells are NOT in this macro: they are provider gf180mcu_fd_io cells in the ring
// (integration/pt_chip.sv pt_host_physical). This macro drives their A/OE/SL/PDRV pins and takes
// their Y outputs. Hardening flow: verification/run_digital_hardening.sh.
// Analog boundary (mode-walk rework 2026-11-14, rows TOP-1..4, TOP-10..18): the macro presents one named, decoded
// port per analog control pin group (c_*, integration/top/ctl_ports.txt; rtl/pt_ctl_decode.sv and the control blocks
// pt_wtx_ctl / pt_wrx_ctl / pt_usb), takes named status inputs (s_*), clamps every island-sourced input on its first
// gate (CP4-1, pt_iso_and) and makes the sample valids itself. analog_cfg / debug_cfg / en_eff are internal.
// Reset: rtl/pt_por_path.sv: rst_n = RESET_N AND (por_n OR por_bypass (strap) OR the pad-free rescue latch).
// por_bypass (integration-plan G3, interface row DT-10) is a static pad level, high = ignore the POR: a
// third-party POR that never releases would otherwise hold the die in reset with nothing to debug.
// It is purely combinational (no flop, no clock, no SPI, no analog): the strap pad's own pull-down
// keeps it 0 when the pad is unbonded or undriven, which is today's behaviour. With the strap high the
// die is reset by RESET_N alone (board supervisor B1). por_flag (RESET_STATUS) still follows the raw
// por_n, so a stuck POR is visible over SPI (por_flag cannot be cleared). AC-1 clocking
// (transport rework 2026-11-10): host_word_clk is the host DDR clock from the clocktree, line/16
// (156.25 MHz at 2.5 Gb/s; one ten-bit word per pin per clock EDGE) or the fixed 156.25 MHz host
// option (IX-2). No macro logic runs at the 312.5 MHz word rate. pt_host_rate_clock selects /1 /2 /4
// of it (hddr: pad-edge DDR launch and gearbox), pt_host_link divides that by 2 for the 78.125 MHz
// core clock that runs the whole 40-bit transport; H2D_CLK clocks the H2D capture and quad-FIFO
// write side.
`include "pt_regmap_defs.svh"
`default_nettype none
module pt_digital_macro(
 input  wire reset_n_pad, por_n, por_bypass,
 // SPI (pad Y / pad A,OE)
 input  wire spi_sclk, spi_cs_n, spi_mosi, output wire spi_miso, spi_miso_oe,
 // host GPIO link
 input  wire host_word_clk,                     // clocktree host DDR clock (line/16 or fixed 156.25 MHz), clamped outside
 input  wire h2d_clk, input wire[9:0] h2d_pin,
 output wire[9:0] d2h_pin, output wire d2h_clk_pin, output wire d2h_oe,
 output wire[1:0] d2h_pdrv, output wire d2h_sl,  // hostio.controls drive/slew to the pad cells
 // clocks. ref_clk: rx_ref_in on the always-on rail. wire_rx_clk = pt_wrx_cap WCLK40, wire_tx_clk = pt_wiredtx
 // WORD_CLK40, rf_tx_clk = CONV_CLK, ct_wclk = prescaled line clock: raw island nets, clamped here (CP4-1).
 // rf_rx_clk = CONV_CLK through an outside clamp (shared with CLK_OBS).
 input  wire ref_clk, wire_rx_clk, wire_tx_clk, rf_rx_clk, rf_tx_clk, ct_wclk,
 output wire ct_det_clk,                        // pt_detect det_clk
 input  wire[5:0] fc_src,                       // frequency-counter sources (P3-7, see pt_digital)
 // Wired boundary (AC-1 S3): 40-bit quads per edge of wire_rx_clk (DX[39:0]) and wire_tx_clk (D0..D39); word 0
 // (earliest on the line) in [9:0]. wire_rx_edge = capture edge word EW (IX-12).
 input  wire[39:0] wire_rx_data, input wire[19:0] wire_rx_edge, output wire[39:0] wire_tx_data,
 // RF boundary: ADC core A / core B codes and the ADC interleave phase outputs; DAC codes with the forwarded clock.
 input  wire[23:0] rf_rx_sample, rf_rx_sample_b, input wire rf_rx_ph_i, rf_rx_ph_q,
 output wire[23:0] rf_tx_sample,
 output wire rf_tx_clk_out, // DT-6: forwarded DAC capture clock (source-synchronous with rf_tx_sample)
 // islands and the external fault level (a future analog supply window comparator; tied 0 today, D-FAULT)
 // Ten supply islands in five enable groups (spec/power-delivery.md PD2-2): island_en / island_on / island_off bit
 // 0 wired = wired_rx + wired_cap + wired_tx, 1 rf = rf_rx + rf_tx + lod + lo, 2 pll, 4 conv, 5 debug (3 reserved).
 // Each switch reports its own power-good; a group is good when all of its switches are.
 input  wire fault,
 input  wire s_pg_wired_rx, s_pg_wired_cap, s_pg_wired_tx, s_pg_rf_rx, s_pg_rf_tx, s_pg_lod, s_pg_lo, s_pg_pll, s_pg_conv, s_pg_debug,
 output wire[`PT_ISLAND_W-1:0] island_en, island_on, island_off, // island_on drives the iso clamps (0 = isolated)
 // PD8: pt_wtx_fallback_control.WIRED_ON, ORed into island_on[0].
 input  wire wired_on_ext,
 output wire[`PT_ATB_W-1:0] atb0_sw, atb1_sw,
 output wire[`PT_ATB0_GRP_W-1:0] atb0_grp, output wire[`PT_ATB1_GRP_W-1:0] atb1_grp, output wire atb0_en, atb1_en,
 output wire rx_en_aux, rx_en_wclk, rx_en_wtx_ext, clk_obs_oe,
 output wire dbg_obs0, dbg_obs0_oe, dbg_obs1, dbg_obs1_oe,
 output wire wire_rx_ptrim_en,                  // SLI7-R / W6-SAFE interlock: ring phases to the slicer
 // analog status (D-STATUS): raw levels, asynchronous
 input  wire s_pll_tx_lock, s_pll_cdr_lock, s_ref_present, s_refbuf_ready,
 input  wire s_adc_i_ovl, s_adc_i_b_ovl, s_adc_q_ovl, s_adc_q_b_ovl, s_adc_i_done, s_adc_i_b_done, s_adc_q_done, s_adc_q_b_done,
 input  wire s_detect_diff_pos, s_detect_diff_neg, s_detect_se_p, s_detect_se_n,
 input  wire s_wrx_slp, s_wrx_slm, s_wtx_ext_data, s_aux_present, s_wtx_ext_present,
 // decoded analog control ports (integration/top/ctl_ports.txt)
 output wire c_aosc_en,
 output wire c_biasgen_ena,
 output wire c_biasgen_ref_sel_vbg,
 output wire c_biasgen_ref_sel_coarse,
 output wire c_biasgen_ref_sel_fine,
 output wire[4:0] c_biasgen_idac2_source,
 output wire[4:0] c_biasgen_idac1_source,
 output wire[2:0] c_biasgen_bandgap_sink1,
 output wire[1:0] c_biasgen_bandgap_sink2,
 output wire[4:0] c_biasgen_voltgen_source,
 output wire[2:0] c_biasgen_voltgen_sink1,
 output wire[2:0] c_biasgen_voltgen_sink2,
 output wire c_bgap_ena,
 output wire[15:0] c_bgap_trim,
 output wire c_bias_dist_en_rf,
 output wire c_bias_dist_en_conv,
 output wire c_bias_dist_en_pll,
 output wire c_bias_dist_en_wire,
 output wire c_bias_dist_en_debug,
 output wire c_lna_en,
 output wire c_lna_gain_lo,
 output wire c_lna_byp,
 output wire[3:0] c_lna_ct,
 output wire c_lna_se,
 output wire c_lna_rt,
 output wire[4:0] c_lna_att,
 output wire c_lna_lobias,
 output wire c_rxmix_i_en,
 output wire c_rxmix_q_en,
 output wire[5:0] c_rxmix_i_ofs,
 output wire[5:0] c_rxmix_q_ofs,
 output wire c_bbfilter_i_en,
 output wire c_bbfilter_q_en,
 output wire c_bbfilter_dir_tx,
 output wire c_bbfilter_inj,
 output wire[1:0] c_bbfilter_obs_sel,
 output wire c_bbfilter_rx_direct,
 output wire c_bbfilter_byp_s1,
 output wire c_bbfilter_byp_s23,
 output wire[6:0] c_bbfilter_i_cut,
 output wire[6:0] c_bbfilter_q_cut,
 output wire[5:0] c_bbfilter_i_gain,
 output wire[5:0] c_bbfilter_q_gain,
 output wire[1:0] c_bbfilter_i_gainc,
 output wire[1:0] c_bbfilter_q_gainc,
 output wire[3:0] c_bbfilter_i_qt,
 output wire[3:0] c_bbfilter_q_qt,
 output wire[8:0] c_bbfilter_i_dcf,
 output wire[8:0] c_bbfilter_q_dcf,
 output wire c_bb_tap_obs_en,
 output wire c_bb_tap_inj_en,
 output wire c_bb_tap_i_bias_en,
 output wire c_bb_tap_q_bias_en,
 output wire c_bb_tap_wmon_bias_en,
 output wire c_wmon_obs_en,
 output wire c_adc_i_en,
 output wire c_adc_q_en,
 output wire[1:0] c_adc_i_test,
 output wire[1:0] c_adc_q_test,
 output wire c_adc_ilen,
 output wire c_dac_i_en,
 output wire c_dac_q_en,
 output wire c_dac_i_hold_zero,
 output wire c_dac_q_hold_zero,
 output wire c_refbuf_en,
 output wire c_refbuf_ovr,
 output wire[1:0] c_adc_acq,
 output wire c_txmix_i_en,
 output wire c_txmix_q_en,
 output wire c_txmix_sel_dac,
 output wire c_txmix_sat,
 output wire c_txsum_en,
 output wire c_rfdriver_en,
 output wire c_rfdriver_mute,
 output wire c_rfdriver_bypass,
 output wire[3:0] c_rfdriver_g,
 output wire c_rfdriver_se,
 output wire c_lo_ext,
 output wire c_lo_int,
 output wire c_lo_cmlsel,
 output wire c_qvco_en,
 output wire[3:0] c_qvco_band,
 output wire c_qvco_atb_en,
 output wire c_lo_pre,
 output wire c_lo_mmd_en,
 output wire[5:0] c_lo_mmd_n,
 output wire c_lo_pfdcp_en,
 output wire[1:0] c_lo_icp,
 output wire c_lo_vreg_en,
 output wire c_lo_obs_en,
 output wire c_refvcm_en,
 output wire c_rx_ref_en,
 output wire[2:0] c_clockmux_ps,
 output wire[3:0] c_clockmux_ws,
 output wire[2:0] c_clockmux_ss,
 output wire[3:0] c_clockmux_cs,
 output wire[1:0] c_clockmux_hs,
 output wire c_prescale_en,
 output wire[3:0] c_prescale_d,
 output wire c_prescale_conv_en,
 output wire[3:0] c_prescale_conv_d,
 output wire c_prescale_hf_en,
 output wire[3:0] c_prescale_hf_d,
 output wire c_wordclk_en,
 output wire c_wordclk_d10,
 output wire c_wordclk_d20,
 output wire c_pllvreg_byp_tx,
 output wire c_pllvreg_byp_cdr,
 output wire c_pll_tx_en,
 output wire c_pll_tx_n4,
 output wire c_pll_tx_n8,
 output wire c_pll_tx_band,
 output wire c_pll_cdr_en,
 output wire c_pll_cdr_n4,
 output wire c_pll_cdr_n8,
 output wire c_pll_cdr_n5,
 output wire c_pll_cdr_n10,
 output wire[2:0] c_pll_cdr_kp,
 output wire c_pll_cdr_band,
 output wire c_cdr_en,
 output wire c_cdr_pfd_mode,
 output wire c_cdr_ref_sel,
 output wire[2:0] c_cdr_g,
 output wire[5:0] c_cdr_otr,
 output wire c_cdr_fup,
 output wire c_cdr_fdn,
 output wire[2:0] c_char_en,
 output wire c_ring_osc_en,
 output wire c_vco_replica_en,
 output wire c_clk_obs_en,
 output wire c_clk_obs_off,
 output wire[3:0] c_clk_obs_s,
 output wire[2:0] c_clk_obs_n,
 output wire[5:0] c_obs_pre4_en,
 output wire c_term_en,
 output wire[1:0] c_term_mode,
 output wire c_term_hs_en,
 output wire c_term_hs_term_en,
 output wire[3:0] c_term_hs_trim,
 output wire c_rxlevel_en,
 output wire c_rxlevel_half,
 output wire c_ctle_en,
 output wire c_ctle_bypass,
 output wire[2:0] c_ctle_peak,
 output wire[2:0] c_ctle_lf_zero,
 output wire c_rxselect_en,
 output wire c_rxselect_direct,
 output wire c_wmon_en,
 output wire[1:0] c_wmon_sel,
 output wire c_detect_en,
 output wire[1:0] c_detect_thr,
 output wire[1:0] c_detect_se,
 output wire c_detect_src_tx,
 output wire c_detect_inject,
 output wire c_vthdac_en,
 output wire[7:0] c_vthdac_a,
 output wire[7:0] c_vthdac_b,
 output wire c_slicer_en,
 output wire[9:0] c_slicer_trim_d0,
 output wire[9:0] c_slicer_trim_d1,
 output wire[9:0] c_slicer_trim_d2,
 output wire[9:0] c_slicer_trim_d3,
 output wire[9:0] c_slicer_trim_e0,
 output wire[9:0] c_slicer_trim_e1,
 output wire[9:0] c_slicer_trim_e2,
 output wire[9:0] c_slicer_trim_e3,
 output wire[1:0] c_slicer_vsel_e0,
 output wire[1:0] c_slicer_vsel_e1,
 output wire[1:0] c_slicer_vsel_e2,
 output wire[1:0] c_slicer_vsel_e3,
 output wire[4:0] c_ptrim_t0,
 output wire[4:0] c_ptrim_t1,
 output wire[4:0] c_ptrim_t2,
 output wire[4:0] c_ptrim_t3,
 output wire[4:0] c_ptrim_t4,
 output wire[4:0] c_ptrim_t5,
 output wire[4:0] c_ptrim_t6,
 output wire[4:0] c_ptrim_t7,
 output wire c_wrx_cap_en,
 output wire c_wrx_cap_rcs,
 output wire c_wrx_cap_b2,
 output wire c_wrx_cap_b1,
 output wire[2:0] c_wrx_cap_psel,
 output wire c_wrx_cap_slipp,
 output wire c_wrx_cap_slipm,
 output wire c_wiredtx_mode_h,
 output wire c_wiredtx_mode_f,
 output wire c_wiredtx_ser_en,
 output wire c_wiredtx_ext,
 output wire c_wiredtx_post_pol,
 output wire[7:0] c_wiredtx_main_code,
 output wire[7:0] c_wiredtx_post_code,
 output wire c_wiredtx_bias_en,
 output wire c_txpad_req_main,
 output wire c_txpad_req_post,
 output wire c_txpad_req_detect,
 output wire c_txpad_req_term,
 output wire c_hsbias_en,
 output wire[7:0] c_hsbias_c,
 output wire[1:0] c_wtxfb_branch,
 output wire[1:0] c_wtxfb_state,
 output wire c_wtxfb_idle,
 output wire c_wtxfb_stage_tmds,
 output wire c_usb_hs_en,
 output wire c_usb_fs_en,
 output wire c_usb_hs_drv,
 output wire c_usb_tx_dp,
 output wire c_usb_tx_dn,
 output wire c_usb_tx_oe,
 output wire[1:0] c_usb_hs_str,
 output wire c_usb_pullup_p,
 output wire c_usb_pullup_n,
 output wire c_usb_pulldown_p,
 output wire c_usb_pulldown_n,
 output wire c_usb_ls_slow,
 output wire[2:0] c_usb_term_trim
);
 // ---------------- reset (rtl/pt_por_path.sv), reset-seen key (INT6)
 wire rst_n, ovr_armed, por_masked;
 pt_por_path por_path(.reset_n_pad(reset_n_pad), .por_n(por_n), .por_bypass(por_bypass), .spi_cs_n(spi_cs_n),
  .spi_sclk(spi_sclk), .spi_mosi(spi_mosi), .rst_n(rst_n), .ovr_armed(ovr_armed), .por_masked(por_masked));
 wire reset_seen;
 pt_reset_seen rseen(.rst_n(rst_n), .clk(spi_sclk), .seen(reset_seen));

 // ---------------- island state. Without a reset since power-up (reset_seen = 0) no island is enabled.
 wire[`PT_ISLAND_W-1:0] island_pgood = {s_pg_debug, s_pg_conv, 1'b0, s_pg_pll, s_pg_rf_rx & s_pg_rf_tx & s_pg_lod & s_pg_lo,
  s_pg_wired_rx & s_pg_wired_cap & s_pg_wired_tx};
 wire[`PT_ISLAND_W-1:0] island_en_reg, island_on_reg; // register file: switch enable; switch on AND (pgood OR override)
 wire[`PT_ISLAND_W-1:0] ion = island_on_reg & {`PT_ISLAND_W{reset_seen}};
 assign island_en = island_en_reg & {`PT_ISLAND_W{reset_seen}};
 assign island_on = ion | {{(`PT_ISLAND_W-1){1'b0}}, wired_on_ext};
 assign island_off = ~island_on;

 // ---------------- CP4-1: island-sourced inputs, AND with island_on on the first gate (generated/macro_clamps.txt;
 // verification/check_macro_clamps.py compares this list with it). conv = 4, debug = 5, pll = 2, wired = 0.
 wire[23:0] rf_rx_a, rf_rx_b; wire rf_ph_i, rf_ph_q;
 assign rf_rx_a[1:0] = rf_rx_sample[1:0], rf_rx_a[13:12] = rf_rx_sample[13:12];     // tied low at chip level
 assign rf_rx_b[1:0] = rf_rx_sample_b[1:0], rf_rx_b[13:12] = rf_rx_sample_b[13:12];
 pt_iso_and #(10) iso_rf_rx_sample_i(.a(rf_rx_sample[11:2]), .on(island_on[4]), .y(rf_rx_a[11:2]));
 pt_iso_and #(10) iso_rf_rx_sample_q(.a(rf_rx_sample[23:14]), .on(island_on[4]), .y(rf_rx_a[23:14]));
 pt_iso_and #(10) iso_rf_rx_sample_b_i(.a(rf_rx_sample_b[11:2]), .on(island_on[4]), .y(rf_rx_b[11:2]));
 pt_iso_and #(10) iso_rf_rx_sample_b_q(.a(rf_rx_sample_b[23:14]), .on(island_on[4]), .y(rf_rx_b[23:14]));
 pt_iso_and #(2) iso_rf_rx_ph(.a({rf_rx_ph_q, rf_rx_ph_i}), .on(island_on[4]), .y({rf_ph_q, rf_ph_i}));
 wire adc_i_ovl, adc_i_b_ovl, adc_q_ovl, adc_q_b_ovl, adc_i_done, adc_i_b_done, adc_q_done, adc_q_b_done, refbuf_ready;
 pt_iso_and #(9) iso_s_conv(.a({s_refbuf_ready, s_adc_q_b_done, s_adc_q_done, s_adc_i_b_done, s_adc_i_done, s_adc_q_b_ovl, s_adc_q_ovl, s_adc_i_b_ovl, s_adc_i_ovl}),
  .on(island_on[4]), .y({refbuf_ready, adc_q_b_done, adc_q_done, adc_i_b_done, adc_i_done, adc_q_b_ovl, adc_q_ovl, adc_i_b_ovl, adc_i_ovl}));
 wire[5:0] fc; wire aux_present, wtx_ext_present;
 assign fc[0] = fc_src[0], fc[4] = fc_src[4];        // tx ring FBCK (outside clamp, shared with CLK_OBS), aosc (core rail)
 pt_iso_and #(2) iso_fc_src_debug(.a(fc_src[3:2]), .on(island_on[5]), .y(fc[3:2]));
 pt_iso_and #(2) iso_s_debug(.a({s_wtx_ext_present, s_aux_present}), .on(island_on[5]), .y({wtx_ext_present, aux_present}));
 wire ct_wclk_c, rf_tx_clk_c, pll_cdr_lock, pll_tx_lock;
 pt_iso_and #(1) iso_ct_wclk(.a(ct_wclk), .on(island_on[2]), .y(ct_wclk_c));
 pt_iso_and #(1) iso_fc_src_1(.a(fc_src[1]), .on(island_on[2]), .y(fc[1]));
 pt_iso_and #(1) iso_fc_src_5(.a(fc_src[5]), .on(island_on[1]), .y(fc[5]));   // lo_mmd.FB: lo island = rf enable group
 pt_iso_and #(1) iso_rf_tx_clk(.a(rf_tx_clk), .on(island_on[2]), .y(rf_tx_clk_c));
 pt_iso_and #(2) iso_s_pll(.a({s_pll_tx_lock, s_pll_cdr_lock}), .on(island_on[2]), .y({pll_tx_lock, pll_cdr_lock}));
 wire det_diff_pos, det_diff_neg, det_se_p, det_se_n, wrx_slp, wrx_slm, wtx_ext_data, wire_rx_clk_c, wire_tx_clk_c;
 pt_iso_and #(7) iso_s_wired(.a({s_wtx_ext_data, s_wrx_slm, s_wrx_slp, s_detect_se_n, s_detect_se_p, s_detect_diff_neg, s_detect_diff_pos}),
  .on(island_on[0]), .y({wtx_ext_data, wrx_slm, wrx_slp, det_se_n, det_se_p, det_diff_neg, det_diff_pos}));
 pt_iso_and #(1) iso_wire_rx_clk(.a(wire_rx_clk), .on(island_on[0]), .y(wire_rx_clk_c));
 pt_iso_and #(1) iso_wire_tx_clk(.a(wire_tx_clk), .on(island_on[0]), .y(wire_tx_clk_c));
 wire[39:0] wrx_dx; wire[19:0] wrx_ew;
 pt_iso_and #(40) iso_wire_rx_data(.a(wire_rx_data), .on(island_on[0]), .y(wrx_dx));
 pt_iso_and #(20) iso_wire_rx_edge(.a(wire_rx_edge), .on(island_on[0]), .y(wrx_ew));

 // ---------------- register file, transport, pattern, counters (pt_digital)
 wire[`PT_ANALOG_CFG_W-1:0] analog_cfg; wire[`PT_DEBUG_CFG_W-1:0] debug_cfg;
`include "pt_regmap_fields.svh"
 wire[6:0] rx_gain; wire rx_gain_active;
 wire[39:0] h2d_quad, d2h_quad;
 // Reduced-rate fallback (debug.host_link.rate, stopped-only): the host link and the whole
 // transport core run from link_clk = host_word_clk / {1,2,4} (core clock = link_clk / 2). A rate
 // change holds both in reset (host_rst_n) while the clock select switches (pt_host_rate_clock).
 // The transport core's reset is released synchronously to its own clock (pt_host_link core_rst_n).
 wire ddr_clk, sdr_word_clk, core_clk, core_rst_n, rate_hold_n;
 pt_host_rate_clock host_rate(.clk(host_word_clk), .rst_n(rst_n), .rate(f_debug_host_link__rate),
  .out_clk(ddr_clk), .word_clk(sdr_word_clk), .hold_n(rate_hold_n));
 wire host_rst_n = rst_n & rate_hold_n;
 // Datapath handshakes made in the macro (D-VALID): no analog block produces a valid or a request.
 wire[39:0] core_rx_quad, core_tx_quad; wire core_rx_valid, core_tx_valid, core_tx_request, core_idle;
 wire[23:0] rf_rx_merged; wire rf_rx_valid, rf_mute;
 wire fault_eff, mon_fault, bg_ok, cdr_freq_locked, fca_locked_ref, fcb_upd_ref; wire[13:0] fcb_diff_ref;
 wire[1:0] vth_fast; wire[7:0] vth_a, vth_b;
 wire rx_en_aux_reg, rx_en_wclk_reg, aosc_div;
 // status of the control blocks
 wire[9:0] mon_cause, mon_qualified; wire mon_cause_clk, mon_ready, mon_dead, mon_ref_alive, mon_in_alive;
 wire[2:0] wtx_state, wrx_state; wire wtx_seq_fault, tx_ring_ready;
 wire wrx_fll_done, wrx_fll_lost, wrx_freq_ok, wrx_wclk_alive, wrx_sig_ok, wrx_idle, wrx_slp_seen, wrx_slm_seen;
 wire[13:0] wrx_fll_err; wire[7:0] wrx_fll_win, wrx_pick_acc, wrx_slip_cnt; wire[4:0] wrx_viol;
 wire[1:0] usb_line; wire usb_j, usb_k, usb_se0, usb_se1, usb_diff, usb_squelch, usb_disconnect;
 wire usb_rx_active, usb_tx_busy, usb_tx_underrun, usb_tx_blocked, usb_tx_armed;
 wire wire_rx_valid_q, wire_tx_request_q;
 // Observation vectors (spec/debug-controls.json obs_status / wire_status order; see pt_digital).
 wire[11:0] analog_status = {aosc_div, adc_q_ovl | adc_q_b_ovl, adc_i_ovl | adc_i_b_ovl, adc_q_done, adc_i_done,
  wrx_fll_lost, wrx_freq_ok, por_n, refbuf_ready, bg_ok, s_ref_present, pll_tx_lock};
 wire[12:0] wire_analog_status = {wtx_ext_data, pll_cdr_lock, usb_disconnect, det_diff_pos | det_diff_neg, usb_squelch,
  usb_diff, usb_se0, usb_k, usb_j, wrx_idle, wrx_sig_ok, wrx_fll_lost, wrx_freq_ok};
 wire[15:0] rf_trim, wire_trim, clock_trim, status; wire enable, mode8, commit_toggle; wire[11:0] cal_trial;
 wire[39:0] wire_tx_quad; wire wire_tx_valid, wire_idle; wire[23:0] rf_tx_sample_q;
 assign rf_tx_sample = rf_tx_sample_q & {24{island_on[4]}};
 pt_digital digital(.rst_n(rst_n), .ref_clk(ref_clk), .host_sclk(spi_sclk), .host_cs_n(spi_cs_n), .host_mosi(spi_mosi),
  .host_miso(spi_miso), .host_miso_oe(spi_miso_oe), .host_tx_clk(core_clk), .host_rx_clk(core_clk), .core_rst_n(core_rst_n),
  .wire_rx_clk(wire_rx_clk_c), .wire_tx_clk(wire_tx_clk_c), .rf_rx_clk(rf_rx_clk), .rf_tx_clk(rf_tx_clk_c),
  .h2d_quad(h2d_quad), .d2h_quad(d2h_quad), .wire_rx_data(core_rx_quad), .wire_rx_valid(core_rx_valid),
  .wire_tx_data(wire_tx_quad), .wire_tx_valid(wire_tx_valid), .wire_idle(wire_idle), .wire_tx_request(core_tx_request),
  .rf_rx_sample(rf_rx_merged), .rf_rx_valid(rf_rx_valid), .rf_tx_sample(rf_tx_sample_q), .rf_tx_valid(),
  .rf_mute(rf_mute), .rf_tx_request(1'b1), .rf_tx_clk_out(rf_tx_clk_out), .enable(enable), .mode8(mode8), .rf_trim(rf_trim),
  .wire_trim(wire_trim), .clock_trim(clock_trim), .calibration_above_target(1'b0), .calibration_trial(cal_trial),
  .status(status), .por_n(por_n), .por_path({por_masked, ovr_armed, por_bypass}), .fault(fault_eff), .island_pgood(island_pgood),
  .fc_src(fc), .cdr_freq_locked(cdr_freq_locked), .fca_locked_ref(fca_locked_ref), .fcb_diff_ref(fcb_diff_ref), .fcb_upd_ref(fcb_upd_ref),
  .analog_status(analog_status), .wire_analog_status(wire_analog_status), .obs_extra({reset_seen, wtx_ext_present, aux_present}),
  .analog_cfg(analog_cfg), .debug_cfg(debug_cfg),
  .island_en(island_en_reg), .island_on(island_on_reg), .atb0_sw(atb0_sw), .atb1_sw(atb1_sw), .atb0_grp(atb0_grp), .atb1_grp(atb1_grp),
  .atb0_en(atb0_en), .atb1_en(atb1_en), .rx_en_aux(rx_en_aux_reg), .rx_en_wclk(rx_en_wclk_reg),
  .rx_en_wtx_ext(rx_en_wtx_ext), .clk_obs_oe(clk_obs_oe), .dbg_obs0(dbg_obs0),
  .dbg_obs0_oe(dbg_obs0_oe), .dbg_obs1(dbg_obs1), .dbg_obs1_oe(dbg_obs1_oe), .commit_toggle(commit_toggle),
  .linecode(f_digital_transport_config__linecode), .rx_gain(rx_gain), .rx_gain_active(rx_gain_active),
  .vth_fast(vth_fast), .vth_a(vth_a), .vth_b(vth_b),
  .mon_cause(mon_cause), .mon_qualified(mon_qualified), .mon_cause_clk(mon_cause_clk), .mon_ready(mon_ready), .mon_dead(mon_dead),
  .mon_ref_alive(mon_ref_alive), .mon_in_alive(mon_in_alive), .mon_fault(fault_eff),
  .wtx_state(wtx_state), .wrx_state(wrx_state), .wtx_seq_fault(wtx_seq_fault), .wtx_ring_ready(tx_ring_ready),
  .wrx_flags({wrx_slm_seen, wrx_slp_seen, wrx_idle, wrx_sig_ok, wrx_wclk_alive, wrx_freq_ok, wrx_fll_lost, wrx_fll_done}),
  .wrx_fll_win(wrx_fll_win), .wrx_pick_acc(wrx_pick_acc), .wrx_slip_cnt(wrx_slip_cnt), .wrx_fll_err(wrx_fll_err), .wrx_viol(wrx_viol),
  .usb_line(usb_line), .usb_flags({usb_disconnect, usb_squelch, usb_diff, usb_se1, usb_se0, usb_k, usb_j}),
  .usb_stream({usb_tx_armed, usb_tx_blocked, usb_tx_underrun, usb_tx_busy, usb_rx_active}));
 assign rx_en_wclk = 1'b0;   // CP4-3: the forwarded wire clock uses the AUX_CLK pair (rx_en_aux); no WCLK_IN receiver
 pt_toggle_div aosc_dv(fc[4], rst_n, aosc_div);
 pt_host_link host(.rst_n(host_rst_n), .mode(f_debug_host_link__mode), .d2h_enable(f_hostio_controls__d2h_enable),
  .h2d_clk(h2d_clk), .h2d_pin(h2d_pin), .link_clk(ddr_clk), .word_clk(sdr_word_clk), .core_clk(core_clk), .core_rst_n(core_rst_n), .h2d_quad(h2d_quad), .d2h_quad(d2h_quad),
  .d2h_pin(d2h_pin), .d2h_clk_pin(d2h_clk_pin), .d2h_stagger(f_hostio_controls__d2h_stagger),
  .d2h_oe(d2h_oe), .h2d_overflow(), .h2d_underflow());
 assign d2h_pdrv = f_hostio_controls__drive;
 assign d2h_sl = f_hostio_controls__slew;

 // ---------------- supply / clock monitor -> fault (D-FAULT, CP4-11). Time base = always-on oscillator.
 // rf lock = frequency counter a in lock, wire lock = frequency counter b in lock (sources by register).
 pt_monitor monitor(.rst_n(rst_n), .mon_clk(fc[4]), .ref_clk(ref_clk), .in_clk(h2d_clk), .rf_lock(fca_locked_ref),
  .wire_lock(cdr_freq_locked), .island_pgood(island_pgood), .supply_win_ok(6'd0),
  .cfg_require_reference(f_monitor_config__require_reference), .cfg_require_input_clock(f_monitor_config__require_input_clock),
  .cfg_require_rf_lock(f_monitor_config__require_rf_lock), .cfg_require_wire_lock(f_monitor_config__require_wire_lock),
  .cfg_required_supply_mask(f_monitor_config__required_supply_mask), .cfg_loss_timeout_ticks(f_monitor_config__loss_timeout_ticks),
  .cfg_qualification_ticks(f_monitor_config__qualification_ticks), .clear_fault(f_monitor_reset__clear_fault),
  .fault(mon_fault), .ready(mon_ready), .cause(mon_cause), .cause_mon_clk(mon_cause_clk), .qualified(mon_qualified),
  .ref_alive(mon_ref_alive), .in_alive(mon_in_alive), .mon_dead(mon_dead));
 assign fault_eff = fault | mon_fault;

 // ---------------- static decode
 // PD9 regulated ring supplies: a ring whose pt_pll_vreg is out of bypass is held off for >= 50 us after
 // the pll island powers up or the regulator leaves bypass (rtl/pt_vreg_seq.sv).
 wire vreg_tx_ok, vreg_rx_ok;
 pt_vreg_seq vreg_seq(.rst_n(rst_n), .ref_clk(ref_clk), .pll_on(ion[2]),
  .tx_bypass(f_pllvreg_config__tx_bypass), .rx_bypass(f_pllvreg_config__rx_bypass), .tx_ok(vreg_tx_ok), .rx_ok(vreg_rx_ok));
 pt_bgap_interlock bgap(.rst_n(rst_n), .sclk(spi_sclk), .bgap_ena(f_core_refchain__bgap_ena & reset_seen), .ok(bg_ok));
 pt_ctl_decode decode(.analog_cfg(analog_cfg), .debug_cfg(debug_cfg), .island_on(ion), .vreg_rx_ok(vreg_rx_ok), .bg_ok(bg_ok),
  .reset_seen(reset_seen), .rx_gain(rx_gain), .rx_gain_active(rx_gain_active), .rf_mute(rf_mute),
  .rx_en_aux_reg(rx_en_aux_reg), .rx_en_wclk_reg(rx_en_wclk_reg), .vth_fast(vth_fast), .vth_fast_a(vth_a), .vth_fast_b(vth_b),
  .rx_en_aux(rx_en_aux), .wire_rx_ptrim_en(wire_rx_ptrim_en),
  .c_aosc_en(c_aosc_en),
  .c_biasgen_ena(c_biasgen_ena),
  .c_biasgen_ref_sel_vbg(c_biasgen_ref_sel_vbg),
  .c_biasgen_ref_sel_coarse(c_biasgen_ref_sel_coarse),
  .c_biasgen_ref_sel_fine(c_biasgen_ref_sel_fine),
  .c_biasgen_idac2_source(c_biasgen_idac2_source),
  .c_biasgen_idac1_source(c_biasgen_idac1_source),
  .c_biasgen_bandgap_sink1(c_biasgen_bandgap_sink1),
  .c_biasgen_bandgap_sink2(c_biasgen_bandgap_sink2),
  .c_biasgen_voltgen_source(c_biasgen_voltgen_source),
  .c_biasgen_voltgen_sink1(c_biasgen_voltgen_sink1),
  .c_biasgen_voltgen_sink2(c_biasgen_voltgen_sink2),
  .c_bgap_ena(c_bgap_ena),
  .c_bgap_trim(c_bgap_trim),
  .c_bias_dist_en_rf(c_bias_dist_en_rf),
  .c_bias_dist_en_conv(c_bias_dist_en_conv),
  .c_bias_dist_en_pll(c_bias_dist_en_pll),
  .c_bias_dist_en_wire(c_bias_dist_en_wire),
  .c_bias_dist_en_debug(c_bias_dist_en_debug),
  .c_lna_en(c_lna_en),
  .c_lna_gain_lo(c_lna_gain_lo),
  .c_lna_byp(c_lna_byp),
  .c_lna_ct(c_lna_ct),
  .c_lna_se(c_lna_se),
  .c_lna_rt(c_lna_rt),
  .c_lna_att(c_lna_att),
  .c_lna_lobias(c_lna_lobias),
  .c_rxmix_i_en(c_rxmix_i_en),
  .c_rxmix_q_en(c_rxmix_q_en),
  .c_rxmix_i_ofs(c_rxmix_i_ofs),
  .c_rxmix_q_ofs(c_rxmix_q_ofs),
  .c_bbfilter_i_en(c_bbfilter_i_en),
  .c_bbfilter_q_en(c_bbfilter_q_en),
  .c_bbfilter_dir_tx(c_bbfilter_dir_tx),
  .c_bbfilter_inj(c_bbfilter_inj),
  .c_bbfilter_obs_sel(c_bbfilter_obs_sel),
  .c_bbfilter_rx_direct(c_bbfilter_rx_direct),
  .c_bbfilter_byp_s1(c_bbfilter_byp_s1),
  .c_bbfilter_byp_s23(c_bbfilter_byp_s23),
  .c_bbfilter_i_cut(c_bbfilter_i_cut),
  .c_bbfilter_q_cut(c_bbfilter_q_cut),
  .c_bbfilter_i_gain(c_bbfilter_i_gain),
  .c_bbfilter_q_gain(c_bbfilter_q_gain),
  .c_bbfilter_i_gainc(c_bbfilter_i_gainc),
  .c_bbfilter_q_gainc(c_bbfilter_q_gainc),
  .c_bbfilter_i_qt(c_bbfilter_i_qt),
  .c_bbfilter_q_qt(c_bbfilter_q_qt),
  .c_bbfilter_i_dcf(c_bbfilter_i_dcf),
  .c_bbfilter_q_dcf(c_bbfilter_q_dcf),
  .c_bb_tap_obs_en(c_bb_tap_obs_en),
  .c_bb_tap_inj_en(c_bb_tap_inj_en),
  .c_bb_tap_i_bias_en(c_bb_tap_i_bias_en),
  .c_bb_tap_q_bias_en(c_bb_tap_q_bias_en),
  .c_bb_tap_wmon_bias_en(c_bb_tap_wmon_bias_en),
  .c_wmon_obs_en(c_wmon_obs_en),
  .c_adc_i_en(c_adc_i_en),
  .c_adc_q_en(c_adc_q_en),
  .c_adc_i_test(c_adc_i_test),
  .c_adc_q_test(c_adc_q_test),
  .c_adc_ilen(c_adc_ilen),
  .c_dac_i_en(c_dac_i_en),
  .c_dac_q_en(c_dac_q_en),
  .c_dac_i_hold_zero(c_dac_i_hold_zero),
  .c_dac_q_hold_zero(c_dac_q_hold_zero),
  .c_refbuf_en(c_refbuf_en),
  .c_refbuf_ovr(c_refbuf_ovr),
  .c_adc_acq(c_adc_acq),
  .c_txmix_i_en(c_txmix_i_en),
  .c_txmix_q_en(c_txmix_q_en),
  .c_txmix_sel_dac(c_txmix_sel_dac),
  .c_txmix_sat(c_txmix_sat),
  .c_txsum_en(c_txsum_en),
  .c_rfdriver_en(c_rfdriver_en),
  .c_rfdriver_mute(c_rfdriver_mute),
  .c_rfdriver_bypass(c_rfdriver_bypass),
  .c_rfdriver_g(c_rfdriver_g),
  .c_rfdriver_se(c_rfdriver_se),
  .c_lo_ext(c_lo_ext),
  .c_lo_int(c_lo_int),
  .c_lo_cmlsel(c_lo_cmlsel),
  .c_qvco_en(c_qvco_en),
  .c_qvco_band(c_qvco_band),
  .c_qvco_atb_en(c_qvco_atb_en),
  .c_lo_pre(c_lo_pre),
  .c_lo_mmd_en(c_lo_mmd_en),
  .c_lo_mmd_n(c_lo_mmd_n),
  .c_lo_pfdcp_en(c_lo_pfdcp_en),
  .c_lo_icp(c_lo_icp),
  .c_lo_vreg_en(c_lo_vreg_en),
  .c_lo_obs_en(c_lo_obs_en),
  .c_refvcm_en(c_refvcm_en),
  .c_rx_ref_en(c_rx_ref_en),
  .c_clockmux_ps(c_clockmux_ps),
  .c_clockmux_ws(c_clockmux_ws),
  .c_clockmux_ss(c_clockmux_ss),
  .c_clockmux_cs(c_clockmux_cs),
  .c_clockmux_hs(c_clockmux_hs),
  .c_prescale_en(c_prescale_en),
  .c_prescale_d(c_prescale_d),
  .c_prescale_conv_en(c_prescale_conv_en),
  .c_prescale_conv_d(c_prescale_conv_d),
  .c_prescale_hf_en(c_prescale_hf_en),
  .c_prescale_hf_d(c_prescale_hf_d),
  .c_wordclk_en(c_wordclk_en),
  .c_wordclk_d10(c_wordclk_d10),
  .c_wordclk_d20(c_wordclk_d20),
  .c_pllvreg_byp_tx(c_pllvreg_byp_tx),
  .c_pllvreg_byp_cdr(c_pllvreg_byp_cdr),
  .c_pll_cdr_en(c_pll_cdr_en),
  .c_pll_cdr_n4(c_pll_cdr_n4),
  .c_pll_cdr_n8(c_pll_cdr_n8),
  .c_pll_cdr_n5(c_pll_cdr_n5),
  .c_pll_cdr_n10(c_pll_cdr_n10),
  .c_pll_cdr_kp(c_pll_cdr_kp),
  .c_pll_cdr_band(c_pll_cdr_band),
  .c_cdr_en(c_cdr_en),
  .c_cdr_pfd_mode(c_cdr_pfd_mode),
  .c_cdr_ref_sel(c_cdr_ref_sel),
  .c_cdr_g(c_cdr_g),
  .c_cdr_otr(c_cdr_otr),
  .c_ring_osc_en(c_ring_osc_en),
  .c_vco_replica_en(c_vco_replica_en),
  .c_clk_obs_en(c_clk_obs_en),
  .c_clk_obs_off(c_clk_obs_off),
  .c_clk_obs_s(c_clk_obs_s),
  .c_clk_obs_n(c_clk_obs_n),
  .c_obs_pre4_en(c_obs_pre4_en),
  .c_char_en(c_char_en),
  .c_term_en(c_term_en),
  .c_term_mode(c_term_mode),
  .c_term_hs_en(c_term_hs_en),
  .c_term_hs_term_en(c_term_hs_term_en),
  .c_term_hs_trim(c_term_hs_trim),
  .c_rxlevel_en(c_rxlevel_en),
  .c_rxlevel_half(c_rxlevel_half),
  .c_ctle_en(c_ctle_en),
  .c_ctle_bypass(c_ctle_bypass),
  .c_ctle_peak(c_ctle_peak),
  .c_ctle_lf_zero(c_ctle_lf_zero),
  .c_rxselect_en(c_rxselect_en),
  .c_rxselect_direct(c_rxselect_direct),
  .c_wmon_en(c_wmon_en),
  .c_wmon_sel(c_wmon_sel),
  .c_detect_en(c_detect_en),
  .c_detect_thr(c_detect_thr),
  .c_detect_se(c_detect_se),
  .c_detect_src_tx(c_detect_src_tx),
  .c_detect_inject(c_detect_inject),
  .c_vthdac_en(c_vthdac_en),
  .c_vthdac_a(c_vthdac_a),
  .c_vthdac_b(c_vthdac_b),
  .c_slicer_en(c_slicer_en),
  .c_slicer_trim_d0(c_slicer_trim_d0),
  .c_slicer_trim_d1(c_slicer_trim_d1),
  .c_slicer_trim_d2(c_slicer_trim_d2),
  .c_slicer_trim_d3(c_slicer_trim_d3),
  .c_slicer_trim_e0(c_slicer_trim_e0),
  .c_slicer_trim_e1(c_slicer_trim_e1),
  .c_slicer_trim_e2(c_slicer_trim_e2),
  .c_slicer_trim_e3(c_slicer_trim_e3),
  .c_slicer_vsel_e0(c_slicer_vsel_e0),
  .c_slicer_vsel_e1(c_slicer_vsel_e1),
  .c_slicer_vsel_e2(c_slicer_vsel_e2),
  .c_slicer_vsel_e3(c_slicer_vsel_e3),
  .c_ptrim_t0(c_ptrim_t0),
  .c_ptrim_t1(c_ptrim_t1),
  .c_ptrim_t2(c_ptrim_t2),
  .c_ptrim_t3(c_ptrim_t3),
  .c_ptrim_t4(c_ptrim_t4),
  .c_ptrim_t5(c_ptrim_t5),
  .c_ptrim_t6(c_ptrim_t6),
  .c_ptrim_t7(c_ptrim_t7),
  .c_wrx_cap_en(c_wrx_cap_en),
  .c_wrx_cap_rcs(c_wrx_cap_rcs),
  .c_wrx_cap_b2(c_wrx_cap_b2),
  .c_wrx_cap_b1(c_wrx_cap_b1),
  .c_wiredtx_ext(c_wiredtx_ext),
  .c_wiredtx_post_pol(c_wiredtx_post_pol),
  .c_wiredtx_main_code(c_wiredtx_main_code),
  .c_wiredtx_post_code(c_wiredtx_post_code),
  .c_hsbias_en(c_hsbias_en),
  .c_hsbias_c(c_hsbias_c),
  .c_usb_pullup_p(c_usb_pullup_p),
  .c_usb_pullup_n(c_usb_pullup_n),
  .c_usb_pulldown_p(c_usb_pulldown_p),
  .c_usb_pulldown_n(c_usb_pulldown_n),
  .c_usb_ls_slow(c_usb_ls_slow),
  .c_usb_term_trim(c_usb_term_trim),
  .c_usb_hs_str(c_usb_hs_str));

 // ---------------- wired TX launch (rtl/pt_wtx_ctl.sv): ring enable, SER_EN, pad requests, wire_tx_request
 wire wire_tx_up;
 pt_wtx_ctl wtx(.rst_n(rst_n), .ref_clk(ref_clk), .wire_tx_clk(wire_tx_clk_c), .island_on_wired(island_on[0]), .island_on_pll(ion[2]),
  .vreg_tx_ok(vreg_tx_ok), .fault(fault_eff), .fc_tx_in_tol(fca_locked_ref), .txpad_ready(1'b1),
  .cfg_ring_en(f_ring_l_config__enable), .cfg_ring_n(f_ring_l_config__modulus), .cfg_ring_band(f_ring_l_config__band),
  .cfg_ring_lock_time(f_ring_l_config__lock_time), .cfg_ring_ready_sel(f_ring_l_config__ready_select),
  .cfg_wtx_state(f_wiredtx_state__state), .cfg_rate_mode(f_consolidation_wiredtx_stage__rate_mode), .cfg_branch(f_txpad_config__branch),
  .cfg_idle(f_wiredtx_idle__idle), .cfg_wtx_ext(f_debug_wtx_ext__enable), .cfg_post_pol(f_wiredtx_config__post_polarity),
  .cfg_post_code(f_wiredtx_config__postcursor_code), .cfg_term_req(f_txpad_config__term_request),
  .cfg_stage_tmds(f_consolidation_wiredtx_stage__stage),
  .c_pll_tx_en(c_pll_tx_en), .c_pll_tx_n4(c_pll_tx_n4), .c_pll_tx_n8(c_pll_tx_n8), .c_pll_tx_band(c_pll_tx_band),
  .c_wiredtx_ser_en(c_wiredtx_ser_en), .c_wiredtx_mode_h(c_wiredtx_mode_h), .c_wiredtx_mode_f(c_wiredtx_mode_f), .c_wiredtx_bias_en(c_wiredtx_bias_en),
  .c_txpad_req_main(c_txpad_req_main), .c_txpad_req_post(c_txpad_req_post), .c_txpad_req_detect(c_txpad_req_detect), .c_txpad_req_term(c_txpad_req_term),
  .c_wtxfb_branch(c_wtxfb_branch), .c_wtxfb_state(c_wtxfb_state), .c_wtxfb_idle(c_wtxfb_idle), .c_wtxfb_stage_tmds(c_wtxfb_stage_tmds),
  .wire_tx_request(wire_tx_request_q), .wire_tx_up(wire_tx_up), .tx_ring_ready(tx_ring_ready), .st_state(wtx_state), .st_seq_fault(wtx_seq_fault));

 // ---------------- wired RX control plane (rtl/pt_wrx_ctl.sv): FLL pulses, phase picker, wire_rx_valid
 wire wrx_en = (f_cdr_state__state == 2'd2) & ion[2] & (f_slicer_state__state == 2'd2) & ion[0];
 pt_wrx_ctl wrx(.ref_clk(ref_clk), .wire_rx_clk(wire_rx_clk_c), .rst_n(rst_n), .cfg_en(wrx_en), .cfg_restart(f_wrx_loop__restart),
  .cfg_freq_src(f_wrx_loop__freq_source), .cfg_fll_auto(f_wrx_loop__fll_auto), .cfg_fll_inv(f_wrx_loop__fll_invert),
  .cfg_fll_shift(f_wrx_loop__fll_shift), .cfg_fll_tol(f_wrx_loop__fll_tolerance), .cfg_fll_loss(f_wrx_loop__fll_loss),
  .cfg_fll_man_trig(f_wrx_loop__fll_manual_trigger), .cfg_fll_man_dir(f_wrx_loop__fll_manual_up), .cfg_fll_man_len(f_wrx_loop__fll_manual_length),
  .cfg_pick_auto(f_wrx_picker__auto), .cfg_pick_inv(f_wrx_picker__invert), .cfg_pick_thr(f_wrx_picker__threshold),
  .cfg_pick_hold(f_wrx_picker__hold), .cfg_man_psel(f_wrx_picker__manual_psel), .cfg_man_slipp_trig(f_wrx_picker__manual_slip_plus),
  .cfg_man_slipm_trig(f_wrx_picker__manual_slip_minus), .cfg_ew_half(f_wrx_picker__edge_half), .cfg_viol_thr(f_wrx_picker__violation_threshold),
  .cfg_idle_words(f_wrx_picker__idle_words), .cfg_lock_exp(f_wrx_picker__lock_exp), .cfg_loss_exp(f_wrx_picker__loss_exp),
  .cfg_valid_mode(f_wrx_picker__valid_mode), .fc_upd(fcb_upd_ref), .fc_diff(fcb_diff_ref), .fc_locked(cdr_freq_locked),
  .s_pll_cdr_lock(pll_cdr_lock), .s_wrx_slp(wrx_slp), .s_wrx_slm(wrx_slm), .wire_rx_data(wrx_dx), .wire_rx_edge(wrx_ew),
  .c_cdr_fup(c_cdr_fup), .c_cdr_fdn(c_cdr_fdn), .c_wrx_cap_psel(c_wrx_cap_psel), .c_wrx_cap_slipp(c_wrx_cap_slipp),
  .c_wrx_cap_slipm(c_wrx_cap_slipm), .wire_rx_valid(wire_rx_valid_q), .st_state(wrx_state), .st_fll_done(wrx_fll_done),
  .st_fll_lost(wrx_fll_lost), .st_freq_ok(wrx_freq_ok), .st_wclk_alive(wrx_wclk_alive), .st_fll_err(wrx_fll_err), .st_fll_win(wrx_fll_win),
  .st_sig_ok(wrx_sig_ok), .st_idle(wrx_idle), .st_viol(wrx_viol), .st_pick_acc(wrx_pick_acc), .st_slip_cnt(wrx_slip_cnt),
  .st_slp_seen(wrx_slp_seen), .st_slm_seen(wrx_slm_seen));
 wire[39:0] wrx_quad;
 pt_wrx_lane lane(.clk(wire_rx_clk_c), .rst_n(rst_n), .lane(f_slicer_capture__raw_lane), .dx(wrx_dx), .ew(wrx_ew), .quad(wrx_quad));

 // ---------------- USB direct stream (rtl/pt_usb.sv; MW-18, D-USB). With digital.transport_config.direct_stream_enable
 // the wired transport quads carry line symbols: egress -> pt_usb (FS/LS, chirp), pt_usb -> ingress. HS packets go
 // through pt_wiredtx and the pt_usb_txdrv pre-driver; pt_usb then only makes the enables and the envelope.
 wire usb_direct = f_digital_transport_config__direct_stream_enable;
 wire[39:0] usb_rx_quad; wire usb_rx_valid, usb_tx_ready;
 pt_usb usb(.rst_n(rst_n), .island_on(island_on[0]), .fault(fault_eff), .tx_clk(wire_tx_clk_c),
  .cfg_branch(f_usbdrive_select__branch), .cfg_active(f_usbdrive_state__state == 2'd2), .cfg_hs_tx_en(f_usbhs_config__tx_enable),
  .cfg_fs_drive_en(f_usbfs_config__drive_enable), .cfg_hs_sym(f_usb_config__hs_symbol), .cfg_force_en(f_usb_config__force_enable),
  .cfg_force_sym(f_usb_config__force_symbol), .cfg_ls_slow(f_usbfs_config__ls_slow), .cfg_term_on(c_term_en),
  .cfg_tx_div(f_usb_config__tx_divider), .cfg_bbm(f_usb_config__bbm), .tx_data(wire_tx_quad), .tx_valid(wire_tx_valid & usb_direct),
  .tx_ready(usb_tx_ready), .hs_tx_active(wire_tx_valid & ~wire_idle & ~usb_direct),
  .c_usb_hs_p(), .c_usb_hs_n(), .c_usb_fs_high_p(), .c_usb_fs_high_n(), .c_usb_fs_low_p(), .c_usb_fs_low_n(), // direct pad gates: replaced by pt_usb_txdrv
  .usb_hs_en(c_usb_hs_en), .usb_hs_drv(c_usb_hs_drv), .usb_fs_en(c_usb_fs_en), .usb_tx_dp(c_usb_tx_dp), .usb_tx_dn(c_usb_tx_dn), .usb_tx_oe(c_usb_tx_oe),
  .st_tx_busy(usb_tx_busy), .st_tx_underrun(usb_tx_underrun), .st_tx_blocked(usb_tx_blocked), .st_tx_armed(usb_tx_armed),
  .rx_clk(wire_rx_clk_c), .s_detect_diff_pos(det_diff_pos), .s_detect_diff_neg(det_diff_neg), .s_detect_se_p(det_se_p), .s_detect_se_n(det_se_n),
  .cfg_rx_en(f_usb_config__rx_enable), .cfg_rx_diff(f_usb_config__rx_differential), .cfg_rx_echo(f_usb_config__rx_echo),
  .cfg_ls(f_usbfs_config__slew), .cfg_thr_disc(f_detect_config__high_threshold_code == 2'd3), .cfg_rx_div(f_usb_config__rx_divider),
  .cfg_rx_quiet(f_usb_config__rx_quiet), .cfg_deb_se(f_usb_config__debounce_se), .cfg_deb_diff(f_usb_config__debounce_diff),
  .rx_data(usb_rx_quad), .rx_valid(usb_rx_valid), .st_rx_active(usb_rx_active), .st_line(usb_line), .st_j(usb_j), .st_k(usb_k),
  .st_se0(usb_se0), .st_se1(usb_se1), .st_diff(usb_diff), .st_squelch(usb_squelch), .st_disconnect(usb_disconnect));
 assign core_rx_quad = usb_direct ? usb_rx_quad : wrx_quad;
 assign core_rx_valid = usb_direct ? usb_rx_valid : wire_rx_valid_q;
 assign core_tx_request = usb_direct ? usb_tx_ready : wire_tx_request_q;
 // D-DATAOFF (TOP-25): the serializer data inputs are transmission gates and the DAC code inputs reach p-diffusion:
 // both buses read 0 while their island is off (the DAC's forwarded clock is a gate input and is not gated).
 assign wire_tx_data = wire_tx_quad & {40{island_on[0]}};

 // ---------------- RF RX sample register (rtl/pt_boundary.sv pt_adc_merge) and the detector clock
 pt_adc_merge adc_merge(.clk(rf_rx_clk), .rst_n(rst_n), .adc_en(c_adc_i_en | c_adc_q_en), .ilen(c_adc_ilen),
  .ph_i(rf_ph_i), .ph_q(rf_ph_q), .sample_a(rf_rx_a), .sample_b(rf_rx_b), .sample(rf_rx_merged), .valid(rf_rx_valid));
 pt_det_clk det(.clk(ct_wclk_c), .rst_n(rst_n), .en(c_detect_en), .cfg_rate_khz(f_cdr_config__nominal_rate_khz), .det_clk(ct_det_clk));
endmodule
`default_nettype wire
