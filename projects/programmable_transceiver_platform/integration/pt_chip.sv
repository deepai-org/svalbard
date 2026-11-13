// WIRE_RX is bidirectional for planned USB D+/D-; USB control/data macros remain unimplemented.
// Integration skeleton: 51 functional logical terminals plus the 19 debug sites of
// spec/tapeout-readiness.json:debug_sites; the physical ring retains 74 sites.
// Black-box macros are obligations, not fabricated IP.
// Control: pt_digital_macro (hardened) contains pt_digital, which instantiates pt_mgmt (pt_spi + generated rtl/pt_regfile.sv). Every analog,
// island-switch, debug and fallback control reaches the macros only through analog_cfg/debug_cfg
// (field positions in rtl/pt_regmap_defs.svh), island_en, the ATB one-hot vectors and the
// derived receiver/observation enables. Reset is RESET_N AND (the on-die POR OR the POR_BYPASS strap).
`include "pt_regmap_defs.svh"
module pt_chip(
 inout wire RESET_N,SPI_SCLK,SPI_CS_N,SPI_MOSI,output wire SPI_MISO,
 input wire REF_IN,REF_IN_N,
 inout wire[9:0]H2D,inout wire H2D_CLK,output wire[9:0]D2H,output wire D2H_CLK,
 inout wire WIRE_RX_P,WIRE_RX_N,output wire WIRE_TX_P,WIRE_TX_N,
 input wire RF_RX_P,RF_RX_N,output wire RF_TX_P,RF_TX_N,
 // Debug sites (tapeout-plan.md tier 3).
 inout wire BB_I_P,BB_I_N,BB_Q_P,BB_Q_N,input wire AUX_CLK_P,AUX_CLK_N,inout wire ATB0,ATB1,
 output wire CLK_OBS,DBG_OBS0,DBG_OBS1,input wire WCLK_IN_P,WCLK_IN_N,output wire WCLK_OBS,WDBG_OBS,
 input wire WTX_EXT_P,WTX_EXT_N,output wire WMON,inout wire ESD_TEST,
 inout wire VDD_CORE,VSS_CORE,VDD_HOST_A,VSS_HOST_A,VDD_HOST_B,VSS_HOST_B,
 VDD_WIRE_A,VSS_WIRE_A,VDD_WIRE_B,VSS_WIRE_B,VDD_RF,VSS_RF,VDD_PLL,VSS_PLL);
 wire pad_rst_n,por_n,rst_n,ref_clk,sclk,cs_n,mosi,miso,miso_oe;
 wire ht,h2d_clk,wr,wt,rr,rt,enable,mode8,wv,wvalid,wrequest,rv,rvalid,rrequest,idle,mute,above;
 wire[9:0]h2d_pin,d2h_pin;wire[39:0]wire_rx,wire_tx; // wired boundary: 40-bit quads (AC-1 S3)
 wire[23:0]rf_rx,rf_tx;wire d2h_clk_pin,d2h_oe,d2h_sl;wire[1:0]d2h_pdrv;
 wire[15:0]rf_trim,wire_trim,clock_trim;wire[11:0]trial;
 // Generated control boundary.
 wire fault,commit_toggle;wire[`PT_ISLAND_W-1:0]island_pgood,island_en,island_on;
 wire[11:0]analog_status;wire[12:0]wire_analog_status;
 wire[`PT_ANALOG_CFG_W-1:0]analog_cfg;wire[`PT_DEBUG_CFG_W-1:0]debug_cfg;wire[`PT_ATB_W-1:0]atb0_sw,atb1_sw;
 wire[`PT_ATB0_GRP_W-1:0]atb0_grp;wire[`PT_ATB1_GRP_W-1:0]atb1_grp;wire atb0_en,atb1_en;
 wire rx_en_aux,rx_en_wclk,rx_en_wtx_ext,clk_obs_oe,wclk_obs_oe,clk_obs,wclk_obs;
 wire dbg_obs0,dbg_obs0_oe,dbg_obs1,dbg_obs1_oe,wdbg_obs,wdbg_obs_oe;
 // pt_clocktree_slow (hardened inside pt_digital_macro) <-> transistor-level clocktree.
 wire ct_wclk,ct_ref_clk,ct_det_clk_in,ct_word_clk,ct_word_load,ct_ser_run,ct_bit_phase,ct_qualified;
 wire ct_armed,ct_marker_seen,ct_launched,ct_arm_fault,ct_det_clk;wire[2:0]ct_det_div;
 wire[5:0]fc_src;wire cdr_freq_locked; // frequency counters rtl/pt_freq_count.sv (P3-7)
 // Asynchronous assert from either source; deassertion happens with SCLK idle (CS_N high).
 // The hardened macro forms the same function internally from its reset_n_pad, por_n and por_bypass inputs.
 // por_bypass (integration-plan G3, interface row DT-10): static strap level, 1 = ignore a POR that never
 // releases (reset by RESET_N alone). OPEN at chip level: no pad is bound yet, so it is tied 0 here (today's
 // behaviour). Pads/assembly bind it to a strap pad whose provider pull-down keeps it 0 when unbonded;
 // the pad Y must replace this constant, and the analog-side rst_n below must use the same function.
 wire por_bypass=1'b0;
 assign rst_n=pad_rst_n&(por_n|por_bypass);
 pt_host_physical host(RESET_N,SPI_SCLK,SPI_CS_N,SPI_MOSI,SPI_MISO,
 H2D,H2D_CLK,D2H,D2H_CLK,VDD_CORE,VSS_CORE,VDD_HOST_A,VSS_HOST_A,VDD_HOST_B,VSS_HOST_B,
 pad_rst_n,sclk,cs_n,mosi,miso,miso_oe,h2d_clk,h2d_pin,d2h_pin,d2h_clk_pin,d2h_oe,d2h_pdrv,d2h_sl);
 pt_analog_physical analog(REF_IN,REF_IN_N,WIRE_RX_P,WIRE_RX_N,WIRE_TX_P,WIRE_TX_N,RF_RX_P,RF_RX_N,RF_TX_P,RF_TX_N,
 VDD_CORE,VSS_CORE,VDD_WIRE_A,VSS_WIRE_A,VDD_WIRE_B,VSS_WIRE_B,VDD_RF,VSS_RF,VDD_PLL,VSS_PLL,
 rst_n,ref_clk,enable,mode8,rf_trim,wire_trim,clock_trim,trial,above,
 ht,wr,wt,rr,rt,wire_rx,wv,wire_tx,wvalid,wrequest,idle,rf_rx,rv,rf_tx,rvalid,rrequest,mute,
 BB_I_P,BB_I_N,BB_Q_P,BB_Q_N,AUX_CLK_P,AUX_CLK_N,ATB0,ATB1,WCLK_IN_P,WCLK_IN_N,WTX_EXT_P,WTX_EXT_N,WMON,ESD_TEST,
 por_n,fault,island_pgood,analog_status,wire_analog_status,
 analog_cfg,debug_cfg,island_en,island_on,atb0_sw,atb1_sw,atb0_grp,atb1_grp,atb0_en,atb1_en,rx_en_aux,rx_en_wclk,rx_en_wtx_ext,clk_obs,wclk_obs,
 ct_wclk,ct_ref_clk,ct_det_clk_in,ct_word_clk,ct_word_load,ct_ser_run,ct_bit_phase,ct_qualified,ct_det_div,ct_det_clk,fc_src,cdr_freq_locked);
 pt_debug_physical debug_pads(VDD_CORE,VSS_CORE,CLK_OBS,DBG_OBS0,DBG_OBS1,WCLK_OBS,WDBG_OBS,
 clk_obs,clk_obs_oe,dbg_obs0,dbg_obs0_oe,dbg_obs1,dbg_obs1_oe,wclk_obs,wclk_obs_oe,wdbg_obs,wdbg_obs_oe);
 // Hardened core digital macro (freeze stage 1; verification/run_digital_hardening.sh).
 // host_word_clk is the clocktree host clock (ht: line-divided or host_follow), which clocks both
 // transport directions; H2D_CLK only clocks the capture registers (rtl/pt_host_link.sv).
 // ALIGN_MARKER: SPI_SCLK while CS_N is high (analog-architecture video_alignment).
 // ct_cfg_det_en / det_div have no register-map field yet: strapped here.
 pt_digital_macro digital(.reset_n_pad(pad_rst_n),.por_n(por_n),.por_bypass(por_bypass),.spi_sclk(sclk),.spi_cs_n(cs_n),.spi_mosi(mosi),
 .spi_miso(miso),.spi_miso_oe(miso_oe),.host_word_clk(ht),.h2d_clk(h2d_clk),.h2d_pin(h2d_pin),
 .d2h_pin(d2h_pin),.d2h_clk_pin(d2h_clk_pin),.d2h_oe(d2h_oe),.d2h_pdrv(d2h_pdrv),.d2h_sl(d2h_sl),
 .ref_clk(ref_clk),.wire_rx_clk(wr),.wire_tx_clk(wt),.rf_rx_clk(rr),.rf_tx_clk(rt),
 .wire_rx_data(wire_rx),.wire_rx_valid(wv),.wire_tx_data(wire_tx),.wire_tx_valid(wvalid),.wire_idle(idle),
 .wire_tx_request(wrequest),.rf_rx_sample(rf_rx),.rf_rx_valid(rv),.rf_tx_sample(rf_tx),.rf_tx_valid(rvalid),
 .rf_mute(mute),.rf_tx_request(rrequest),.enable(enable),.mode8(mode8),.rf_trim(rf_trim),.wire_trim(wire_trim),
 .clock_trim(clock_trim),.calibration_above_target(above),.calibration_trial(trial),
 .fault(fault),.island_pgood(island_pgood),.analog_status(analog_status),.wire_analog_status(wire_analog_status),
 .fc_src(fc_src),.cdr_freq_locked(cdr_freq_locked),
 .analog_cfg(analog_cfg),.debug_cfg(debug_cfg),.island_en(island_en),.island_on(island_on),.wired_on_ext(1'b0), // PD8: WIRED_ON of pt_wtx_fallback_control (assembly binding)
 .wire_linecode(1'b0), // IX-2 8b/10b offload select: strapped off until the register field exists (interface-changes T7)
 .atb0_sw(atb0_sw),.atb1_sw(atb1_sw),.atb0_grp(atb0_grp),.atb1_grp(atb1_grp),.atb0_en(atb0_en),.atb1_en(atb1_en),
 .rx_en_aux(rx_en_aux),.rx_en_wclk(rx_en_wclk),.rx_en_wtx_ext(rx_en_wtx_ext),.clk_obs_oe(clk_obs_oe),
 .wclk_obs_oe(wclk_obs_oe),.dbg_obs0(dbg_obs0),.dbg_obs0_oe(dbg_obs0_oe),.dbg_obs1(dbg_obs1),
 .dbg_obs1_oe(dbg_obs1_oe),.wdbg_obs(wdbg_obs),.wdbg_obs_oe(wdbg_obs_oe),.commit_toggle(commit_toggle),
 .ct_wclk(ct_wclk),.ct_ref_clk(ct_ref_clk),.ct_det_clk_in(ct_det_clk_in),.ct_pll_lock(analog_status[0]),
 .ct_marker(sclk&cs_n),
 .ct_cfg_det_en(analog_cfg[`PT_A_CLOCKTREE_CONFIG__TX_ENABLE_LSB]),.ct_cfg_det_div(3'd0),
 .ct_word_clk(ct_word_clk),.ct_word_load(ct_word_load),.ct_ser_run(ct_ser_run),.ct_bit_phase(ct_bit_phase),
 .ct_qualified(ct_qualified),.ct_armed(ct_armed),.ct_marker_seen(ct_marker_seen),.ct_launched(ct_launched),
 .ct_arm_fault(ct_arm_fault),.ct_det_div(ct_det_div),.ct_det_clk(ct_det_clk));
