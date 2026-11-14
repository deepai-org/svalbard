// Analog control decode (mode-walk rework, rows TOP-1, TOP-10..18; coordinator decision: the decode glue lives in
// the digital macro and the register map follows the cells). One named output per analog control pin group,
// already decoded (one-hot where the cell is one-hot), at the cell's width. The list, widths, resets and
// encodings are integration/top/ctl_ports.txt; the consumers are in integration/top/pt_chip.conn.
// Inputs are the register-file buses (island-gated: a field of a switched island reads 0 while that island is
// off; fault-forced), so every output of a switched island is 0 while the island is off. Outputs whose decode
// would otherwise be non-zero at field value 0 are ANDed with island_on here.
// Combinational and static except: the RXR-D2 fast-gain override (rx_gain, rf_rx_clk domain level) on the LNA
// attenuator / PGA gain pins, rf_mute (rf_tx_clk domain) on c_rfdriver_mute and the IX-11 fast thresholds.
// The wired TX, CDR and USB dynamic ports are made by pt_wtx_ctl, pt_wrx_ctl and pt_usb (see pt_digital_macro).
// Enable meaning (D-EN): c_<blk>_en = (state == active) & island_on. "warm" keeps the configuration and leaves
// the cell off: no published cell has a second (bias-only) enable pin.
`include "pt_regmap_defs.svh"
`default_nettype none
module pt_ctl_decode(
 input  wire[`PT_ANALOG_CFG_W-1:0] analog_cfg, input wire[`PT_DEBUG_CFG_W-1:0] debug_cfg,
 input  wire[`PT_ISLAND_W-1:0] island_on,   // register-file island state (switch on AND (pgood OR override))
 input  wire vreg_rx_ok,                    // pt_vreg_seq: CDR ring regulator settled
 input  wire bg_ok,                         // pt_bgap_interlock: bandgap enabled for >= 128 SCLK cycles
 input  wire reset_seen,                    // pt_reset_seen: a real reset has happened since power-up (INT6)
 input  wire[6:0] rx_gain, input wire rx_gain_active, // opcode-4 fast gain {LNA index[1:0], PGA index[4:0]}
 input  wire rf_mute,                       // transport mute (pt_rf_out_reg)
 input  wire rx_en_aux_reg, rx_en_wclk_reg, // register-file AUX_CLK / WCLK_IN receiver requests (one pad pair since CP4-3)
 input  wire[1:0] vth_fast, input wire[7:0] vth_fast_a, vth_fast_b, // IX-11 in-band thresholds ([0] A, [1] B active + values)
 // ---- always-on
 output wire c_aosc_en, c_biasgen_ena, c_biasgen_ref_sel_vbg, c_biasgen_ref_sel_coarse, c_biasgen_ref_sel_fine,
 output wire[4:0] c_biasgen_idac2_source, c_biasgen_idac1_source, output wire[2:0] c_biasgen_bandgap_sink1,
 output wire[1:0] c_biasgen_bandgap_sink2, output wire[4:0] c_biasgen_voltgen_source,
 output wire[2:0] c_biasgen_voltgen_sink1, c_biasgen_voltgen_sink2,
 output wire c_bgap_ena, output wire[15:0] c_bgap_trim,
 output wire c_bias_dist_en_rf, c_bias_dist_en_conv, c_bias_dist_en_pll, c_bias_dist_en_wire, c_bias_dist_en_debug,
 // ---- RF receive
 output wire c_lna_en, c_lna_gain_lo, c_lna_byp, output wire[3:0] c_lna_ct, output wire c_lna_se, c_lna_rt,
 output wire[4:0] c_lna_att, output wire c_lna_lobias,
 output wire c_rxmix_i_en, c_rxmix_q_en, output wire[5:0] c_rxmix_i_ofs, c_rxmix_q_ofs,
 output wire c_bbfilter_i_en, c_bbfilter_q_en, c_bbfilter_dir_tx, c_bbfilter_inj, output wire[1:0] c_bbfilter_obs_sel,
 output wire c_bbfilter_rx_direct, c_bbfilter_byp_s1, c_bbfilter_byp_s23,
 output wire[6:0] c_bbfilter_i_cut, c_bbfilter_q_cut, output wire[5:0] c_bbfilter_i_gain, c_bbfilter_q_gain,
 output wire[1:0] c_bbfilter_i_gainc, c_bbfilter_q_gainc, output wire[3:0] c_bbfilter_i_qt, c_bbfilter_q_qt,
 output wire[8:0] c_bbfilter_i_dcf, c_bbfilter_q_dcf,
 output wire c_bb_tap_obs_en, c_bb_tap_inj_en, c_bb_tap_i_bias_en, c_bb_tap_q_bias_en, c_bb_tap_wmon_bias_en, c_wmon_obs_en,
 // ---- converters
 output wire c_adc_i_en, c_adc_q_en, output wire[1:0] c_adc_i_test, c_adc_q_test, output wire c_adc_ilen,
 output wire c_dac_i_en, c_dac_q_en, c_dac_i_hold_zero, c_dac_q_hold_zero, c_refbuf_en, c_refbuf_ovr,
 output wire[1:0] c_adc_acq,
 // ---- RF transmit
 output wire c_txmix_i_en, c_txmix_q_en, c_txmix_sel_dac, c_txmix_sat, c_txsum_en, c_rfdriver_en, c_rfdriver_mute,
 output wire c_rfdriver_bypass, output wire[3:0] c_rfdriver_g, output wire c_rfdriver_se,
 // ---- LO
 output wire c_lo_ext, c_lo_int, c_lo_cmlsel, c_qvco_en, output wire[3:0] c_qvco_band, output wire c_qvco_atb_en,
 output wire c_lo_pre, c_lo_mmd_en, output wire[5:0] c_lo_mmd_n, output wire c_lo_pfdcp_en, output wire[1:0] c_lo_icp,
 output wire c_lo_vreg_en, c_lo_obs_en, c_refvcm_en,
 // ---- clocks
 output wire c_rx_ref_en, output wire[2:0] c_clockmux_ps, output wire[3:0] c_clockmux_ws, output wire[2:0] c_clockmux_ss,
 output wire[3:0] c_clockmux_cs, output wire[1:0] c_clockmux_hs,
 output wire c_prescale_en, output wire[3:0] c_prescale_d, output wire c_prescale_conv_en, output wire[3:0] c_prescale_conv_d,
 output wire c_prescale_hf_en, output wire[3:0] c_prescale_hf_d,
 output wire c_wordclk_en, c_wordclk_d10, c_wordclk_d20, c_pllvreg_byp_tx, c_pllvreg_byp_cdr,
 output wire c_pll_cdr_en, c_pll_cdr_n4, c_pll_cdr_n8, c_pll_cdr_n5, c_pll_cdr_n10, output wire[2:0] c_pll_cdr_kp,
 output wire c_pll_cdr_band, c_cdr_en, c_cdr_pfd_mode, c_cdr_ref_sel, output wire[2:0] c_cdr_g, output wire[5:0] c_cdr_otr,
 output wire c_ring_osc_en, c_vco_replica_en, c_clk_obs_en, c_clk_obs_off, output wire[3:0] c_clk_obs_s,
 output wire[2:0] c_clk_obs_n, output wire[5:0] c_obs_pre4_en, output wire[2:0] c_char_en, output wire rx_en_aux,
 // ---- wired receive
 output wire c_term_en, output wire[1:0] c_term_mode, output wire c_term_hs_en, c_term_hs_term_en,
 output wire[3:0] c_term_hs_trim, output wire c_rxlevel_en, c_rxlevel_half, c_ctle_en, c_ctle_bypass,
 output wire[2:0] c_ctle_peak, c_ctle_lf_zero, output wire c_rxselect_en, c_rxselect_direct, c_wmon_en,
 output wire[1:0] c_wmon_sel, output wire c_detect_en, output wire[1:0] c_detect_thr, c_detect_se,
 output wire c_detect_src_tx, c_detect_inject, c_vthdac_en, output wire[7:0] c_vthdac_a, c_vthdac_b,
 output wire c_slicer_en, output wire[9:0] c_slicer_trim_d0, c_slicer_trim_d1, c_slicer_trim_d2, c_slicer_trim_d3,
 output wire[9:0] c_slicer_trim_e0, c_slicer_trim_e1, c_slicer_trim_e2, c_slicer_trim_e3,
 output wire[1:0] c_slicer_vsel_e0, c_slicer_vsel_e1, c_slicer_vsel_e2, c_slicer_vsel_e3,
 output wire[4:0] c_ptrim_t0, c_ptrim_t1, c_ptrim_t2, c_ptrim_t3, c_ptrim_t4, c_ptrim_t5, c_ptrim_t6, c_ptrim_t7,
 output wire c_wrx_cap_en, c_wrx_cap_rcs, c_wrx_cap_b2, c_wrx_cap_b1, wire_rx_ptrim_en,
 // ---- wired transmit (static part; the sequenced ports come from pt_wtx_ctl)
 output wire c_wiredtx_ext, c_wiredtx_post_pol, output wire[7:0] c_wiredtx_main_code, c_wiredtx_post_code,
 output wire c_hsbias_en, output wire[7:0] c_hsbias_c,
 // ---- USB pad static part
 output wire c_usb_pullup_p, c_usb_pullup_n, c_usb_pulldown_p, c_usb_pulldown_n, c_usb_ls_slow,
 output wire[2:0] c_usb_term_trim, output wire[1:0] c_usb_hs_str
);
`include "pt_regmap_fields.svh"
 localparam [1:0] ACTIVE = 2'd2;
 wire on_wired = island_on[0], on_rf = island_on[1], on_pll = island_on[2], on_conv = island_on[4], on_debug = island_on[5];

 // ---------------- always-on (core rail)
 // INT6: without a reset (POR bypassed by the strap and RESET_N high through power-up) every register powers up
 // random. The always-on enables are held 0 until a real reset has been seen; the island enables likewise
 // (pt_digital_macro), so no switched cell is powered either.
 assign c_aosc_en = f_core_aosc__enable & reset_seen;
 assign c_biasgen_ena = f_core_biasgen__ena & reset_seen;
 // Always-on audit F5: VBG overshoots to the rail for a few us after bgap_ena rises. The bandgap-referenced
 // bias select and the trunk-leg enables stay 0 until the bandgap has been on long enough (bg_ok).
 assign c_biasgen_ref_sel_vbg = f_core_biasgen__ref_sel_vbg & bg_ok;
 assign c_biasgen_ref_sel_coarse = f_core_biasgen__ref_sel_coarse;
 assign c_biasgen_ref_sel_fine = f_core_biasgen__ref_sel_fine;
 assign c_biasgen_idac2_source = f_core_biasgen__idac2_source;
 assign c_biasgen_idac1_source = f_core_biasgen__idac1_source;
 assign c_biasgen_bandgap_sink1 = f_core_biasgen__bandgap_sink1;
 assign c_biasgen_bandgap_sink2 = f_core_biasgen__bandgap_sink2;
 assign c_biasgen_voltgen_source = f_core_biasgen__voltgen_source;
 assign c_biasgen_voltgen_sink1 = f_core_biasgen__voltgen_sink1;
 assign c_biasgen_voltgen_sink2 = f_core_biasgen__voltgen_sink2;
 assign c_bgap_ena = f_core_refchain__bgap_ena & reset_seen;
 assign c_bgap_trim = f_core_refchain__bgap_trim;   // thermometer of the 5-bit count (register file)
 assign c_bias_dist_en_rf = f_core_refchain__dist_en_rf & bg_ok;
 assign c_bias_dist_en_conv = f_core_refchain__dist_en_conv & bg_ok;
 assign c_bias_dist_en_pll = f_core_refchain__dist_en_pll & bg_ok;
 assign c_bias_dist_en_wire = f_core_refchain__dist_en_wire & bg_ok;
 assign c_bias_dist_en_debug = f_core_refchain__dist_en_debug & bg_ok;

 // ---------------- RF receive (rf island)
 // Opcode-4 fast gain: LNA index -> programmable attenuator code lna.agc.code<k> = {gain_lo, att[4:0]};
 // PGA index (0..16 = -6..+42 dB) = the bbfilter dB index (clamped at 16).
 reg[5:0] agc_code;
 always @* case (rx_gain[6:5])
  2'd0: agc_code = f_lna_agc__code0; 2'd1: agc_code = f_lna_agc__code1;
  2'd2: agc_code = f_lna_agc__code2; default: agc_code = f_lna_agc__code3;
 endcase
 wire[5:0] lna_code = rx_gain_active ? agc_code : {f_lna_match__gain_lo, f_lna_match__att};
 assign c_lna_en = (f_lna_state__state == ACTIVE) & on_rf;
 assign c_lna_gain_lo = lna_code[5];
 assign c_lna_att = lna_code[4:0];
 assign c_lna_byp = f_debug_rf_rx_bypass__lna;
 assign c_lna_ct = f_lna_match__ctrim;
 assign c_lna_se = f_lna_match__se;
 assign c_lna_rt = f_lna_match__rterm;
 assign c_lna_lobias = f_lna_bias__lo;
 assign c_rxmix_i_en = (f_rxmix_i_state__state == ACTIVE) & on_rf;
 assign c_rxmix_q_en = (f_rxmix_q_state__state == ACTIVE) & on_rf;
 assign c_rxmix_i_ofs = f_rxmix_offset__i_code;
 assign c_rxmix_q_ofs = f_rxmix_offset__q_code;
 wire[1:0] bb_dir = f_consolidation_bbfilter__direction;  // 0 isolated, 1 rx, 2 tx
 wire[2:0] tap = f_debug_bb_tap__mode; // 0 off 1 observe_rx_mixer 2 observe_rx_filter 3 observe_rx_pga 4 inject_rx
                                       // 5 observe_tx 6 inject_tx_filter 7 inject_tx_mixer
 wire bb_en = (bb_dir != 2'd0) & on_rf;
 assign c_bbfilter_i_en = bb_en;
 assign c_bbfilter_q_en = bb_en;
 assign c_bbfilter_dir_tx = (bb_dir == 2'd2) | (tap == 3'd7);
 assign c_bbfilter_inj = (tap == 3'd4) | (tap == 3'd6) | (tap == 3'd7);
 assign c_bbfilter_obs_sel = (tap == 3'd1) ? 2'b01 : (tap == 3'd3) ? 2'b10 : ((tap == 3'd2) | (tap == 3'd5)) ? 2'b11 : 2'b00;
 assign c_bbfilter_rx_direct = f_consolidation_bbfilter__rx_direct;
 assign c_bbfilter_byp_s1 = f_debug_rf_bb_bypass__pga | (tap == 3'd7);
 assign c_bbfilter_byp_s23 = f_debug_rf_bb_bypass__rxfilter | (tap == 3'd7);
 // PGA LUT (analog/rf_rx netlists.GAIN_TABLE): dB index -> {gainc1, gainc0, k[5:0]}. Never k = 0 with the island on.
 function automatic [7:0] pga_lut(input [4:0] idx);
  case (idx)
   5'd0: pga_lut = {2'b00, 6'd2};   5'd1: pga_lut = {2'b00, 6'd3};   5'd2: pga_lut = {2'b00, 6'd4};
   5'd3: pga_lut = {2'b00, 6'd6};   5'd4: pga_lut = {2'b00, 6'd8};   5'd5: pga_lut = {2'b00, 6'd12};
   5'd6: pga_lut = {2'b00, 6'd17};  5'd7: pga_lut = {2'b00, 6'd24};  5'd8: pga_lut = {2'b00, 6'd35};
   5'd9: pga_lut = {2'b01, 6'd12};  5'd10: pga_lut = {2'b01, 6'd17}; 5'd11: pga_lut = {2'b01, 6'd24};
   5'd12: pga_lut = {2'b01, 6'd35}; 5'd13: pga_lut = {2'b11, 6'd12}; 5'd14: pga_lut = {2'b11, 6'd17};
   5'd15: pga_lut = {2'b11, 6'd25}; default: pga_lut = {2'b11, 6'd36};
  endcase
 endfunction
 wire[4:0] agc_pga = (rx_gain[4:0] > 5'd16) ? 5'd16 : rx_gain[4:0];
 wire[7:0] pga_i = pga_lut(rx_gain_active ? agc_pga : f_bbfilter_i_trim__gain) & {8{on_rf}};
 wire[7:0] pga_q = pga_lut(rx_gain_active ? agc_pga : f_bbfilter_q_trim__gain) & {8{on_rf}};
 assign c_bbfilter_i_gain = pga_i[5:0];  assign c_bbfilter_i_gainc = pga_i[7:6];   // gainc[0] = gainc0, [1] = gainc1
 assign c_bbfilter_q_gain = pga_q[5:0];  assign c_bbfilter_q_gainc = pga_q[7:6];
 assign c_bbfilter_i_cut = f_bbfilter_i_trim__cut;  assign c_bbfilter_q_cut = f_bbfilter_q_trim__cut;
 assign c_bbfilter_i_qt = f_bbfilter_i_trim__qt;    assign c_bbfilter_q_qt = f_bbfilter_q_trim__qt;
 assign c_bbfilter_i_dcf = f_bbfilter_i_trim__dcf;  assign c_bbfilter_q_dcf = f_bbfilter_q_trim__dcf;
 // debug.bb_tap.mode is gated by the rf AND debug islands, debug.wmon_select by wired AND debug.
 assign c_bb_tap_obs_en = (tap == 3'd1) | (tap == 3'd2) | (tap == 3'd3) | (tap == 3'd5);
 assign c_bb_tap_inj_en = c_bbfilter_inj;
 assign c_bb_tap_i_bias_en = (tap != 3'd0) & on_debug;
 assign c_bb_tap_q_bias_en = (tap != 3'd0) & on_debug;
 wire[2:0] wmon = f_debug_wmon_select__select;   // 0 off, 1 rx_p, 2 rx_n, 3 ctle_p, 4 ctle_n
 wire wmon_on = (wmon != 3'd0);
 assign c_bb_tap_wmon_bias_en = wmon_on & on_debug;
 assign c_wmon_obs_en = wmon_on;
 assign c_wmon_en = wmon_on;
 wire[2:0] wmon_m1 = wmon - 3'd1;
 assign c_wmon_sel = wmon_on ? wmon_m1[1:0] : 2'd0;

 // ---------------- converters (conv island)
 assign c_adc_i_en = (f_adc_i_state__state == ACTIVE) & on_conv;
 assign c_adc_q_en = (f_adc_q_state__state == ACTIVE) & on_conv;
 assign c_adc_i_test = f_adc_i_config__input_test;
 assign c_adc_q_test = f_adc_q_config__input_test;
 assign c_adc_ilen = f_adc_config__interleave;
 assign c_adc_acq = f_adc_config__acquisition;
 assign c_dac_i_en = (f_dac_i_state__state == ACTIVE) & on_conv;
 assign c_dac_q_en = (f_dac_q_state__state == ACTIVE) & on_conv;
 assign c_dac_i_hold_zero = f_dac_i_config__hold_zero;
 assign c_dac_q_hold_zero = f_dac_q_config__hold_zero;
 assign c_refbuf_en = (f_refbuf_state__state == ACTIVE) & on_conv;
 assign c_refbuf_ovr = f_debug_bias_override__refbuf;

 // ---------------- RF transmit (rf island)
 assign c_txmix_i_en = (f_txmix_i_state__state == ACTIVE) & on_rf;
 assign c_txmix_q_en = (f_txmix_q_state__state == ACTIVE) & on_rf;
 assign c_txmix_sel_dac = f_consolidation_bbfilter__tx_dac_direct;
 assign c_txmix_sat = f_consolidation_txmix__sat_mode;
 assign c_txsum_en = (f_txsum_state__state == ACTIVE) & on_rf;
 assign c_rfdriver_en = (f_rfdriver_state__state == ACTIVE) & on_rf;
 // One mute gate (MW-21): register (fault-forced to 1 in the register file) OR the transport mute.
 assign c_rfdriver_mute = (f_rfdriver_mute__mute | rf_mute) & on_rf;
 assign c_rfdriver_bypass = f_debug_rf_tx_bypass__rfdriver;
 assign c_rfdriver_g = f_rfdriver_gain__code;
 assign c_rfdriver_se = f_rfdriver_gain__single_ended;

 // ---------------- LO (lo / lod islands = rf enable group since PD2-2; MW-1a: lo_mode 0 off, 1 passive external, 2 on-chip, 3 external through CML)
 wire[1:0] lo_mode = f_rfpll_config__lo_mode;
 wire lo_external = (lo_mode == 2'd1) | (lo_mode == 2'd3);
 assign c_lo_ext = lo_external;
 assign c_lo_int = (lo_mode == 2'd2) | (lo_mode == 2'd3);
 assign c_lo_cmlsel = (lo_mode == 2'd3);
 wire lo_synth_en = (f_rfpll_state__state == ACTIVE) & (lo_mode == 2'd2) & on_rf;
 assign c_qvco_en = lo_synth_en;
 assign c_lo_mmd_en = lo_synth_en;
 assign c_lo_pfdcp_en = lo_synth_en;
 assign c_lo_vreg_en = lo_synth_en;
 assign c_qvco_band = f_rfpll_config__vco_coarse;
 assign c_qvco_atb_en = f_rfpll_config__atb_enable;
 assign c_lo_pre = f_rfpll_config__lo_preset;
 assign c_lo_mmd_n = f_rfpll_config__lo_n;
 assign c_lo_icp = f_rfpll_config__lo_icp;
 wire[4:0] obs_src = f_debug_clk_obs__source;   // gated by the debug island
 assign c_lo_obs_en = (obs_src == 5'd1) & on_rf;
 // REF_IN / AUX_CLK carry the 2.4 GHz LO in both external modes: their clock receivers are forced off.
 assign c_rx_ref_en = (f_refinput_state__state == ACTIVE) & ~lo_external;
 assign rx_en_aux = (rx_en_aux_reg | rx_en_wclk_reg) & ~lo_external;
 // the refpad VCM source is bound on the pll island: its enable reads 0 while that island is off (TOP-25; the REF_IN
 // receiver itself is on the always-on rail, so its VCM needs the pll island on or the source must move: D-REFVCM).
 assign c_refvcm_en = (c_lo_ext | c_rx_ref_en | rx_en_aux) & on_pll;

 // ---------------- clocks (pll island). One-hot, 0 = stopped.
 wire[1:0] ring_ref = f_clockmux_config__ring_ref;                  // 0 stopped, 1 ref, 2 aux, 3 h2d
 assign c_clockmux_ps = {ring_ref == 2'd3, ring_ref == 2'd2, ring_ref == 2'd1};
 wire[2:0] ws = f_debug_clk_select__wire_line, ss = f_debug_clk_select__wire_sample;
 wire[2:0] cs = f_debug_clk_select__conv_sample, hs = f_debug_clk_select__host_clk;
 assign c_clockmux_ws = {ws == 3'd4, ws == 3'd3, ws == 3'd2, ws == 3'd1};   // {wck, aux, ref, pll}
 assign c_clockmux_ss = {ss == 3'd4, ss == 3'd2, ss == 3'd1};               // {wck, ref, int}
 assign c_clockmux_cs = {cs == 3'd5, cs == 3'd3, cs == 3'd2, cs == 3'd1};   // {hf, aux, ref, int}
 assign c_clockmux_hs = {hs == 3'd5, hs == 3'd1};                           // {hf, int}
 function automatic [3:0] presc(input [2:0] c);   // 0 stopped, 1 /2, 2 /4, 3 /8, 4 /16 -> {D16, D8, D4, D2}
  presc = {c == 3'd4, c == 3'd3, c == 3'd2, c == 3'd1};
 endfunction
 assign c_prescale_d = presc(f_clockmux_config__host_prescale);      assign c_prescale_en = |c_prescale_d;
 assign c_prescale_conv_d = presc(f_clockmux_config__conv_prescale); assign c_prescale_conv_en = |c_prescale_conv_d;
 assign c_prescale_hf_d = presc(f_clockmux_config__hf_prescale);     assign c_prescale_hf_en = |c_prescale_hf_d;
 wire slicer_active = (f_slicer_state__state == ACTIVE) & on_wired;
 wire[1:0] rx_rate = f_slicer_capture__rate_mode;                    // 0 quarter, 1 half, 2 full
 assign c_wordclk_en = slicer_active & on_pll;
 assign c_wordclk_d10 = (rx_rate == 2'd1);
 assign c_wordclk_d20 = (rx_rate == 2'd2);
 assign c_pllvreg_byp_tx = f_pllvreg_config__tx_bypass;
 assign c_pllvreg_byp_cdr = f_pllvreg_config__rx_bypass;
 // CDR ring: wired CDR (cdr.state active) or line PLL / host_follow (ring_c.config.line_pll alone, D-HF).
 wire cdr_on = ((f_cdr_state__state == ACTIVE) | f_ring_c_config__line_pll) & on_pll;
 wire[2:0] cmod = f_ring_c_config__modulus;                          // 0 /16, 1 /8, 2 /4, 3 /10, 4 /5
 assign c_pll_cdr_en = cdr_on & vreg_rx_ok;
 assign c_pll_cdr_n8 = (cmod == 3'd1);
 assign c_pll_cdr_n4 = (cmod == 3'd2);
 assign c_pll_cdr_n10 = (cmod == 3'd3);
 assign c_pll_cdr_n5 = (cmod == 3'd4);
 assign c_pll_cdr_kp = f_ring_c_config__kp;
 assign c_pll_cdr_band = f_ring_c_config__band;
 assign c_cdr_en = cdr_on;
 assign c_cdr_pfd_mode = f_ring_c_config__line_pll;
 assign c_cdr_ref_sel = f_cdr_ac3__fll_ref_wck;
 assign c_cdr_g = f_cdr_ac3__loop_bw;
 assign c_cdr_otr = f_cdr_ac3__otr;
 assign c_ring_osc_en = f_debug_replica__ringosc_enable;
 assign c_vco_replica_en = f_debug_replica__vco_enable;
 // CLK_OBS (debug island): 4 select pins; codes 15..17 all select input 15 (never alias onto 0/1).
 wire obs_on = (obs_src != 5'd0);
 assign c_clk_obs_en = obs_on;
 assign c_clk_obs_off = ~obs_on;                    // pull-down on the tri-state node while the cell is not driving
 assign c_clk_obs_s = (obs_src >= 5'd15) ? 4'd15 : obs_src[3:0];
 assign c_clk_obs_n = f_debug_clk_obs__divider_log2;
 // /4 prescalers of the fast sources: {cdr_recovered 14, pll_vco 8, aux_clk 6 (= wclk_in 7 since CP4-3: same pad
 // pair), ref_in 5, wire_sample 3, wire_line 2}; the four on pll-island clocks stay off while the pll island is
 // off (their input is NAND(CK, EN)).
 assign c_obs_pre4_en = {(obs_src == 5'd14) & on_pll, (obs_src == 5'd8) & on_pll, (obs_src == 5'd6) | (obs_src == 5'd7),
                         obs_src == 5'd5, (obs_src == 5'd3) & on_pll, (obs_src == 5'd2) & on_pll};
 assign c_char_en = {f_debug_replica__cmldiv_enable, f_debug_replica__ro50_enable, f_debug_replica__ro33_enable};

 // ---------------- wired receive (wired island)
 wire[1:0] p_load = f_termination_config__p_load;   // 0 off, 1 45_to_ground, 2 50_to_vcm
 wire d100 = f_termination_config__differential_100_enable;
 assign c_term_en = (p_load != 2'd0) | d100;
 assign c_term_mode = d100 ? 2'b10 : (p_load == 2'd2) ? 2'b01 : (p_load == 2'd1) ? 2'b11 : 2'b00;
 assign c_term_hs_en = f_termination_config__hs_enable;
 assign c_term_hs_term_en = f_termination_config__hs_term_enable;
 assign c_term_hs_trim = f_termination_config__hs_trim;
 assign c_rxlevel_en = (f_rxlevel_config__path != 2'd0);
 assign c_rxlevel_half = (f_rxlevel_config__path == 2'd2);
 assign c_ctle_en = (f_ctle_state__state == ACTIVE) & on_wired;
 assign c_ctle_bypass = f_debug_wire_bypass__ctle;
 assign c_ctle_peak = f_ctle_config__peak;
 assign c_ctle_lf_zero = f_ctle_config__lf_zero;
 assign c_rxselect_en = (f_rxselect_state__state == ACTIVE) & on_wired;
 assign c_rxselect_direct = f_rxselect_select__branch;
 assign c_detect_en = (f_detect_state__state == ACTIVE) & on_wired;
 assign c_detect_thr = f_detect_config__high_threshold_code;
 assign c_detect_se = f_detect_config__low_threshold_code;
 assign c_detect_src_tx = f_consolidation_detect__src_tx;
 assign c_detect_inject = f_detect_config__test_current_enable;
 assign c_vthdac_en = f_slicer_threshold__vth_enable;
 assign c_vthdac_a = (vth_fast[0] & on_wired) ? vth_fast_a : f_slicer_threshold__vth_a;
 assign c_vthdac_b = (vth_fast[1] & on_wired) ? vth_fast_b : f_slicer_threshold__vth_b;
 assign c_slicer_en = slicer_active;
 assign c_slicer_trim_d0 = f_slicer_offset__trim_d0; assign c_slicer_trim_d1 = f_slicer_offset__trim_d1;
 assign c_slicer_trim_d2 = f_slicer_offset__trim_d2; assign c_slicer_trim_d3 = f_slicer_offset__trim_d3;
 assign c_slicer_trim_e0 = f_slicer_offset__trim_e0; assign c_slicer_trim_e1 = f_slicer_offset__trim_e1;
 assign c_slicer_trim_e2 = f_slicer_offset__trim_e2; assign c_slicer_trim_e3 = f_slicer_offset__trim_e3;
 assign c_slicer_vsel_e0 = f_slicer_threshold__vsel_e0; assign c_slicer_vsel_e1 = f_slicer_threshold__vsel_e1;
 assign c_slicer_vsel_e2 = f_slicer_threshold__vsel_e2; assign c_slicer_vsel_e3 = f_slicer_threshold__vsel_e3;
 assign c_ptrim_t0 = f_cdr_phase_trim__p0; assign c_ptrim_t1 = f_cdr_phase_trim__p1;
 assign c_ptrim_t2 = f_cdr_phase_trim__p2; assign c_ptrim_t3 = f_cdr_phase_trim__p3;
 assign c_ptrim_t4 = f_cdr_phase_trim__p4; assign c_ptrim_t5 = f_cdr_phase_trim__p5;
 assign c_ptrim_t6 = f_cdr_phase_trim__p6; assign c_ptrim_t7 = f_cdr_phase_trim__p7;
 assign c_wrx_cap_en = slicer_active;
 assign c_wrx_cap_rcs = f_slicer_capture__rcsel;
 assign c_wrx_cap_b2 = (rx_rate == 2'd1);
 assign c_wrx_cap_b1 = (rx_rate == 2'd2);
 // SLI7-R / W6-SAFE: ring phases reach the slicer only with the slicer active; also 0 while the pll island is off.
 assign wire_rx_ptrim_en = slicer_active & on_pll;

 // ---------------- wired transmit / USB static pins (wired island)
 assign c_wiredtx_ext = f_debug_wtx_ext__enable;
 assign c_wiredtx_post_pol = f_wiredtx_config__post_polarity;
 assign c_wiredtx_main_code = f_wiredtx_config__current_code;
 assign c_wiredtx_post_code = f_wiredtx_config__postcursor_code;
 assign c_hsbias_en = f_usbhs_bias__enable;
 assign c_hsbias_c = f_usbhs_bias__code;
 assign c_usb_pullup_p = f_usbfs_config__pullup_p;     assign c_usb_pullup_n = f_usbfs_config__pullup_n;
 assign c_usb_pulldown_p = f_usbfs_config__pulldown_p; assign c_usb_pulldown_n = f_usbfs_config__pulldown_n;
 assign c_usb_ls_slow = f_usbfs_config__ls_slow;
 assign c_usb_hs_str = f_usbhs_config__drive_strength;
 assign c_usb_term_trim = f_usbhs_config__term_trim;    // gate_and term_enable in the register file
endmodule

// Bandgap-before-consumers interlock (always-on audit F5; coordinator: an interlock in RTL, not a documented
// order). ok rises 128 SCLK cycles after bgap_ena is seen high and falls with it. SCLK is the only clock that
// is guaranteed in SPI-only bring-up; it runs only inside transactions, so the consumers switch on during the
// fourth SPI transaction after the commit that enabled the bandgap (>= 12.8 us at SCLK <= 10 MHz, 25.6 us at
// 5 MHz, 128 us at 1 MHz). Clocked on the SCLK fall like the register file.
module pt_bgap_interlock(input wire rst_n, sclk, bgap_ena, output reg ok);
 reg[6:0] cnt;
 always @(negedge sclk or negedge rst_n)
  if (!rst_n) begin cnt <= 7'd0; ok <= 1'b0; end
  else if (!bgap_ena) begin cnt <= 7'd0; ok <= 1'b0; end
  else if (cnt == 7'd127) ok <= 1'b1;
  else cnt <= cnt + 7'd1;
endmodule

// Reset-seen key (INT6-*, coordinator 2026-11-13). With the POR bypassed by the strap and RESET_N high through
// power-up there is no reset at all and every flop powers up at random, including island enables. This key is
// eight flops that are only ever written by the asynchronous reset (four reset to 0, four set to 1; D = Q):
// seen = 1 only when they hold the pattern 8'hA5, which a real reset always loads and a random power-up
// matches with probability 1/256. It gates the island enables and the always-on analog enables only: SPI,
// the register file and the observation pads do not depend on it, and any RESET_N low pulse sets it (the
// RESET_N pad has a pull-down, so an undriven pad resets). An upset of a key bit switches the analog off until
// the next reset; it cannot hold the die in reset.
module pt_reset_seen(input wire rst_n, clk, output wire seen);
 wire[7:0] key;
 genvar i;
 generate for (i = 0; i < 8; i = i + 1) begin : k
`ifdef SYNTHESIS
  // instantiated cells: a D = Q flop with a constant reset value would be optimised to a constant
  if ((8'hA5 >> i) & 1) begin : s (* keep=1,dont_touch=1 *) gf180mcu_fd_sc_mcu7t5v0__dffsnq_1 key_ff(.D(key[i]), .SETN(rst_n), .CLK(clk), .Q(key[i])); end
  else begin : r (* keep=1,dont_touch=1 *) gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 key_ff(.D(key[i]), .RN(rst_n), .CLK(clk), .Q(key[i])); end
`else
  reg q;   // no initial value: simulation powers up X like silicon powers up unknown
  always @(posedge clk or negedge rst_n) if (!rst_n) q <= (8'hA5 >> i) & 1; else q <= q;
  assign key[i] = q;
`endif
 end endgenerate
 assign seen = (key == 8'hA5);
endmodule
`default_nettype wire
