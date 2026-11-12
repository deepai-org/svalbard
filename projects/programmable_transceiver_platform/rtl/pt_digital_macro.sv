// Hardened core digital macro (freeze stage 1: control and digital).
// Contents: pt_digital (pt_mgmt = pt_spi + generated pt_regfile, pt_core transport and FIFOs,
// pt_memory capture/playback, pt_pattern generator/checker with ICG word clocks, calibrator),
// pt_clocktree_slow (P2-10 word divider / launch qualification / detector divider), the two
// frequency counters (pt_freq_count, inside pt_digital) and the
// clocked half of hostio (pt_host_link: DDR/SDR capture, launch and forwarded clock).
// Pad cells are NOT in this macro: they are provider gf180mcu_fd_io cells in the ring
// (integration/pt_chip.sv pt_host_physical). This macro drives their A/OE/SL/PDRV pins and takes
// their Y outputs. Hardening flow: verification/run_digital_hardening.sh.
// Reset: rst_n = RESET_N (pad Y) AND por_n (on-die POR), asynchronous assert. AC-1 clocking
// (transport rework 2026-11-10): host_word_clk is the host DDR clock from the clocktree, line/16
// (156.25 MHz at 2.5 Gb/s; one ten-bit word per pin per clock EDGE) or the fixed 156.25 MHz host
// option (IX-2). No macro logic runs at the 312.5 MHz word rate. pt_host_rate_clock selects /1 /2 /4
// of it (hddr: pad-edge DDR launch and gearbox), pt_host_link divides that by 2 for the 78.125 MHz
// core clock that runs the whole 40-bit transport; H2D_CLK clocks the H2D capture and quad-FIFO
// write side.
`include "pt_regmap_defs.svh"
`default_nettype none
module pt_digital_macro(
 input  wire reset_n_pad, por_n,
 // SPI (pad Y / pad A,OE)
 input  wire spi_sclk, spi_cs_n, spi_mosi, output wire spi_miso, spi_miso_oe,
 // host GPIO link
 input  wire host_word_clk,                     // clocktree host DDR clock (line/16 or fixed 156.25 MHz)
 input  wire h2d_clk, input wire[9:0] h2d_pin,
 output wire[9:0] d2h_pin, output wire d2h_clk_pin, output wire d2h_oe,
 output wire[1:0] d2h_pdrv, output wire d2h_sl,  // hostio.controls drive/slew to the pad cells
 // reference / analog clocks
 input  wire ref_clk, wire_rx_clk, wire_tx_clk, rf_rx_clk, rf_tx_clk,
 // analog data boundary
 // Wired boundary (AC-1 S3): 40-bit quads per edge of wire_rx_clk (pt_wrx_cap WCLK40, DX[39:0]) and
 // wire_tx_clk (pt_wiredtx WORD_CLK40, D0..D39); word 0 (earliest on the line) in [9:0].
 input  wire[39:0] wire_rx_data, input wire wire_rx_valid, output wire[39:0] wire_tx_data,
 output wire wire_tx_valid, wire_idle, input wire wire_tx_request,
 input  wire[23:0] rf_rx_sample, input wire rf_rx_valid, output wire[23:0] rf_tx_sample,
 output wire rf_tx_valid, rf_mute, input wire rf_tx_request,
 output wire rf_tx_clk_out, // DT-6: forwarded DAC capture clock (source-synchronous with rf_tx_sample/valid/mute)
 output wire enable, mode8, output wire[15:0] rf_trim, wire_trim, clock_trim,
 input  wire calibration_above_target, output wire[11:0] calibration_trial,
 // generated control boundary
 input  wire fault, input wire[`PT_ISLAND_W-1:0] island_pgood,
 input  wire[5:0] fc_src,                       // frequency-counter sources (P3-7, see pt_digital)
 output wire wire_rx_ptrim_en,                  // SLI7-R / W6-SAFE interlock: wired_rx ptrim_en (ring phases to the slicer)
 output wire cdr_freq_locked,                   // CDR frequency-to-phase handover (freq_count_b lock)
 input  wire[11:0] analog_status, input wire[12:0] wire_analog_status,
 output wire[`PT_ANALOG_CFG_W-1:0] analog_cfg, output wire[`PT_DEBUG_CFG_W-1:0] debug_cfg,
 output wire[`PT_ISLAND_W-1:0] island_en, island_on, // island_on drives the iso_clamps (0 = isolated)
 // PD8 (pads/assembly, 2026-11-10): pt_wtx_fallback_control.WIRED_ON. It used to be bound onto the island_on[0]
 // net together with this macro's output (output-on-output). It is now an input, ORed into island_on[0], so
 // the wired island's clamps follow either controller; the register file's own view stays island_on_reg.
 input  wire wired_on_ext,
 // IX-2 8b/10b wired line-code offload select (stopped-only level). No register-map field yet
 // (requested: wire.config.linecode): strapped at chip level like ct_cfg_det_*.
 input  wire wire_linecode,
 output wire[`PT_ATB_W-1:0] atb0_sw, atb1_sw,
 output wire[`PT_ATB0_GRP_W-1:0] atb0_grp, output wire[`PT_ATB1_GRP_W-1:0] atb1_grp, output wire atb0_en, atb1_en, // ATB group/pad selects
 output wire rx_en_aux, rx_en_wclk, rx_en_wtx_ext, clk_obs_oe, wclk_obs_oe,
 output wire dbg_obs0, dbg_obs0_oe, dbg_obs1, dbg_obs1_oe, wdbg_obs, wdbg_obs_oe, commit_toggle,
 // clocktree slow functions (pt_clocktree_slow)
 input  wire ct_wclk, ct_ref_clk, ct_det_clk_in, ct_pll_lock, ct_marker,
 input  wire ct_cfg_det_en, input wire[2:0] ct_cfg_det_div, // no register-map field yet
 output wire ct_word_clk, ct_word_load, ct_ser_run, ct_bit_phase, ct_qualified,
 output wire ct_armed, ct_marker_seen, ct_launched, ct_arm_fault,
 output wire[2:0] ct_det_div, output wire ct_det_clk,
 // Effective block enables and island-off levels for full-chip assembly
 // (scratch/chip-assembly-dev/binding.json glue nets). Decoded from quasi-static register bits.
//   en_eff[0] EN_EFF_adc_i: adc_i.state.state == active && island_on[4]
//   en_eff[1] EN_EFF_adc_q: adc_q.state.state == active && island_on[4]
//   en_eff[2] EN_EFF_wiredtx: wiredtx.state.state == active && island_on[0]
//   en_eff[3] EN_EFF_dac_i: dac_i.state.state == active && island_on[4]
//   en_eff[4] EN_EFF_dac_q: dac_q.state.state == active && island_on[4]
//   en_eff[5] EN_EFF_refbuf: refbuf.state.state == active && island_on[4]
//   en_eff[6] EN_EFF_detect: detect.state.state == active && island_on[0]
//   en_eff[7] EN_EFF_rfdriver: rfdriver.state.state == active && island_on[1]
//   en_eff[8] EN_EFF_rxmix_i: rxmix_i.state.state == active && island_on[1]
//   en_eff[9] EN_EFF_rxmix_q: rxmix_q.state.state == active && island_on[1]
//   en_eff[10] EN_EFF_pll_cdr: cdr.state.state == active && island_on[2] && vreg_rx_ok (pt_vreg_seq)
//   en_eff[11] EN_EFF_pll_host: rfpll.state.state == active && island_on[2] && vreg_tx_ok (pt_vreg_seq)
//   en_eff[12] EN_EFF_cdr: cdr.state.state == active && island_on[2]
//   en_eff[13] EN_EFF_slicer: slicer.state.state == active && island_on[0]
//   en_eff[14] EN_EFF_ctle: ctle.state.state == active && island_on[0]
//   en_eff[15] EN_EFF_txmix_i: txmix_i.state.state == active && island_on[1]
//   en_eff[16] EN_EFF_txmix_q: txmix_q.state.state == active && island_on[1]
//   en_eff[17] EN_EFF_lna: lna.state.state == active && island_on[1]
//   en_eff[18] EN_EFF_rxselect: rxselect.state.state == active && island_on[0]
//   en_eff[19] EN_EFF_txsum: txsum.state.state == active && island_on[1]
 //   island_off[i] = !island_on[i] (ISLAND_OFF_wired = [0], _rf = [1], _debug = [5]).
 output wire[19:0] en_eff, output wire[`PT_ISLAND_W-1:0] island_off
);
 wire rst_n = reset_n_pad & por_n;
 wire[`PT_ISLAND_W-1:0] island_on_reg; // register-file island state (switch on AND (pgood OR override))
 // RXR-D2 fast gain (opcode4): while the transport has applied an in-band gain (rx_gain_active,
 // cleared by ENABLE=0) the LNA gain_lo and the shared bbfilter PGA gain come from it instead of the
 // SPI fields. Mapping of the opcode4 indices onto today's hardware (analog/rf_rx/README.md):
 //   LNA index 0 (-6 dB) -> pre-LNA attenuator lna.match.att = 2 with gain_lo off (lna.gain.gain_db 1):
 //   RC-16g made gain_lo the attenuator MSB (~27-34 dB), so it can no longer serve the -6 dB step. Code 2
 //   is the level nearest 6 dB at every corner (analog/rf_rx/generated/lna-evidence.json level table:
 //   ss32 5.34, tt27 7.05, ff22 8.52 dB). Indices 1..3 (0/10/20 dB) -> att 0, gain_db 1 (0 dB; 10/20 dB
 //   not built).
 //   PGA index k (-6 + 3k dB) -> bbfilter gain code c with 20 log10(1 + c) nearest, clamped 0..15
 //   (0..24 dB). RXR-D1 (pre-filter steps) will extend this table, not the command.
 wire[6:0] rx_gain; wire rx_gain_active;
 function automatic [3:0] pga_code(input [4:0] k);
  case (k)
   5'd0, 5'd1, 5'd2, 5'd3: pga_code = 4'd0;   // -6, -3, 0, 3 dB -> 0 dB
   5'd4: pga_code = 4'd1;  5'd5: pga_code = 4'd2;  5'd6: pga_code = 4'd3;  5'd7: pga_code = 4'd5;
   5'd8: pga_code = 4'd7;  5'd9: pga_code = 4'd10; default: pga_code = 4'd15;
  endcase
 endfunction
 wire[`PT_ANALOG_CFG_W-1:0] analog_cfg_reg; wire[`PT_DEBUG_CFG_W-1:0] debug_cfg_reg;
 assign analog_cfg = rx_gain_active ?
   {analog_cfg_reg[`PT_ANALOG_CFG_W-1:`PT_A_LNA_MATCH__ATT_LSB+`PT_A_LNA_MATCH__ATT_W],
    (rx_gain[6:5] == 2'd0) ? 5'd2 : 5'd0,
    analog_cfg_reg[`PT_A_LNA_MATCH__ATT_LSB-1:`PT_A_LNA_GAIN__GAIN_DB_LSB+2], 2'd1,
    analog_cfg_reg[`PT_A_LNA_GAIN__GAIN_DB_LSB-1:0]} : analog_cfg_reg;
 assign debug_cfg = rx_gain_active ?
   {debug_cfg_reg[`PT_DEBUG_CFG_W-1:`PT_D_CONSOLIDATION_BBFILTER__GAIN_LSB+4], pga_code(rx_gain[4:0]),
    debug_cfg_reg[`PT_D_CONSOLIDATION_BBFILTER__GAIN_LSB-1:0]} : debug_cfg_reg;
 // SLI7-R (W6-SAFE): the slicer's ring-phase clocks (ptrim_en) are gated in hardware whenever the slicer
 // is not active: slicer.state off (0) and warm (1) both give ptrim_en = 0, so ptrim_en = 0 whenever
 // slicer_en = 0 for any assembly decode of slicer_en from the state (off -> 0 in all of them).
 assign wire_rx_ptrim_en = analog_cfg[`PT_A_SLICER_STATE__STATE_LSB +: 2] == 2'd2;
 wire[39:0] h2d_quad, d2h_quad;
 // Reduced-rate fallback (debug.host_link.rate, stopped-only): the host link and the whole
 // transport core run from link_clk = host_word_clk / {1,2,4} (core clock = link_clk / 2). A rate
 // change holds both in reset (host_rst_n) while the clock select switches (pt_host_rate_clock).
 // The transport core's reset is released synchronously to its own clock (pt_host_link core_rst_n).
 wire ddr_clk, sdr_word_clk, core_clk, core_rst_n, rate_hold_n;
 pt_host_rate_clock host_rate(.clk(host_word_clk), .rst_n(rst_n),
  .rate(debug_cfg[`PT_D_DEBUG_HOST_LINK__RATE_LSB+:`PT_D_DEBUG_HOST_LINK__RATE_W]),
  .out_clk(ddr_clk), .word_clk(sdr_word_clk), .hold_n(rate_hold_n));
 wire host_rst_n = rst_n & rate_hold_n;
 wire[15:0] status;
 pt_digital digital(.rst_n(rst_n), .ref_clk(ref_clk), .host_sclk(spi_sclk), .host_cs_n(spi_cs_n), .host_mosi(spi_mosi),
  .host_miso(spi_miso), .host_miso_oe(spi_miso_oe), .host_tx_clk(core_clk), .host_rx_clk(core_clk), .core_rst_n(core_rst_n),
  .wire_rx_clk(wire_rx_clk), .wire_tx_clk(wire_tx_clk), .rf_rx_clk(rf_rx_clk), .rf_tx_clk(rf_tx_clk),
  .h2d_quad(h2d_quad), .d2h_quad(d2h_quad), .wire_rx_data(wire_rx_data), .wire_rx_valid(wire_rx_valid),
  .wire_tx_data(wire_tx_data), .wire_tx_valid(wire_tx_valid), .wire_idle(wire_idle), .wire_tx_request(wire_tx_request),
  .rf_rx_sample(rf_rx_sample), .rf_rx_valid(rf_rx_valid), .rf_tx_sample(rf_tx_sample), .rf_tx_valid(rf_tx_valid),
  .rf_mute(rf_mute), .rf_tx_request(rf_tx_request), .rf_tx_clk_out(rf_tx_clk_out), .enable(enable), .mode8(mode8), .rf_trim(rf_trim),
  .wire_trim(wire_trim), .clock_trim(clock_trim), .calibration_above_target(calibration_above_target),
  .calibration_trial(calibration_trial), .status(status), .por_n(por_n), .fault(fault), .island_pgood(island_pgood), .fc_src(fc_src), .cdr_freq_locked(cdr_freq_locked),
  .analog_status(analog_status), .wire_analog_status(wire_analog_status), .analog_cfg(analog_cfg_reg), .debug_cfg(debug_cfg_reg),
  .island_en(island_en), .island_on(island_on_reg), .atb0_sw(atb0_sw), .atb1_sw(atb1_sw), .atb0_grp(atb0_grp), .atb1_grp(atb1_grp), .atb0_en(atb0_en), .atb1_en(atb1_en), .rx_en_aux(rx_en_aux), .rx_en_wclk(rx_en_wclk),
  .rx_en_wtx_ext(rx_en_wtx_ext), .clk_obs_oe(clk_obs_oe), .wclk_obs_oe(wclk_obs_oe), .dbg_obs0(dbg_obs0),
  .dbg_obs0_oe(dbg_obs0_oe), .dbg_obs1(dbg_obs1), .dbg_obs1_oe(dbg_obs1_oe), .wdbg_obs(wdbg_obs),
  .wdbg_obs_oe(wdbg_obs_oe), .commit_toggle(commit_toggle),
  .linecode(wire_linecode), .rx_gain(rx_gain), .rx_gain_active(rx_gain_active));
 pt_host_link host(.rst_n(host_rst_n),
  .mode(debug_cfg[`PT_D_DEBUG_HOST_LINK__MODE_LSB+:`PT_D_DEBUG_HOST_LINK__MODE_W]),
  .d2h_enable(analog_cfg[`PT_A_HOSTIO_CONTROLS__D2H_ENABLE_LSB]),
  .h2d_clk(h2d_clk), .h2d_pin(h2d_pin), .link_clk(ddr_clk), .word_clk(sdr_word_clk), .core_clk(core_clk), .core_rst_n(core_rst_n), .h2d_quad(h2d_quad), .d2h_quad(d2h_quad),
  .d2h_pin(d2h_pin), .d2h_clk_pin(d2h_clk_pin), .d2h_stagger(analog_cfg[`PT_A_HOSTIO_CONTROLS__D2H_STAGGER_LSB]),
  .d2h_oe(d2h_oe), .h2d_overflow(), .h2d_underflow());
 assign en_eff[0] = (analog_cfg[`PT_A_ADC_I_STATE__STATE_LSB+:2] == 2'd2) && island_on_reg[4]; // adc_i
 assign en_eff[1] = (analog_cfg[`PT_A_ADC_Q_STATE__STATE_LSB+:2] == 2'd2) && island_on_reg[4]; // adc_q
 assign en_eff[2] = (analog_cfg[`PT_A_WIREDTX_STATE__STATE_LSB+:2] == 2'd2) && island_on_reg[0]; // wiredtx
 assign en_eff[3] = (analog_cfg[`PT_A_DAC_I_STATE__STATE_LSB+:2] == 2'd2) && island_on_reg[4]; // dac_i
 assign en_eff[4] = (analog_cfg[`PT_A_DAC_Q_STATE__STATE_LSB+:2] == 2'd2) && island_on_reg[4]; // dac_q
 assign en_eff[5] = (analog_cfg[`PT_A_REFBUF_STATE__STATE_LSB+:2] == 2'd2) && island_on_reg[4]; // refbuf
 assign en_eff[6] = (analog_cfg[`PT_A_DETECT_STATE__STATE_LSB+:2] == 2'd2) && island_on_reg[0]; // detect
 assign en_eff[7] = (analog_cfg[`PT_A_RFDRIVER_STATE__STATE_LSB+:2] == 2'd2) && island_on_reg[1]; // rfdriver
 assign en_eff[8] = (analog_cfg[`PT_A_RXMIX_I_STATE__STATE_LSB+:2] == 2'd2) && island_on_reg[1]; // rxmix_i
 assign en_eff[9] = (analog_cfg[`PT_A_RXMIX_Q_STATE__STATE_LSB+:2] == 2'd2) && island_on_reg[1]; // rxmix_q
 // PD9 regulated ring supplies: a ring whose pt_pll_vreg is out of bypass is held off for >= 50 us after
 // the pll island powers up or the regulator leaves bypass (rtl/pt_vreg_seq.sv).
 wire vreg_tx_ok, vreg_rx_ok;
 pt_vreg_seq vreg_seq(.rst_n(rst_n), .ref_clk(ref_clk), .pll_on(island_on_reg[2]),
  .tx_bypass(analog_cfg[`PT_A_PLLVREG_CONFIG__TX_BYPASS_LSB]), .rx_bypass(analog_cfg[`PT_A_PLLVREG_CONFIG__RX_BYPASS_LSB]),
  .tx_ok(vreg_tx_ok), .rx_ok(vreg_rx_ok));
 assign en_eff[10] = (analog_cfg[`PT_A_CDR_STATE__STATE_LSB+:2] == 2'd2) && island_on_reg[2] && vreg_rx_ok; // pll_cdr
 assign en_eff[11] = (analog_cfg[`PT_A_RFPLL_STATE__STATE_LSB+:2] == 2'd2) && island_on_reg[2] && vreg_tx_ok; // pll_host
 assign en_eff[12] = (analog_cfg[`PT_A_CDR_STATE__STATE_LSB+:2] == 2'd2) && island_on_reg[2]; // cdr
 assign en_eff[13] = (analog_cfg[`PT_A_SLICER_STATE__STATE_LSB+:2] == 2'd2) && island_on_reg[0]; // slicer
 assign en_eff[14] = (analog_cfg[`PT_A_CTLE_STATE__STATE_LSB+:2] == 2'd2) && island_on_reg[0]; // ctle
 assign en_eff[15] = (analog_cfg[`PT_A_TXMIX_I_STATE__STATE_LSB+:2] == 2'd2) && island_on_reg[1]; // txmix_i
 assign en_eff[16] = (analog_cfg[`PT_A_TXMIX_Q_STATE__STATE_LSB+:2] == 2'd2) && island_on_reg[1]; // txmix_q
 assign en_eff[17] = (analog_cfg[`PT_A_LNA_STATE__STATE_LSB+:2] == 2'd2) && island_on_reg[1]; // lna
 assign en_eff[18] = (analog_cfg[`PT_A_RXSELECT_STATE__STATE_LSB+:2] == 2'd2) && island_on_reg[0]; // rxselect
 assign en_eff[19] = (analog_cfg[`PT_A_TXSUM_STATE__STATE_LSB+:2] == 2'd2) && island_on_reg[1]; // txsum
 assign island_off = ~island_on;
 assign island_on = island_on_reg | {{(`PT_ISLAND_W-1){1'b0}}, wired_on_ext};
 assign d2h_pdrv = analog_cfg[`PT_A_HOSTIO_CONTROLS__DRIVE_LSB+:`PT_A_HOSTIO_CONTROLS__DRIVE_W];
 assign d2h_sl = analog_cfg[`PT_A_HOSTIO_CONTROLS__SLEW_LSB];
 // Word-divider modulus from consolidation.wiredtx_stage.bits_per_cycle: 1 bit/cycle -> 10 ring cycles per
 // 10-bit word; 2 -> 5; 4 -> 5 ring cycles per 20-bit double word (the divider then marks double words).
 pt_clocktree_slow #(.QUAL_CYCLES(64)) clocktree(.rst_n(rst_n), .wclk(ct_wclk), .cfg_half_rate(debug_cfg[`PT_D_CONSOLIDATION_WIREDTX_STAGE__BITS_PER_CYCLE_LSB+:2] != 2'd0),
  .cfg_bit_delay(analog_cfg[`PT_A_CLOCKTREE_CONFIG__LAUNCH_BIT_DELAY_LSB+:4]),
  .cfg_word_delay(analog_cfg[`PT_A_CLOCKTREE_CONFIG__LAUNCH_WORD_DELAY_LSB+:2]),
  .pll_lock(ct_pll_lock), .word_clk(ct_word_clk), .word_load(ct_word_load), .ser_run(ct_ser_run),
  .bit_phase(ct_bit_phase), .qualified(ct_qualified), .ref_clk(ct_ref_clk), .marker(ct_marker),
  .cfg_sync_arm(analog_cfg[`PT_A_CLOCKTREE_CONFIG__SYNC_ARM_LSB]),
  .cfg_ref_count(analog_cfg[`PT_A_CLOCKTREE_CONFIG__LAUNCH_REFERENCE_COUNT_LSB+:16]),
  .armed(ct_armed), .marker_seen(ct_marker_seen), .launched(ct_launched), .arm_fault(ct_arm_fault),
  .det_clk_in(ct_det_clk_in), .cfg_det_en(ct_cfg_det_en), .cfg_det_div(ct_cfg_det_div),
  .cfg_rate_khz(analog_cfg[`PT_A_CDR_CONFIG__NOMINAL_RATE_KHZ_LSB+:22]), .det_div(ct_det_div), .det_clk(ct_det_clk));
endmodule
`default_nettype wire