endmodule

// Host GPIO pads (hostio): provider gf180mcu_fd_io cells only; all clocked logic (DDR/SDR capture,
// launch, forwarded clock, H2D FIFO) is pt_host_link inside pt_digital_macro.
// Sites (spec/contract.json assembly_policy) and cells:
//   RESET_N  rst_n_pad  in_c   PU=0 PD=1 (weak on-chip pull-down, tapeout-plan POR/reset row)
//   SPI_SCLK/CS_N/MOSI  bidir[11]/[10]/[12]  bi_24t  OE=0 IE=1 CS=0 (CMOS input)
//   SPI_MISO bidir[13]  bi_t  A=miso OE=miso_oe IE=0 PDRV0=0 PDRV1=1 SL=0
//   H2D[9:0], H2D_CLK  bidir[26..33,35,36], bidir[34]  bi_24t  OE=0 IE=1 CS=0 PU=PD=0
//   D2H[9:0], D2H_CLK  clk_pad, bidir[0..4,6..9], bidir[5]  bi_t  A=d2h_pin/d2h_clk_pin OE=d2h_oe
//                      SL=d2h_sl IE=0. clk_pad is an in_s site in the provider template: the
//                      provider-permitted signal-cell substitution to bi_t is required for D2H[0].
//   d2h_pdrv drives PDRV0/PDRV1. D2H stays tristated while d2h_enable=0 (reset).
// Define PT_EXTERNAL_IO and compile pt_provider_io.sv to bind the retained
// provider cells. The declarations remain available for interface-only checks.
`ifndef PT_EXTERNAL_IO
(* blackbox *) module pt_host_physical(
 inout wire RESET_N,SPI_SCLK,SPI_CS_N,SPI_MOSI,output wire SPI_MISO,
 inout wire[9:0]H2D,inout wire H2D_CLK,output wire[9:0]D2H,output wire D2H_CLK,
 inout wire VDD_CORE,VSS_CORE,VDD_HOST_A,VSS_HOST_A,VDD_HOST_B,VSS_HOST_B,
 output wire rst_n,sclk,cs_n,mosi,input wire miso,miso_oe,
 output wire h2d_clk,output wire[9:0]h2d_pin,input wire[9:0]d2h_pin,input wire d2h_clk_pin,d2h_oe,
 input wire[1:0]d2h_pdrv,input wire d2h_sl);
endmodule
`endif

// Internal architecture and circuit implementation tracked in macro-contract.md.
// Differential reference protection/conditioning belongs here, not in host GPIO.
// Debug sites: BB taps, AUX_CLK/WCLK_IN/WTX_EXT receivers, ATB switches, WMON buffer and the
// CLK_OBS/WCLK_OBS source muxes and prescalers live here; the observation pad drivers are in
// pt_debug_physical. Island switches follow island_en; island_pgood reports each local rail; every
// iso_clamp at a core/island boundary follows island_on (switch on AND (pgood OR override)).
`ifndef PT_EXTERNAL_ANALOG
(* blackbox *) module pt_analog_physical(
 input wire REF_IN,REF_IN_N,
 inout wire WIRE_RX_P,WIRE_RX_N,output wire WIRE_TX_P,WIRE_TX_N,
 input wire RF_RX_P,RF_RX_N,output wire RF_TX_P,RF_TX_N,
 inout wire VDD_CORE,VSS_CORE,VDD_WIRE_A,VSS_WIRE_A,VDD_WIRE_B,VSS_WIRE_B,VDD_RF,VSS_RF,VDD_PLL,VSS_PLL,
 input wire rst_n,output wire ref_clk,input wire enable,mode8,input wire[15:0]rf_trim,wire_trim,clock_trim,
 input wire[11:0]calibration_trial,output wire calibration_above_target,
 output wire host_tx_clk,wire_rx_clk,wire_tx_clk,rf_rx_clk,rf_tx_clk,
 output wire[39:0]wire_rx_data,output wire wire_rx_valid,input wire[39:0]wire_tx_data, // 40-bit quads (AC-1 S3), word 0 in [9:0]
 input wire wire_tx_valid,output wire wire_tx_request,input wire wire_idle,
 output wire[23:0]rf_rx_sample,output wire rf_rx_valid,input wire[23:0]rf_tx_sample,
 input wire rf_tx_valid,output wire rf_tx_request,input wire rf_mute,
 inout wire BB_I_P,BB_I_N,BB_Q_P,BB_Q_N,input wire AUX_CLK_P,AUX_CLK_N,inout wire ATB0,ATB1,
 input wire WCLK_IN_P,WCLK_IN_N,WTX_EXT_P,WTX_EXT_N,output wire WMON,inout wire ESD_TEST,
 output wire por_n,fault,output wire[`PT_ISLAND_W-1:0]island_pgood,
 output wire[11:0]analog_status,output wire[12:0]wire_analog_status,
 input wire[`PT_ANALOG_CFG_W-1:0]analog_cfg,input wire[`PT_DEBUG_CFG_W-1:0]debug_cfg,
 input wire[`PT_ISLAND_W-1:0]island_en,
 input wire[`PT_ISLAND_W-1:0]island_on, // iso_clamp control at every core/island boundary (0 = isolated)
 input wire[`PT_ATB_W-1:0]atb0_sw,atb1_sw,
 input wire[`PT_ATB0_GRP_W-1:0]atb0_grp,input wire[`PT_ATB1_GRP_W-1:0]atb1_grp,input wire atb0_en,atb1_en, // atb_grp / atb_pad SEL
 input wire rx_en_aux,rx_en_wclk,rx_en_wtx_ext,output wire clk_obs,wclk_obs,
 // pt_clocktree_slow boundary (standard-cell part hardened in pt_digital_macro): pt_prescale CK_OUT,
 // word reference, detector input clock; word divider / launch / detector clock back.
 output wire ct_wclk,ct_ref_clk,ct_det_clk_in,
 input wire ct_word_clk,ct_word_load,ct_ser_run,ct_bit_phase,ct_qualified,input wire[2:0]ct_det_div,input wire ct_det_clk,
 // Frequency-counter sources [0] tx_ring_fbck (pt_pll FBCK = VCO/16) [1] cdr_ring_fbck [2] ring_osc
 // [3] vco_replica [4] aosc [5] lc_prescale; cdr_freq_locked = CDR frequency-to-phase handover.
 output wire[5:0]fc_src,input wire cdr_freq_locked);
endmodule
`endif

// Digital observation pad cells (consolidation-pass.md item 8): tristate while oe=0 (reset).
`ifndef PT_EXTERNAL_IO
(* blackbox *) module pt_debug_physical(
 inout wire VDD_CORE,VSS_CORE,output wire CLK_OBS,DBG_OBS0,DBG_OBS1,WCLK_OBS,WDBG_OBS,
 input wire clk_obs,clk_obs_oe,dbg_obs0,dbg_obs0_oe,dbg_obs1,dbg_obs1_oe,wclk_obs,wclk_obs_oe,wdbg_obs,wdbg_obs_oe);
endmodule
`endif
