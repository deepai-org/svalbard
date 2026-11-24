// pt_analog_top_stub of pt_wired: GENERATED from wired/chip.conn by check_top.py wired --write (stub for sim/tb_top_*.sv). Do not edit.
`default_nettype wire
module pt_analog_top_stub(
 inout wire ATB0,
 inout wire ATB1,
 inout wire AUX_CLK_N,
 inout wire AUX_CLK_P,
 output wire AUX_PRESENT,
 output wire DET_DIFF_NEG,
 output wire DET_DIFF_POS,
 output wire DET_SE_N,
 output wire DET_SE_P,
 output wire PLL_CDR_FBCK,
 output wire PLL_CDR_LOCK,
 output wire PLL_TX_LOCK,
 output wire PRE_CK,
 inout wire REF_IN,
 inout wire REF_IN_N,
 output wire RING_OSC_CK,
 inout wire TLP_TEST,
 inout wire USB_DN,
 inout wire USB_DP,
 output wire VCO_REPLICA_CK,
 inout wire VDD,
 inout wire VSS,
 inout wire WIRE_RX_N,
 inout wire WIRE_RX_P,
 inout wire WIRE_TX_N,
 inout wire WIRE_TX_P,
 inout wire WMON,
 output wire [39:0] WRX_DX,
 output wire [19:0] WRX_EW,
 output wire WRX_SLM,
 output wire WRX_SLP,
 output wire WRX_WCLK40,
 output wire WTX_EXT_DATA,
 inout wire WTX_EXT_N,
 inout wire WTX_EXT_P,
 output wire WTX_EXT_PRESENT,
 output wire WTX_RUN,
 output wire WTX_WCLK40,
 input wire atb0_en,
 input wire [1:0] atb0_grp,
 input wire [57:0] atb0_sw,
 input wire atb1_en,
 input wire [4:0] atb1_grp,
 input wire [59:0] atb1_sw,
 input wire c_aosc_en,
 input wire c_bb_tap_wmon_bias_en,
 input wire c_bgap_ena,
 input wire [15:0] c_bgap_trim,
 input wire c_bias_dist_en_debug,
 input wire c_bias_dist_en_pll,
 input wire c_bias_dist_en_wire,
 input wire [2:0] c_biasgen_bandgap_sink1,
 input wire [1:0] c_biasgen_bandgap_sink2,
 input wire c_biasgen_ena,
 input wire [4:0] c_biasgen_idac1_source,
 input wire [4:0] c_biasgen_idac2_source,
 input wire c_biasgen_ref_sel_coarse,
 input wire c_biasgen_ref_sel_fine,
 input wire c_biasgen_ref_sel_vbg,
 input wire [2:0] c_biasgen_voltgen_sink1,
 input wire [2:0] c_biasgen_voltgen_sink2,
 input wire [4:0] c_biasgen_voltgen_source,
 input wire c_cdr_en,
 input wire c_cdr_fdn,
 input wire c_cdr_fup,
 input wire [2:0] c_cdr_g,
 input wire [5:0] c_cdr_otr,
 input wire c_cdr_pfd_mode,
 input wire c_cdr_ref_sel,
 input wire [2:0] c_char_en,
 input wire c_clk_obs_en,
 input wire [2:0] c_clk_obs_n,
 input wire c_clk_obs_off,
 input wire [3:0] c_clk_obs_s,
 input wire [1:0] c_clockmux_hs,
 input wire [2:0] c_clockmux_ps,
 input wire [2:0] c_clockmux_ss,
 input wire [3:0] c_clockmux_ws,
 input wire c_ctle_bypass,
 input wire c_ctle_en,
 input wire [2:0] c_ctle_lf_zero,
 input wire [2:0] c_ctle_peak,
 input wire c_detect_en,
 input wire c_detect_inject,
 input wire [1:0] c_detect_se,
 input wire c_detect_src_tx,
 input wire [1:0] c_detect_thr,
 input wire [7:0] c_hsbias_c,
 input wire c_hsbias_en,
 input wire [5:0] c_obs_pre4_en,
 input wire c_pll_cdr_band,
 input wire c_pll_cdr_en,
 input wire [2:0] c_pll_cdr_kp,
 input wire c_pll_cdr_n10,
 input wire c_pll_cdr_n4,
 input wire c_pll_cdr_n5,
 input wire c_pll_cdr_n8,
 input wire c_pll_tx_band,
 input wire c_pll_tx_en,
 input wire c_pll_tx_n4,
 input wire c_pll_tx_n8,
 input wire c_pllvreg_byp_cdr,
 input wire c_pllvreg_byp_tx,
 input wire [3:0] c_prescale_d,
 input wire c_prescale_en,
 input wire [3:0] c_prescale_hf_d,
 input wire c_prescale_hf_en,
 input wire [4:0] c_ptrim_t0,
 input wire [4:0] c_ptrim_t1,
 input wire [4:0] c_ptrim_t2,
 input wire [4:0] c_ptrim_t3,
 input wire [4:0] c_ptrim_t4,
 input wire [4:0] c_ptrim_t5,
 input wire [4:0] c_ptrim_t6,
 input wire [4:0] c_ptrim_t7,
 input wire c_refvcm_en,
 input wire c_ring_osc_en,
 input wire c_rx_ref_en,
 input wire c_rxlevel_en,
 input wire c_rxlevel_half,
 input wire c_rxselect_direct,
 input wire c_rxselect_en,
 input wire c_slicer_en,
 input wire [9:0] c_slicer_trim_d0,
 input wire [9:0] c_slicer_trim_d1,
 input wire [9:0] c_slicer_trim_d2,
 input wire [9:0] c_slicer_trim_d3,
 input wire [9:0] c_slicer_trim_e0,
 input wire [9:0] c_slicer_trim_e1,
 input wire [9:0] c_slicer_trim_e2,
 input wire [9:0] c_slicer_trim_e3,
 input wire [1:0] c_slicer_vsel_e0,
 input wire [1:0] c_slicer_vsel_e1,
 input wire [1:0] c_slicer_vsel_e2,
 input wire [1:0] c_slicer_vsel_e3,
 input wire c_term_en,
 input wire c_term_hs_en,
 input wire c_term_hs_term_en,
 input wire [3:0] c_term_hs_trim,
 input wire [1:0] c_term_mode,
 input wire c_txpad_req_detect,
 input wire c_txpad_req_main,
 input wire c_txpad_req_post,
 input wire c_txpad_req_term,
 input wire [3:0] c_txpad_term_trim,
 input wire c_usb_fs_en,
 input wire c_usb_hs_drv,
 input wire c_usb_hs_en,
 input wire [1:0] c_usb_hs_str,
 input wire c_usb_ls_slow,
 input wire c_usb_pulldown_n,
 input wire c_usb_pulldown_p,
 input wire c_usb_pullup_n,
 input wire c_usb_pullup_p,
 input wire [2:0] c_usb_term_trim,
 input wire c_usb_tx_dn,
 input wire c_usb_tx_dp,
 input wire c_usb_tx_oe,
 input wire c_vco_replica_en,
 input wire [7:0] c_vthdac_a,
 input wire [7:0] c_vthdac_b,
 input wire c_vthdac_en,
 input wire c_wiredtx_bias_en,
 input wire c_wiredtx_cascode_boost,
 input wire c_wiredtx_ext,
 input wire c_wiredtx_idle,
 input wire c_wiredtx_idle_mode,
 input wire [7:0] c_wiredtx_main_code,
 input wire [7:0] c_wiredtx_post_code,
 input wire c_wiredtx_post_pol,
 input wire c_wiredtx_ser_en,
 input wire [31:0] c_wiredtx_tr,
 input wire c_wmon_en,
 input wire c_wmon_obs_en,
 input wire [1:0] c_wmon_sel,
 input wire c_wordclk_d10,
 input wire c_wordclk_d20,
 input wire c_wordclk_en,
 input wire c_wrx_cap_b1,
 input wire c_wrx_cap_b2,
 input wire c_wrx_cap_en,
 input wire [2:0] c_wrx_cap_psel,
 input wire c_wrx_cap_rcs,
 input wire c_wrx_cap_slipm,
 input wire c_wrx_cap_slipp,
 input wire [1:0] c_wtxfb_branch,
 input wire c_wtxfb_idle,
 input wire c_wtxfb_stage_tmds,
 input wire [1:0] c_wtxfb_state,
 output wire clk_obs,
 input wire ct_det_clk,
 output wire [4:0] fc_src,
 input wire h2d_clk,
 output wire host_word_clk,
 input wire [5:0] island_en,
 input wire [5:0] island_off,
 input wire [5:0] island_on,
 output wire por_n,
 output wire ref_clk,
 input wire rx_en_aux,
 input wire rx_en_wtx_ext,
 output wire s_pg_debug,
 output wire s_pg_pll,
 output wire s_pg_wired_cap,
 output wire s_pg_wired_rx,
 output wire s_pg_wired_tx,
 output wire s_pg_wired_tx_b,
 output wire s_ref_present,
 input wire wire_rx_ptrim_en,
 input wire [39:0] wire_tx_data,
 output wire wired_on_ext
);
 wire RESET_N;
 wire SPI_SCLK;
 wire SPI_CS_N;
 wire SPI_MOSI;
 wire SPI_MISO;
 wire [9:0] H2D;
 wire H2D_CLK;
 wire [9:0] D2H;
 wire D2H_CLK;
 wire reset_n_pad;
 wire spi_sclk;
 wire spi_cs_n;
 wire spi_mosi;
 wire spi_miso;
 wire spi_miso_oe;
 wire [9:0] h2d_pin;
 wire [9:0] d2h_pin;
 wire d2h_clk_pin;
 wire d2h_oe;
 wire [1:0] d2h_pdrv;
 wire d2h_sl;
 wire CLK_OBS;
 wire DBG_OBS0;
 wire DBG_OBS1;
 wire clk_obs_oe;
 wire dbg_obs0;
 wire dbg_obs0_oe;
 wire dbg_obs1;
 wire dbg_obs1_oe;
 wire POR_BYPASS;
 wire por_bypass;
 wire REF_VCM;
 wire HOST_CLK;
 wire WIRE_CK;
 wire [7:0] CDRPH;
 wire PRE_HF_CK;
 wire PLL_TX_FBCK;
 wire AUX_CK;
 wire AUX_CK_P;
 wire VCO_REPLICA_VCTRL;
 wire OBS4_wire;
 wire WSMP_CK;
 wire OBS4_wsmp;
 wire OBS4_ref;
 wire OBS4_aux;
 wire [7:0] TXPH;
 wire OBS4_pll;
 wire OBS4_cdr;
 wire CLK_OBS_DBG;
 wire CHAR_RN_LNA;
 wire CHAR_RP_LNA;
 wire CHAR_RN_MIX;
 wire CHAR_RP_MIX;
 wire CHAR_RN_SMP;
 wire CHAR_RP_SMP;
 wire CHAR_RN_DRV;
 wire CHAR_RP_DRV;
 wire CHAR_RES_A;
 wire CHAR_RES_B;
 wire CHAR_MIM_A;
 wire CHAR_MIM_B;
 wire ATBN_master_ibias;
 wire ATB0_LOCAL0;
 wire ATBN_pll_ibias;
 wire ATBN_vbg;
 wire ATBN_debug_ibias;
 wire ATB0_GLOBAL;
 wire ATB0_LOCAL1;
 wire ATB1_LOCAL0;
 wire VREF0_MASTER;
 wire VCM_MASTER;
 wire ATB1_GLOBAL;
 wire ATB1_LOCAL1;
 wire ATB1_LOCAL2;
 wire ATB1_LOCAL3;
 wire ATBN_pll_vctrl;
 wire BIAS_pll_ring_tx;
 wire ATBN_cdr_bias;
 wire ATBN_debug_buffer_bias;
 wire ATB1_LOCAL4;
 wire ATBN_idac1;
 wire BIAS_pll_ring_rx;
 wire BIAS_cdr;
 wire BIAS_ctle;
 wire BIAS_detect;
 wire BIAS_wiredtx;
 wire BIAS_hsbias;
 wire BIAS_txpad_det;
 wire BIAS_bb_tap_wmon;
 wire ATBN_wire_ibias;
 wire ISO_wired_tx;
 wire HS_TERM_VCM;
 wire HS_TERM_ENABLE;
 wire [3:0] HS_TERM_TRIM;
 wire HS_VBIAS;
 wire HSRX_P;
 wire HSRX_N;
 wire TERM_VCM;
 wire TERM_ENABLE;
 wire DIFF_ENABLE;
 wire DIV_ENABLE;
 wire BYPASS_ENABLE;
 wire URX_P;
 wire URX_N;
 wire HS_PBIAS;
 wire USB_HS_P;
 wire USB_HS_N;
 wire USB_FS_HIGH_P;
 wire USB_FS_HIGH_N;
 wire USB_FS_LOW_P;
 wire USB_FS_LOW_N;
 wire TX_CASCODE;
 wire TX_MAIN_P;
 wire TX_MAIN_N;
 wire TX_MAIN_BIAS;
 wire TX_POST_P;
 wire TX_POST_N;
 wire TX_POST_BIAS;
 wire TX_EN_DETECT;
 wire TX_DETECT_PBIAS;
 wire TX_EN_TERM;
 wire TX_TERM_VCM;
 wire WMON_IN;
 wire PREF;
 wire CDR_REF;
 wire CDR_HOLD;
 wire CDR_VCTRL;
 wire [3:0] CDR_UP;
 wire [3:0] CDR_DN;
 wire [3:0] WRX_UP;
 wire [3:0] WRX_DN;
 wire WTX_DX_DBG;
 wire WTX_DX;
 wire CHAR_RO33_CK;
 wire CHAR_RO50_CK;
 wire CHAR_CMLDIV_CK;
 wire CTLE_P;
 wire CTLE_N;
 wire ATBN_ctle_bias;
 wire SL_P;
 wire SL_N;
 wire ATBN_detect_vref;
 wire [7:0] CKP;
 wire WRX_LDE;
 wire VTAP;
 wire VTAN;
 wire VTBP;
 wire VTBN;
 wire [7:0] SLS;
 wire TX_EN_MAIN;
 wire TX_EN_POST;
 wire WTX_TAP_P;
 wire WTX_TAP_N;
 wire ATBN_wiredtx_avgp;
 wire ATBN_wiredtx_avgn;
 wire ATBN_wiredtx_bias;
 wire TX_BUF_REF;
 wire TX_BUF_BIAS;
 wire WTX_FORCE_SELECTED;
 wire RAIL_debug = VDD, RAIL_pll = VDD, RAIL_wired_cap = VDD, RAIL_wired_rx = VDD, RAIL_wired_tx = VDD, VREG_CDR = VDD, VREG_TX = VDD;
 wire p_por__ena = VDD;
 assign por_n = 1'b1;
 wire p_aosc__EN = c_aosc_en;
 assign fc_src[4] = 1'b0;
 wire p_isw_pll__EN = island_en[2];
 assign s_pg_pll = island_en[2];
 wire p_refvcm__EN = c_refvcm_en;
 wire p_rx_ref_in__EN = c_rx_ref_en;
 wire p_rx_ref_in__SE = VSS;
 assign ref_clk = 1'b0;
 assign s_ref_present = 1'b0;
 wire p_iso_host_clk__A = HOST_CLK;
 wire p_iso_host_clk__ISO = island_off[2];
 assign host_word_clk = HOST_CLK & ~island_off[2];
 wire p_prescale__CK_IN = WIRE_CK;
 wire p_prescale__EN = c_prescale_en;
 wire p_prescale__D2 = c_prescale_d[0];
 wire p_prescale__D4 = c_prescale_d[1];
 wire p_prescale__D8 = c_prescale_d[2];
 wire p_prescale__D16 = c_prescale_d[3];
 assign PRE_CK = 1'b0;
 wire p_prescale_hf__CK_IN = CDRPH[0];
 wire p_prescale_hf__EN = c_prescale_hf_en;
 wire p_prescale_hf__D2 = c_prescale_hf_d[0];
 wire p_prescale_hf__D4 = c_prescale_hf_d[1];
 wire p_prescale_hf__D8 = c_prescale_hf_d[2];
 wire p_prescale_hf__D16 = c_prescale_hf_d[3];
 assign PRE_HF_CK = 1'b0;
 wire p_pll_vreg2__BYP_TX = c_pllvreg_byp_tx;
 wire p_pll_vreg2__BYP_CDR = c_pllvreg_byp_cdr;
 wire p_iso_pll_tx_fbck__A = PLL_TX_FBCK;
 wire p_iso_pll_tx_fbck__ISO = island_off[2];
 assign fc_src[0] = PLL_TX_FBCK & ~island_off[2];
 wire p_rx_aux_clk__EN = rx_en_aux;
 wire p_rx_aux_clk__SE = VSS;
 assign AUX_CK = 1'b0;
 assign AUX_PRESENT = 1'b0;
 wire p_iso_aux_ck__A = AUX_CK;
 wire p_iso_aux_ck__ISO = island_off[5];
 assign AUX_CK_P = AUX_CK & ~island_off[5];
 wire p_ring_osc__EN = c_ring_osc_en;
 assign RING_OSC_CK = 1'b0;
 wire p_vco_replica__EN = c_vco_replica_en;
 assign VCO_REPLICA_CK = 1'b0;
 wire p_obs_pre4_wire__CK = WIRE_CK;
 wire p_obs_pre4_wire__EN = c_obs_pre4_en[0];
 assign OBS4_wire = 1'b0;
 wire p_obs_pre4_wsmp__CK = WSMP_CK;
 wire p_obs_pre4_wsmp__EN = c_obs_pre4_en[1];
 assign OBS4_wsmp = 1'b0;
 wire p_obs_pre4_ref__CK = ref_clk;
 wire p_obs_pre4_ref__EN = c_obs_pre4_en[2];
 assign OBS4_ref = 1'b0;
 wire p_obs_pre4_aux__CK = AUX_CK;
 wire p_obs_pre4_aux__EN = c_obs_pre4_en[3];
 assign OBS4_aux = 1'b0;
 wire p_obs_pre4_pll__CK = TXPH[1];
 wire p_obs_pre4_pll__EN = c_obs_pre4_en[4];
 assign OBS4_pll = 1'b0;
 wire p_obs_pre4_cdr__CK = CDRPH[1];
 wire p_obs_pre4_cdr__EN = c_obs_pre4_en[5];
 assign OBS4_cdr = 1'b0;
 wire p_pd_clk_obs__ISO = c_clk_obs_off;
 wire p_iso_clk_obs__A = CLK_OBS_DBG;
 wire p_iso_clk_obs__ISO = island_off[5];
 assign clk_obs = CLK_OBS_DBG & ~island_off[5];
 wire p_atb0_leaf1__SEL = atb0_sw[0];
 wire p_atb0_leaf29__SEL = atb0_sw[28];
 wire p_atb0_leaf55__SEL = atb0_sw[54];
 wire p_atb0_leaf56__SEL = atb0_sw[55];
 wire p_atb0_leaf58__SEL = atb0_sw[57];
 wire p_atb0_grp0__SEL = atb0_grp[0];
 wire p_atb0_leaf43__SEL = atb0_sw[42];
 wire p_atb0_leaf44__SEL = atb0_sw[43];
 wire p_atb0_leaf45__SEL = atb0_sw[44];
 wire p_atb0_leaf46__SEL = atb0_sw[45];
 wire p_atb0_leaf47__SEL = atb0_sw[46];
 wire p_atb0_leaf48__SEL = atb0_sw[47];
 wire p_atb0_leaf49__SEL = atb0_sw[48];
 wire p_atb0_leaf50__SEL = atb0_sw[49];
 wire p_atb0_leaf51__SEL = atb0_sw[50];
 wire p_atb0_leaf52__SEL = atb0_sw[51];
 wire p_atb0_leaf53__SEL = atb0_sw[52];
 wire p_atb0_leaf54__SEL = atb0_sw[53];
 wire p_atb0_grp1__SEL = atb0_grp[1];
 wire p_atb0_pad__SEL = atb0_en;
 wire p_atb1_leaf1__SEL = atb1_sw[0];
 wire p_atb1_leaf2__SEL = atb1_sw[1];
 wire p_atb1_leaf3__SEL = atb1_sw[2];
 wire p_atb1_leaf4__SEL = atb1_sw[3];
 wire p_atb1_leaf5__SEL = atb1_sw[4];
 wire p_atb1_leaf6__SEL = atb1_sw[5];
 wire p_atb1_leaf9__SEL = atb1_sw[8];
 wire p_atb1_leaf12__SEL = atb1_sw[11];
 wire p_atb1_leaf13__SEL = atb1_sw[12];
 wire p_atb1_grp0__SEL = atb1_grp[0];
 wire p_atb1_leaf43__SEL = atb1_sw[42];
 wire p_atb1_leaf44__SEL = atb1_sw[43];
 wire p_atb1_grp1__SEL = atb1_grp[1];
 wire p_atb1_leaf25__SEL = atb1_sw[24];
 wire p_atb1_leaf41__SEL = atb1_sw[40];
 wire p_atb1_leaf58__SEL = atb1_sw[57];
 wire p_atb1_grp2__SEL = atb1_grp[2];
 wire p_atb1_leaf29__SEL = atb1_sw[28];
 wire p_atb1_leaf30__SEL = atb1_sw[29];
 wire p_atb1_leaf31__SEL = atb1_sw[30];
 wire p_atb1_leaf32__SEL = atb1_sw[31];
 wire p_atb1_leaf34__SEL = atb1_sw[33];
 wire p_atb1_leaf37__SEL = atb1_sw[36];
 wire p_atb1_leaf47__SEL = atb1_sw[46];
 wire p_atb1_leaf48__SEL = atb1_sw[47];
 wire p_atb1_grp3__SEL = atb1_grp[3];
 wire p_atb1_leaf42__SEL = atb1_sw[41];
 wire p_atb1_leaf45__SEL = atb1_sw[44];
 wire p_atb1_leaf46__SEL = atb1_sw[45];
 wire p_atb1_leaf49__SEL = atb1_sw[48];
 wire p_atb1_leaf50__SEL = atb1_sw[49];
 wire p_atb1_leaf51__SEL = atb1_sw[50];
 wire p_atb1_leaf52__SEL = atb1_sw[51];
 wire p_atb1_leaf53__SEL = atb1_sw[52];
 wire p_atb1_leaf54__SEL = atb1_sw[53];
 wire p_atb1_leaf55__SEL = atb1_sw[54];
 wire p_atb1_leaf56__SEL = atb1_sw[55];
 wire p_atb1_leaf57__SEL = atb1_sw[56];
 wire p_atb1_grp4__SEL = atb1_grp[4];
 wire p_atb1_pad__SEL = atb1_en;
 wire p_core_bias__ON_wired = island_on[0];
 wire p_core_bias__ON_pll = island_on[2];
 wire p_core_bias__ON_debug = island_on[5];
 wire p_core_bias__C_core_biasgen_ena = c_biasgen_ena;
 wire p_core_bias__C_core_biasgen_ref_sel_vbg = c_biasgen_ref_sel_vbg;
 wire p_core_bias__C_core_biasgen_ref_sel_coarse = c_biasgen_ref_sel_coarse;
 wire p_core_bias__C_core_biasgen_ref_sel_fine = c_biasgen_ref_sel_fine;
 wire p_core_bias__C_core_biasgen_idac2_source_0 = c_biasgen_idac2_source[0];
 wire p_core_bias__C_core_biasgen_idac2_source_1 = c_biasgen_idac2_source[1];
 wire p_core_bias__C_core_biasgen_idac2_source_2 = c_biasgen_idac2_source[2];
 wire p_core_bias__C_core_biasgen_idac2_source_3 = c_biasgen_idac2_source[3];
 wire p_core_bias__C_core_biasgen_idac2_source_4 = c_biasgen_idac2_source[4];
 wire p_core_bias__C_core_biasgen_idac1_source_0 = c_biasgen_idac1_source[0];
 wire p_core_bias__C_core_biasgen_idac1_source_1 = c_biasgen_idac1_source[1];
 wire p_core_bias__C_core_biasgen_idac1_source_2 = c_biasgen_idac1_source[2];
 wire p_core_bias__C_core_biasgen_idac1_source_3 = c_biasgen_idac1_source[3];
 wire p_core_bias__C_core_biasgen_idac1_source_4 = c_biasgen_idac1_source[4];
 wire p_core_bias__C_core_biasgen_bandgap_sink1_0 = c_biasgen_bandgap_sink1[0];
 wire p_core_bias__C_core_biasgen_bandgap_sink1_1 = c_biasgen_bandgap_sink1[1];
 wire p_core_bias__C_core_biasgen_bandgap_sink1_2 = c_biasgen_bandgap_sink1[2];
 wire p_core_bias__C_core_biasgen_bandgap_sink2_0 = c_biasgen_bandgap_sink2[0];
 wire p_core_bias__C_core_biasgen_bandgap_sink2_1 = c_biasgen_bandgap_sink2[1];
 wire p_core_bias__C_core_biasgen_voltgen_source_0 = c_biasgen_voltgen_source[0];
 wire p_core_bias__C_core_biasgen_voltgen_source_1 = c_biasgen_voltgen_source[1];
 wire p_core_bias__C_core_biasgen_voltgen_source_2 = c_biasgen_voltgen_source[2];
 wire p_core_bias__C_core_biasgen_voltgen_source_3 = c_biasgen_voltgen_source[3];
 wire p_core_bias__C_core_biasgen_voltgen_source_4 = c_biasgen_voltgen_source[4];
 wire p_core_bias__C_core_biasgen_voltgen_sink1_0 = c_biasgen_voltgen_sink1[0];
 wire p_core_bias__C_core_biasgen_voltgen_sink1_1 = c_biasgen_voltgen_sink1[1];
 wire p_core_bias__C_core_biasgen_voltgen_sink1_2 = c_biasgen_voltgen_sink1[2];
 wire p_core_bias__C_core_biasgen_voltgen_sink2_0 = c_biasgen_voltgen_sink2[0];
 wire p_core_bias__C_core_biasgen_voltgen_sink2_1 = c_biasgen_voltgen_sink2[1];
 wire p_core_bias__C_core_biasgen_voltgen_sink2_2 = c_biasgen_voltgen_sink2[2];
 wire p_core_bias__C_core_refchain_bgap_ena = c_bgap_ena;
 wire p_core_bias__C_core_refchain_bgap_trim_0 = c_bgap_trim[0];
 wire p_core_bias__C_core_refchain_bgap_trim_1 = c_bgap_trim[1];
 wire p_core_bias__C_core_refchain_bgap_trim_2 = c_bgap_trim[2];
 wire p_core_bias__C_core_refchain_bgap_trim_3 = c_bgap_trim[3];
 wire p_core_bias__C_core_refchain_bgap_trim_4 = c_bgap_trim[4];
 wire p_core_bias__C_core_refchain_bgap_trim_5 = c_bgap_trim[5];
 wire p_core_bias__C_core_refchain_bgap_trim_6 = c_bgap_trim[6];
 wire p_core_bias__C_core_refchain_bgap_trim_7 = c_bgap_trim[7];
 wire p_core_bias__C_core_refchain_bgap_trim_8 = c_bgap_trim[8];
 wire p_core_bias__C_core_refchain_bgap_trim_9 = c_bgap_trim[9];
 wire p_core_bias__C_core_refchain_bgap_trim_10 = c_bgap_trim[10];
 wire p_core_bias__C_core_refchain_bgap_trim_11 = c_bgap_trim[11];
 wire p_core_bias__C_core_refchain_bgap_trim_12 = c_bgap_trim[12];
 wire p_core_bias__C_core_refchain_bgap_trim_13 = c_bgap_trim[13];
 wire p_core_bias__C_core_refchain_bgap_trim_14 = c_bgap_trim[14];
 wire p_core_bias__C_core_refchain_bgap_trim_15 = c_bgap_trim[15];
 wire p_core_bias__C_core_refchain_dist_en_pll = c_bias_dist_en_pll;
 wire p_core_bias__C_core_refchain_dist_en_wire = c_bias_dist_en_wire;
 wire p_core_bias__C_core_refchain_dist_en_debug = c_bias_dist_en_debug;
 wire p_core_bias__EN_pll_ring_tx = c_pll_tx_en;
 wire p_core_bias__EN_pll_ring_rx = c_pll_cdr_en;
 wire p_core_bias__EN_cdr = c_cdr_en;
 wire p_core_bias__EN_ctle = c_ctle_en;
 wire p_core_bias__EN_detect = c_detect_en;
 wire p_core_bias__EN_wiredtx = c_wiredtx_bias_en;
 wire p_core_bias__EN_hsbias = c_hsbias_en;
 wire p_core_bias__EN_txpad_det = c_txpad_req_detect;
 wire p_core_bias__EN_bb_tap_wmon = c_bb_tap_wmon_bias_en;
 wire p_isw_wired_rx__EN = island_en[0];
 assign s_pg_wired_rx = island_en[0];
 wire p_isw_debug__EN = island_en[5];
 assign s_pg_debug = island_en[5];
 wire p_isw_wired_tx_a__EN = island_en[0];
 assign ISO_wired_tx = ~island_en[0];
 assign s_pg_wired_tx = island_en[0];
 wire p_isw_wired_tx_b__EN = island_en[0];
 assign s_pg_wired_tx_b = island_en[0];
 wire p_isw_wired_cap__EN = island_en[0];
 assign s_pg_wired_cap = island_en[0];
 wire p_pad_hs_rx__TERM_ENABLE = HS_TERM_ENABLE;
 wire p_pad_hs_rx__TERM_TRIM0 = HS_TERM_TRIM[0];
 wire p_pad_hs_rx__TERM_TRIM1 = HS_TERM_TRIM[1];
 wire p_pad_hs_rx__TERM_TRIM2 = HS_TERM_TRIM[2];
 wire p_pad_hs_rx__TERM_TRIM3 = HS_TERM_TRIM[3];
 wire p_pad_usb__TERM_ENABLE = TERM_ENABLE;
 wire p_pad_usb__DIFF_ENABLE = DIFF_ENABLE;
 wire p_pad_usb__DIV_ENABLE = DIV_ENABLE;
 wire p_pad_usb__BYPASS_ENABLE = BYPASS_ENABLE;
 wire p_pad_usb__HS_P = USB_HS_P;
 wire p_pad_usb__HS_N = USB_HS_N;
 wire p_pad_usb__FS_HIGH_P = USB_FS_HIGH_P;
 wire p_pad_usb__FS_HIGH_N = USB_FS_HIGH_N;
 wire p_pad_usb__FS_LOW_P = USB_FS_LOW_P;
 wire p_pad_usb__FS_LOW_N = USB_FS_LOW_N;
 wire p_pad_usb__PULLUP_P = c_usb_pullup_p;
 wire p_pad_usb__PULLUP_N = c_usb_pullup_n;
 wire p_pad_usb__PULLDOWN_P = c_usb_pulldown_p;
 wire p_pad_usb__PULLDOWN_N = c_usb_pulldown_n;
 wire p_pad_usb__TERM_TRIM0 = c_usb_term_trim[0];
 wire p_pad_usb__TERM_TRIM1 = c_usb_term_trim[1];
 wire p_pad_usb__TERM_TRIM2 = c_usb_term_trim[2];
 wire p_pad_usb__LS_SLOW = c_usb_ls_slow;
 wire p_pad_wire_tx__TERM_TRIM0 = c_txpad_term_trim[0];
 wire p_pad_wire_tx__TERM_TRIM1 = c_txpad_term_trim[1];
 wire p_pad_wire_tx__TERM_TRIM2 = c_txpad_term_trim[2];
 wire p_pad_wire_tx__TERM_TRIM3 = c_txpad_term_trim[3];
 wire p_pad_wire_tx__MAIN_P = TX_MAIN_P;
 wire p_pad_wire_tx__MAIN_N = TX_MAIN_N;
 wire p_pad_wire_tx__POST_P = TX_POST_P;
 wire p_pad_wire_tx__POST_N = TX_POST_N;
 wire p_pad_wire_tx__TMDS_P = VSS;
 wire p_pad_wire_tx__TMDS_N = VSS;
 wire p_pad_wire_tx__DETECT_ENABLE = TX_EN_DETECT;
 wire p_pad_wire_tx__TERM_ENABLE = TX_EN_TERM;
 wire p_bb_tap_wmon__obs_en = c_wmon_obs_en;
 wire p_bb_tap_wmon__inj_en = VSS;
 wire p_bb_tap_wmon__island_off = island_off[5];
 wire p_iso_wmon__ISO = island_off[0];
 wire p_clockmux__PLLW = TXPH[0];
 wire p_clockmux__REF = ref_clk;
 wire p_clockmux__AUX = AUX_CK_P;
 wire p_clockmux__WCK = AUX_CK_P;
 wire p_clockmux__H2D = h2d_clk;
 wire p_clockmux__WSI = CDRPH[0];
 wire p_clockmux__CONV_INT = VSS;
 wire p_clockmux__HOST_INT = PRE_CK;
 wire p_clockmux__HF = PRE_HF_CK;
 wire p_clockmux__PS_REF = c_clockmux_ps[0];
 wire p_clockmux__PS_AUX = c_clockmux_ps[1];
 wire p_clockmux__PS_H2D = c_clockmux_ps[2];
 wire p_clockmux__WS_PLL = c_clockmux_ws[0];
 wire p_clockmux__WS_REF = c_clockmux_ws[1];
 wire p_clockmux__WS_AUX = c_clockmux_ws[2];
 wire p_clockmux__WS_WCK = c_clockmux_ws[3];
 wire p_clockmux__SS_INT = c_clockmux_ss[0];
 wire p_clockmux__SS_REF = c_clockmux_ss[1];
 wire p_clockmux__SS_WCK = c_clockmux_ss[2];
 wire p_clockmux__CS_INT = VSS;
 wire p_clockmux__CS_REF = VSS;
 wire p_clockmux__CS_AUX = VSS;
 wire p_clockmux__CS_HF = VSS;
 wire p_clockmux__HS_INT = c_clockmux_hs[0];
 wire p_clockmux__HS_HF = c_clockmux_hs[1];
 assign PREF = 1'b0;
 assign WIRE_CK = 1'b0;
 assign WSMP_CK = 1'b0;
 assign HOST_CLK = 1'b0;
 wire p_pll_tx__REF = PREF;
 wire p_pll_tx__EN = c_pll_tx_en;
 wire p_pll_tx__N4 = c_pll_tx_n4;
 wire p_pll_tx__N8 = c_pll_tx_n8;
 wire p_pll_tx__HOLD = VSS;
 assign TXPH[0] = 1'b0;
 assign TXPH[1] = 1'b0;
 assign TXPH[2] = 1'b0;
 assign TXPH[3] = 1'b0;
 assign TXPH[4] = 1'b0;
 assign TXPH[5] = 1'b0;
 assign TXPH[6] = 1'b0;
 assign TXPH[7] = 1'b0;
 assign PLL_TX_LOCK = 1'b0;
 assign PLL_TX_FBCK = 1'b0;
 wire p_pll_tx__BAND = c_pll_tx_band;
 wire p_pll_cdr__REF = CDR_REF;
 wire p_pll_cdr__EN = c_pll_cdr_en;
 wire p_pll_cdr__N4 = c_pll_cdr_n4;
 wire p_pll_cdr__N8 = c_pll_cdr_n8;
 wire p_pll_cdr__N5 = c_pll_cdr_n5;
 wire p_pll_cdr__N10 = c_pll_cdr_n10;
 wire p_pll_cdr__HOLD = CDR_HOLD;
 assign CDRPH[0] = 1'b0;
 assign CDRPH[1] = 1'b0;
 assign CDRPH[2] = 1'b0;
 assign CDRPH[3] = 1'b0;
 assign CDRPH[4] = 1'b0;
 assign CDRPH[5] = 1'b0;
 assign CDRPH[6] = 1'b0;
 assign CDRPH[7] = 1'b0;
 assign PLL_CDR_LOCK = 1'b0;
 assign PLL_CDR_FBCK = 1'b0;
 wire p_pll_cdr__KP0 = c_pll_cdr_kp[0];
 wire p_pll_cdr__KP1 = c_pll_cdr_kp[1];
 wire p_pll_cdr__KP2 = c_pll_cdr_kp[2];
 wire p_pll_cdr__FU0 = CDR_UP[0];
 wire p_pll_cdr__FU1 = CDR_UP[1];
 wire p_pll_cdr__FU2 = CDR_UP[2];
 wire p_pll_cdr__FU3 = CDR_UP[3];
 wire p_pll_cdr__FD0 = CDR_DN[0];
 wire p_pll_cdr__FD1 = CDR_DN[1];
 wire p_pll_cdr__FD2 = CDR_DN[2];
 wire p_pll_cdr__FD3 = CDR_DN[3];
 wire p_pll_cdr__BAND = c_pll_cdr_band;
 wire p_cdr__cdr_en = c_cdr_en;
 wire p_cdr__pfd_mode = c_cdr_pfd_mode;
 wire p_cdr__ref_sel = c_cdr_ref_sel;
 wire p_cdr__g0 = c_cdr_g[0];
 wire p_cdr__g1 = c_cdr_g[1];
 wire p_cdr__g2 = c_cdr_g[2];
 wire p_cdr__UP0 = CDR_UP[0];
 wire p_cdr__UP1 = CDR_UP[1];
 wire p_cdr__UP2 = CDR_UP[2];
 wire p_cdr__UP3 = CDR_UP[3];
 wire p_cdr__DN0 = CDR_DN[0];
 wire p_cdr__DN1 = CDR_DN[1];
 wire p_cdr__DN2 = CDR_DN[2];
 wire p_cdr__DN3 = CDR_DN[3];
 wire p_cdr__FUP = c_cdr_fup;
 wire p_cdr__FDN = c_cdr_fdn;
 assign CDR_HOLD = 1'b0;
 wire p_cdr__REF_IN = PREF;
 wire p_cdr__WCK_IN = AUX_CK_P;
 assign CDR_REF = 1'b0;
 wire p_cdr__otr0 = c_cdr_otr[0];
 wire p_cdr__otr1 = c_cdr_otr[1];
 wire p_cdr__otr2 = c_cdr_otr[2];
 wire p_cdr__otr3 = c_cdr_otr[3];
 wire p_cdr__otr4 = c_cdr_otr[4];
 wire p_cdr__otrs = c_cdr_otr[5];
 wire p_iso_cdr_up_0__A = WRX_UP[0];
 wire p_iso_cdr_up_0__ISO = island_off[0];
 assign CDR_UP[0] = WRX_UP[0] & ~island_off[0];
 wire p_iso_cdr_up_1__A = WRX_UP[1];
 wire p_iso_cdr_up_1__ISO = island_off[0];
 assign CDR_UP[1] = WRX_UP[1] & ~island_off[0];
 wire p_iso_cdr_up_2__A = WRX_UP[2];
 wire p_iso_cdr_up_2__ISO = island_off[0];
 assign CDR_UP[2] = WRX_UP[2] & ~island_off[0];
 wire p_iso_cdr_up_3__A = WRX_UP[3];
 wire p_iso_cdr_up_3__ISO = island_off[0];
 assign CDR_UP[3] = WRX_UP[3] & ~island_off[0];
 wire p_iso_cdr_dn_0__A = WRX_DN[0];
 wire p_iso_cdr_dn_0__ISO = island_off[0];
 assign CDR_DN[0] = WRX_DN[0] & ~island_off[0];
 wire p_iso_cdr_dn_1__A = WRX_DN[1];
 wire p_iso_cdr_dn_1__ISO = island_off[0];
 assign CDR_DN[1] = WRX_DN[1] & ~island_off[0];
 wire p_iso_cdr_dn_2__A = WRX_DN[2];
 wire p_iso_cdr_dn_2__ISO = island_off[0];
 assign CDR_DN[2] = WRX_DN[2] & ~island_off[0];
 wire p_iso_cdr_dn_3__A = WRX_DN[3];
 wire p_iso_cdr_dn_3__ISO = island_off[0];
 assign CDR_DN[3] = WRX_DN[3] & ~island_off[0];
 wire p_rx_wtx_ext__EN = rx_en_wtx_ext;
 wire p_rx_wtx_ext__SE = VSS;
 assign WTX_DX_DBG = 1'b0;
 assign WTX_EXT_PRESENT = 1'b0;
 wire p_iso_wtx_dx__A = WTX_DX_DBG;
 wire p_iso_wtx_dx__ISO = island_off[5];
 assign WTX_DX = WTX_DX_DBG & ~island_off[5];
 wire p_clk_obs__IN0 = VSS;
 wire p_clk_obs__IN1 = VSS;
 wire p_clk_obs__IN2 = OBS4_wire;
 wire p_clk_obs__IN3 = OBS4_wsmp;
 wire p_clk_obs__IN4 = VSS;
 wire p_clk_obs__IN5 = OBS4_ref;
 wire p_clk_obs__IN6 = OBS4_aux;
 wire p_clk_obs__IN7 = VSS;
 wire p_clk_obs__IN8 = OBS4_pll;
 wire p_clk_obs__IN9 = fc_src[0];
 wire p_clk_obs__IN10 = RING_OSC_CK;
 wire p_clk_obs__IN11 = VCO_REPLICA_CK;
 wire p_clk_obs__IN12 = fc_src[4];
 wire p_clk_obs__IN13 = host_word_clk;
 wire p_clk_obs__IN14 = OBS4_cdr;
 wire p_clk_obs__IN15A = CHAR_RO33_CK;
 wire p_clk_obs__IN15B = CHAR_RO50_CK;
 wire p_clk_obs__IN15C = CHAR_CMLDIV_CK;
 wire p_clk_obs__S0 = c_clk_obs_s[0];
 wire p_clk_obs__S1 = c_clk_obs_s[1];
 wire p_clk_obs__S2 = c_clk_obs_s[2];
 wire p_clk_obs__S3 = c_clk_obs_s[3];
 wire p_clk_obs__N0 = c_clk_obs_n[0];
 wire p_clk_obs__N1 = c_clk_obs_n[1];
 wire p_clk_obs__N2 = c_clk_obs_n[2];
 wire p_clk_obs__EN = c_clk_obs_en;
 assign CLK_OBS_DBG = 1'b0;
 wire p_termination__term_en = c_term_en;
 wire p_termination__term_mode0 = c_term_mode[0];
 wire p_termination__term_mode1 = c_term_mode[1];
 wire p_termination__hs_en = c_term_hs_en;
 wire p_termination__hs_term_en = c_term_hs_term_en;
 wire p_termination__hs_trim0 = c_term_hs_trim[0];
 wire p_termination__hs_trim1 = c_term_hs_trim[1];
 wire p_termination__hs_trim2 = c_term_hs_trim[2];
 wire p_termination__hs_trim3 = c_term_hs_trim[3];
 assign TERM_ENABLE = 1'b0;
 assign DIFF_ENABLE = 1'b0;
 assign HS_TERM_ENABLE = 1'b0;
 assign HS_TERM_TRIM[0] = 1'b0;
 assign HS_TERM_TRIM[1] = 1'b0;
 assign HS_TERM_TRIM[2] = 1'b0;
 assign HS_TERM_TRIM[3] = 1'b0;
 wire p_rxlevel__rxlevel_en = c_rxlevel_en;
 wire p_rxlevel__rxlevel_half = c_rxlevel_half;
 assign DIV_ENABLE = 1'b0;
 assign BYPASS_ENABLE = 1'b0;
 wire p_ctle__ctle_en = c_ctle_en;
 wire p_ctle__wire_ctle_bypass = c_ctle_bypass;
 wire p_ctle__ctle_peak0 = c_ctle_peak[0];
 wire p_ctle__ctle_peak1 = c_ctle_peak[1];
 wire p_ctle__ctle_peak2 = c_ctle_peak[2];
 wire p_ctle__lf_zero0 = c_ctle_lf_zero[0];
 wire p_ctle__lf_zero1 = c_ctle_lf_zero[1];
 wire p_ctle__lf_zero2 = c_ctle_lf_zero[2];
 wire p_rxselect__rxselect_en = c_rxselect_en;
 wire p_rxselect__rxselect_direct = c_rxselect_direct;
 wire p_wmon_sel__wmon_en = c_wmon_en;
 wire p_wmon_sel__wmon_sel0 = c_wmon_sel[0];
 wire p_wmon_sel__wmon_sel1 = c_wmon_sel[1];
 wire p_detect__det_en = c_detect_en;
 wire p_detect__det_clk = ct_det_clk;
 wire p_detect__det_thr0 = c_detect_thr[0];
 wire p_detect__det_thr1 = c_detect_thr[1];
 wire p_detect__det_se0 = c_detect_se[0];
 wire p_detect__det_se1 = c_detect_se[1];
 wire p_detect__det_src_tx = c_detect_src_tx;
 wire p_detect__det_inject = c_detect_inject;
 assign DET_DIFF_POS = 1'b0;
 assign DET_DIFF_NEG = 1'b0;
 assign DET_SE_P = 1'b0;
 assign DET_SE_N = 1'b0;
 wire p_wordclk_rx__CK = CKP[0];
 wire p_wordclk_rx__EN = c_wordclk_en;
 wire p_wordclk_rx__D10 = c_wordclk_d10;
 wire p_wordclk_rx__D20 = c_wordclk_d20;
 assign WRX_LDE = 1'b0;
 wire p_vthdac__vth_en = c_vthdac_en;
 wire p_vthdac__A0 = c_vthdac_a[0];
 wire p_vthdac__A1 = c_vthdac_a[1];
 wire p_vthdac__A2 = c_vthdac_a[2];
 wire p_vthdac__A3 = c_vthdac_a[3];
 wire p_vthdac__A4 = c_vthdac_a[4];
 wire p_vthdac__A5 = c_vthdac_a[5];
 wire p_vthdac__A6 = c_vthdac_a[6];
 wire p_vthdac__A7 = c_vthdac_a[7];
 wire p_vthdac__B0 = c_vthdac_b[0];
 wire p_vthdac__B1 = c_vthdac_b[1];
 wire p_vthdac__B2 = c_vthdac_b[2];
 wire p_vthdac__B3 = c_vthdac_b[3];
 wire p_vthdac__B4 = c_vthdac_b[4];
 wire p_vthdac__B5 = c_vthdac_b[5];
 wire p_vthdac__B6 = c_vthdac_b[6];
 wire p_vthdac__B7 = c_vthdac_b[7];
 wire p_ptrim__ptrim_en = wire_rx_ptrim_en;
 wire p_ptrim__PH0 = CDRPH[0];
 wire p_ptrim__PH1 = CDRPH[1];
 wire p_ptrim__PH2 = CDRPH[2];
 wire p_ptrim__PH3 = CDRPH[3];
 wire p_ptrim__PH4 = CDRPH[4];
 wire p_ptrim__PH5 = CDRPH[5];
 wire p_ptrim__PH6 = CDRPH[6];
 wire p_ptrim__PH7 = CDRPH[7];
 assign CKP[0] = 1'b0;
 assign CKP[1] = 1'b0;
 assign CKP[2] = 1'b0;
 assign CKP[3] = 1'b0;
 assign CKP[4] = 1'b0;
 assign CKP[5] = 1'b0;
 assign CKP[6] = 1'b0;
 assign CKP[7] = 1'b0;
 wire p_ptrim__T0_0 = c_ptrim_t0[0];
 wire p_ptrim__T0_1 = c_ptrim_t0[1];
 wire p_ptrim__T0_2 = c_ptrim_t0[2];
 wire p_ptrim__T0_3 = c_ptrim_t0[3];
 wire p_ptrim__T0_4 = c_ptrim_t0[4];
 wire p_ptrim__T1_0 = c_ptrim_t1[0];
 wire p_ptrim__T1_1 = c_ptrim_t1[1];
 wire p_ptrim__T1_2 = c_ptrim_t1[2];
 wire p_ptrim__T1_3 = c_ptrim_t1[3];
 wire p_ptrim__T1_4 = c_ptrim_t1[4];
 wire p_ptrim__T2_0 = c_ptrim_t2[0];
 wire p_ptrim__T2_1 = c_ptrim_t2[1];
 wire p_ptrim__T2_2 = c_ptrim_t2[2];
 wire p_ptrim__T2_3 = c_ptrim_t2[3];
 wire p_ptrim__T2_4 = c_ptrim_t2[4];
 wire p_ptrim__T3_0 = c_ptrim_t3[0];
 wire p_ptrim__T3_1 = c_ptrim_t3[1];
 wire p_ptrim__T3_2 = c_ptrim_t3[2];
 wire p_ptrim__T3_3 = c_ptrim_t3[3];
 wire p_ptrim__T3_4 = c_ptrim_t3[4];
 wire p_ptrim__T4_0 = c_ptrim_t4[0];
 wire p_ptrim__T4_1 = c_ptrim_t4[1];
 wire p_ptrim__T4_2 = c_ptrim_t4[2];
 wire p_ptrim__T4_3 = c_ptrim_t4[3];
 wire p_ptrim__T4_4 = c_ptrim_t4[4];
 wire p_ptrim__T5_0 = c_ptrim_t5[0];
 wire p_ptrim__T5_1 = c_ptrim_t5[1];
 wire p_ptrim__T5_2 = c_ptrim_t5[2];
 wire p_ptrim__T5_3 = c_ptrim_t5[3];
 wire p_ptrim__T5_4 = c_ptrim_t5[4];
 wire p_ptrim__T6_0 = c_ptrim_t6[0];
 wire p_ptrim__T6_1 = c_ptrim_t6[1];
 wire p_ptrim__T6_2 = c_ptrim_t6[2];
 wire p_ptrim__T6_3 = c_ptrim_t6[3];
 wire p_ptrim__T6_4 = c_ptrim_t6[4];
 wire p_ptrim__T7_0 = c_ptrim_t7[0];
 wire p_ptrim__T7_1 = c_ptrim_t7[1];
 wire p_ptrim__T7_2 = c_ptrim_t7[2];
 wire p_ptrim__T7_3 = c_ptrim_t7[3];
 wire p_ptrim__T7_4 = c_ptrim_t7[4];
 wire p_slicer__slicer_en = c_slicer_en;
 wire p_slicer__CKP0 = CKP[0];
 wire p_slicer__CKP1 = CKP[1];
 wire p_slicer__CKP2 = CKP[2];
 wire p_slicer__CKP3 = CKP[3];
 wire p_slicer__CKP4 = CKP[4];
 wire p_slicer__CKP5 = CKP[5];
 wire p_slicer__CKP6 = CKP[6];
 wire p_slicer__CKP7 = CKP[7];
 assign SLS[0] = 1'b0;
 assign SLS[2] = 1'b0;
 assign SLS[4] = 1'b0;
 assign SLS[6] = 1'b0;
 assign SLS[1] = 1'b0;
 assign SLS[3] = 1'b0;
 assign SLS[5] = 1'b0;
 assign SLS[7] = 1'b0;
 wire p_slicer__trim_d0_p0 = c_slicer_trim_d0[0];
 wire p_slicer__trim_d0_p1 = c_slicer_trim_d0[1];
 wire p_slicer__trim_d0_p2 = c_slicer_trim_d0[2];
 wire p_slicer__trim_d0_n0 = c_slicer_trim_d0[3];
 wire p_slicer__trim_d0_n1 = c_slicer_trim_d0[4];
 wire p_slicer__trim_d0_n2 = c_slicer_trim_d0[5];
 wire p_slicer__trim_d0_f0 = c_slicer_trim_d0[6];
 wire p_slicer__trim_d0_f1 = c_slicer_trim_d0[7];
 wire p_slicer__trim_d0_f2 = c_slicer_trim_d0[8];
 wire p_slicer__trim_d0_f3 = c_slicer_trim_d0[9];
 wire p_slicer__trim_d1_p0 = c_slicer_trim_d1[0];
 wire p_slicer__trim_d1_p1 = c_slicer_trim_d1[1];
 wire p_slicer__trim_d1_p2 = c_slicer_trim_d1[2];
 wire p_slicer__trim_d1_n0 = c_slicer_trim_d1[3];
 wire p_slicer__trim_d1_n1 = c_slicer_trim_d1[4];
 wire p_slicer__trim_d1_n2 = c_slicer_trim_d1[5];
 wire p_slicer__trim_d1_f0 = c_slicer_trim_d1[6];
 wire p_slicer__trim_d1_f1 = c_slicer_trim_d1[7];
 wire p_slicer__trim_d1_f2 = c_slicer_trim_d1[8];
 wire p_slicer__trim_d1_f3 = c_slicer_trim_d1[9];
 wire p_slicer__trim_d2_p0 = c_slicer_trim_d2[0];
 wire p_slicer__trim_d2_p1 = c_slicer_trim_d2[1];
 wire p_slicer__trim_d2_p2 = c_slicer_trim_d2[2];
 wire p_slicer__trim_d2_n0 = c_slicer_trim_d2[3];
 wire p_slicer__trim_d2_n1 = c_slicer_trim_d2[4];
 wire p_slicer__trim_d2_n2 = c_slicer_trim_d2[5];
 wire p_slicer__trim_d2_f0 = c_slicer_trim_d2[6];
 wire p_slicer__trim_d2_f1 = c_slicer_trim_d2[7];
 wire p_slicer__trim_d2_f2 = c_slicer_trim_d2[8];
 wire p_slicer__trim_d2_f3 = c_slicer_trim_d2[9];
 wire p_slicer__trim_d3_p0 = c_slicer_trim_d3[0];
 wire p_slicer__trim_d3_p1 = c_slicer_trim_d3[1];
 wire p_slicer__trim_d3_p2 = c_slicer_trim_d3[2];
 wire p_slicer__trim_d3_n0 = c_slicer_trim_d3[3];
 wire p_slicer__trim_d3_n1 = c_slicer_trim_d3[4];
 wire p_slicer__trim_d3_n2 = c_slicer_trim_d3[5];
 wire p_slicer__trim_d3_f0 = c_slicer_trim_d3[6];
 wire p_slicer__trim_d3_f1 = c_slicer_trim_d3[7];
 wire p_slicer__trim_d3_f2 = c_slicer_trim_d3[8];
 wire p_slicer__trim_d3_f3 = c_slicer_trim_d3[9];
 wire p_slicer__trim_e0_p0 = c_slicer_trim_e0[0];
 wire p_slicer__trim_e0_p1 = c_slicer_trim_e0[1];
 wire p_slicer__trim_e0_p2 = c_slicer_trim_e0[2];
 wire p_slicer__trim_e0_n0 = c_slicer_trim_e0[3];
 wire p_slicer__trim_e0_n1 = c_slicer_trim_e0[4];
 wire p_slicer__trim_e0_n2 = c_slicer_trim_e0[5];
 wire p_slicer__trim_e0_f0 = c_slicer_trim_e0[6];
 wire p_slicer__trim_e0_f1 = c_slicer_trim_e0[7];
 wire p_slicer__trim_e0_f2 = c_slicer_trim_e0[8];
 wire p_slicer__trim_e0_f3 = c_slicer_trim_e0[9];
 wire p_slicer__trim_e1_p0 = c_slicer_trim_e1[0];
 wire p_slicer__trim_e1_p1 = c_slicer_trim_e1[1];
 wire p_slicer__trim_e1_p2 = c_slicer_trim_e1[2];
 wire p_slicer__trim_e1_n0 = c_slicer_trim_e1[3];
 wire p_slicer__trim_e1_n1 = c_slicer_trim_e1[4];
 wire p_slicer__trim_e1_n2 = c_slicer_trim_e1[5];
 wire p_slicer__trim_e1_f0 = c_slicer_trim_e1[6];
 wire p_slicer__trim_e1_f1 = c_slicer_trim_e1[7];
 wire p_slicer__trim_e1_f2 = c_slicer_trim_e1[8];
 wire p_slicer__trim_e1_f3 = c_slicer_trim_e1[9];
 wire p_slicer__trim_e2_p0 = c_slicer_trim_e2[0];
 wire p_slicer__trim_e2_p1 = c_slicer_trim_e2[1];
 wire p_slicer__trim_e2_p2 = c_slicer_trim_e2[2];
 wire p_slicer__trim_e2_n0 = c_slicer_trim_e2[3];
 wire p_slicer__trim_e2_n1 = c_slicer_trim_e2[4];
 wire p_slicer__trim_e2_n2 = c_slicer_trim_e2[5];
 wire p_slicer__trim_e2_f0 = c_slicer_trim_e2[6];
 wire p_slicer__trim_e2_f1 = c_slicer_trim_e2[7];
 wire p_slicer__trim_e2_f2 = c_slicer_trim_e2[8];
 wire p_slicer__trim_e2_f3 = c_slicer_trim_e2[9];
 wire p_slicer__trim_e3_p0 = c_slicer_trim_e3[0];
 wire p_slicer__trim_e3_p1 = c_slicer_trim_e3[1];
 wire p_slicer__trim_e3_p2 = c_slicer_trim_e3[2];
 wire p_slicer__trim_e3_n0 = c_slicer_trim_e3[3];
 wire p_slicer__trim_e3_n1 = c_slicer_trim_e3[4];
 wire p_slicer__trim_e3_n2 = c_slicer_trim_e3[5];
 wire p_slicer__trim_e3_f0 = c_slicer_trim_e3[6];
 wire p_slicer__trim_e3_f1 = c_slicer_trim_e3[7];
 wire p_slicer__trim_e3_f2 = c_slicer_trim_e3[8];
 wire p_slicer__trim_e3_f3 = c_slicer_trim_e3[9];
 wire p_slicer__vsel_e0_0 = c_slicer_vsel_e0[0];
 wire p_slicer__vsel_e0_1 = c_slicer_vsel_e0[1];
 wire p_slicer__vsel_e1_0 = c_slicer_vsel_e1[0];
 wire p_slicer__vsel_e1_1 = c_slicer_vsel_e1[1];
 wire p_slicer__vsel_e2_0 = c_slicer_vsel_e2[0];
 wire p_slicer__vsel_e2_1 = c_slicer_vsel_e2[1];
 wire p_slicer__vsel_e3_0 = c_slicer_vsel_e3[0];
 wire p_slicer__vsel_e3_1 = c_slicer_vsel_e3[1];
 wire p_wrx_cap__S0 = SLS[0];
 wire p_wrx_cap__S1 = SLS[1];
 wire p_wrx_cap__S2 = SLS[2];
 wire p_wrx_cap__S3 = SLS[3];
 wire p_wrx_cap__S4 = SLS[4];
 wire p_wrx_cap__S5 = SLS[5];
 wire p_wrx_cap__S6 = SLS[6];
 wire p_wrx_cap__S7 = SLS[7];
 wire p_wrx_cap__CKP0 = CKP[0];
 wire p_wrx_cap__CKP1 = CKP[1];
 wire p_wrx_cap__CKP2 = CKP[2];
 wire p_wrx_cap__CKP3 = CKP[3];
 wire p_wrx_cap__CKP4 = CKP[4];
 wire p_wrx_cap__CKP5 = CKP[5];
 wire p_wrx_cap__CKP6 = CKP[6];
 wire p_wrx_cap__CKP7 = CKP[7];
 wire p_wrx_cap__EN = c_wrx_cap_en;
 wire p_wrx_cap__LDE = WRX_LDE;
 wire p_wrx_cap__RCS = c_wrx_cap_rcs;
 wire p_wrx_cap__B2 = c_wrx_cap_b2;
 wire p_wrx_cap__B1 = c_wrx_cap_b1;
 wire p_wrx_cap__PSEL0 = c_wrx_cap_psel[0];
 wire p_wrx_cap__PSEL1 = c_wrx_cap_psel[1];
 wire p_wrx_cap__PSEL2 = c_wrx_cap_psel[2];
 wire p_wrx_cap__SLIPP = c_wrx_cap_slipp;
 wire p_wrx_cap__SLIPM = c_wrx_cap_slipm;
 assign WRX_EW[0] = 1'b0;
 assign WRX_EW[1] = 1'b0;
 assign WRX_EW[2] = 1'b0;
 assign WRX_EW[3] = 1'b0;
 assign WRX_EW[4] = 1'b0;
 assign WRX_EW[5] = 1'b0;
 assign WRX_EW[6] = 1'b0;
 assign WRX_EW[7] = 1'b0;
 assign WRX_EW[8] = 1'b0;
 assign WRX_EW[9] = 1'b0;
 assign WRX_EW[10] = 1'b0;
 assign WRX_EW[11] = 1'b0;
 assign WRX_EW[12] = 1'b0;
 assign WRX_EW[13] = 1'b0;
 assign WRX_EW[14] = 1'b0;
 assign WRX_EW[15] = 1'b0;
 assign WRX_EW[16] = 1'b0;
 assign WRX_EW[17] = 1'b0;
 assign WRX_EW[18] = 1'b0;
 assign WRX_EW[19] = 1'b0;
 assign WRX_SLP = 1'b0;
 assign WRX_SLM = 1'b0;
 assign WRX_UP[0] = 1'b0;
 assign WRX_UP[1] = 1'b0;
 assign WRX_UP[2] = 1'b0;
 assign WRX_UP[3] = 1'b0;
 assign WRX_DN[0] = 1'b0;
 assign WRX_DN[1] = 1'b0;
 assign WRX_DN[2] = 1'b0;
 assign WRX_DN[3] = 1'b0;
 assign WRX_DX[0] = 1'b0;
 assign WRX_DX[1] = 1'b0;
 assign WRX_DX[2] = 1'b0;
 assign WRX_DX[3] = 1'b0;
 assign WRX_DX[4] = 1'b0;
 assign WRX_DX[5] = 1'b0;
 assign WRX_DX[6] = 1'b0;
 assign WRX_DX[7] = 1'b0;
 assign WRX_DX[8] = 1'b0;
 assign WRX_DX[9] = 1'b0;
 assign WRX_DX[10] = 1'b0;
 assign WRX_DX[11] = 1'b0;
 assign WRX_DX[12] = 1'b0;
 assign WRX_DX[13] = 1'b0;
 assign WRX_DX[14] = 1'b0;
 assign WRX_DX[15] = 1'b0;
 assign WRX_DX[16] = 1'b0;
 assign WRX_DX[17] = 1'b0;
 assign WRX_DX[18] = 1'b0;
 assign WRX_DX[19] = 1'b0;
 assign WRX_DX[20] = 1'b0;
 assign WRX_DX[21] = 1'b0;
 assign WRX_DX[22] = 1'b0;
 assign WRX_DX[23] = 1'b0;
 assign WRX_DX[24] = 1'b0;
 assign WRX_DX[25] = 1'b0;
 assign WRX_DX[26] = 1'b0;
 assign WRX_DX[27] = 1'b0;
 assign WRX_DX[28] = 1'b0;
 assign WRX_DX[29] = 1'b0;
 assign WRX_DX[30] = 1'b0;
 assign WRX_DX[31] = 1'b0;
 assign WRX_DX[32] = 1'b0;
 assign WRX_DX[33] = 1'b0;
 assign WRX_DX[34] = 1'b0;
 assign WRX_DX[35] = 1'b0;
 assign WRX_DX[36] = 1'b0;
 assign WRX_DX[37] = 1'b0;
 assign WRX_DX[38] = 1'b0;
 assign WRX_DX[39] = 1'b0;
 assign WRX_WCLK40 = 1'b0;
 wire p_wiredtx__PH0 = TXPH[0];
 wire p_wiredtx__PH1 = TXPH[1];
 wire p_wiredtx__PH2 = TXPH[2];
 wire p_wiredtx__PH3 = TXPH[3];
 wire p_wiredtx__PH4 = TXPH[4];
 wire p_wiredtx__PH5 = TXPH[5];
 wire p_wiredtx__PH6 = TXPH[6];
 wire p_wiredtx__PH7 = TXPH[7];
 wire p_wiredtx__D0 = wire_tx_data[0];
 wire p_wiredtx__D1 = wire_tx_data[1];
 wire p_wiredtx__D2 = wire_tx_data[2];
 wire p_wiredtx__D3 = wire_tx_data[3];
 wire p_wiredtx__D4 = wire_tx_data[4];
 wire p_wiredtx__D5 = wire_tx_data[5];
 wire p_wiredtx__D6 = wire_tx_data[6];
 wire p_wiredtx__D7 = wire_tx_data[7];
 wire p_wiredtx__D8 = wire_tx_data[8];
 wire p_wiredtx__D9 = wire_tx_data[9];
 wire p_wiredtx__D10 = wire_tx_data[10];
 wire p_wiredtx__D11 = wire_tx_data[11];
 wire p_wiredtx__D12 = wire_tx_data[12];
 wire p_wiredtx__D13 = wire_tx_data[13];
 wire p_wiredtx__D14 = wire_tx_data[14];
 wire p_wiredtx__D15 = wire_tx_data[15];
 wire p_wiredtx__D16 = wire_tx_data[16];
 wire p_wiredtx__D17 = wire_tx_data[17];
 wire p_wiredtx__D18 = wire_tx_data[18];
 wire p_wiredtx__D19 = wire_tx_data[19];
 wire p_wiredtx__D20 = wire_tx_data[20];
 wire p_wiredtx__D21 = wire_tx_data[21];
 wire p_wiredtx__D22 = wire_tx_data[22];
 wire p_wiredtx__D23 = wire_tx_data[23];
 wire p_wiredtx__D24 = wire_tx_data[24];
 wire p_wiredtx__D25 = wire_tx_data[25];
 wire p_wiredtx__D26 = wire_tx_data[26];
 wire p_wiredtx__D27 = wire_tx_data[27];
 wire p_wiredtx__D28 = wire_tx_data[28];
 wire p_wiredtx__D29 = wire_tx_data[29];
 wire p_wiredtx__D30 = wire_tx_data[30];
 wire p_wiredtx__D31 = wire_tx_data[31];
 wire p_wiredtx__D32 = wire_tx_data[32];
 wire p_wiredtx__D33 = wire_tx_data[33];
 wire p_wiredtx__D34 = wire_tx_data[34];
 wire p_wiredtx__D35 = wire_tx_data[35];
 wire p_wiredtx__D36 = wire_tx_data[36];
 wire p_wiredtx__D37 = wire_tx_data[37];
 wire p_wiredtx__D38 = wire_tx_data[38];
 wire p_wiredtx__D39 = wire_tx_data[39];
 assign WTX_WCLK40 = 1'b0;
 wire p_wiredtx__SER_EN = c_wiredtx_ser_en;
 wire p_wiredtx__WTX_EXT = c_wiredtx_ext;
 wire p_wiredtx__DX = WTX_DX;
 wire p_wiredtx__IDLE = c_wiredtx_idle;
 wire p_wiredtx__IDLE_MODE = c_wiredtx_idle_mode;
 wire p_wiredtx__TAP_EN = c_usb_hs_en;
 wire p_wiredtx__TR0_0 = c_wiredtx_tr[0];
 wire p_wiredtx__TR0_1 = c_wiredtx_tr[1];
 wire p_wiredtx__TR0_2 = c_wiredtx_tr[2];
 wire p_wiredtx__TR0_3 = c_wiredtx_tr[3];
 wire p_wiredtx__TR1_0 = c_wiredtx_tr[4];
 wire p_wiredtx__TR1_1 = c_wiredtx_tr[5];
 wire p_wiredtx__TR1_2 = c_wiredtx_tr[6];
 wire p_wiredtx__TR1_3 = c_wiredtx_tr[7];
 wire p_wiredtx__TR2_0 = c_wiredtx_tr[8];
 wire p_wiredtx__TR2_1 = c_wiredtx_tr[9];
 wire p_wiredtx__TR2_2 = c_wiredtx_tr[10];
 wire p_wiredtx__TR2_3 = c_wiredtx_tr[11];
 wire p_wiredtx__TR3_0 = c_wiredtx_tr[12];
 wire p_wiredtx__TR3_1 = c_wiredtx_tr[13];
 wire p_wiredtx__TR3_2 = c_wiredtx_tr[14];
 wire p_wiredtx__TR3_3 = c_wiredtx_tr[15];
 wire p_wiredtx__TR4_0 = c_wiredtx_tr[16];
 wire p_wiredtx__TR4_1 = c_wiredtx_tr[17];
 wire p_wiredtx__TR4_2 = c_wiredtx_tr[18];
 wire p_wiredtx__TR4_3 = c_wiredtx_tr[19];
 wire p_wiredtx__TR5_0 = c_wiredtx_tr[20];
 wire p_wiredtx__TR5_1 = c_wiredtx_tr[21];
 wire p_wiredtx__TR5_2 = c_wiredtx_tr[22];
 wire p_wiredtx__TR5_3 = c_wiredtx_tr[23];
 wire p_wiredtx__TR6_0 = c_wiredtx_tr[24];
 wire p_wiredtx__TR6_1 = c_wiredtx_tr[25];
 wire p_wiredtx__TR6_2 = c_wiredtx_tr[26];
 wire p_wiredtx__TR6_3 = c_wiredtx_tr[27];
 wire p_wiredtx__TR7_0 = c_wiredtx_tr[28];
 wire p_wiredtx__TR7_1 = c_wiredtx_tr[29];
 wire p_wiredtx__TR7_2 = c_wiredtx_tr[30];
 wire p_wiredtx__TR7_3 = c_wiredtx_tr[31];
 wire p_wiredtx__POST_POL = c_wiredtx_post_pol;
 wire p_wiredtx__EN_MAIN = TX_EN_MAIN;
 wire p_wiredtx__EN_POST = TX_EN_POST;
 wire p_wiredtx__ISLAND_OFF = island_off[0];
 wire p_wiredtx__MAIN_CODE0 = c_wiredtx_main_code[0];
 wire p_wiredtx__MAIN_CODE1 = c_wiredtx_main_code[1];
 wire p_wiredtx__MAIN_CODE2 = c_wiredtx_main_code[2];
 wire p_wiredtx__MAIN_CODE3 = c_wiredtx_main_code[3];
 wire p_wiredtx__MAIN_CODE4 = c_wiredtx_main_code[4];
 wire p_wiredtx__MAIN_CODE5 = c_wiredtx_main_code[5];
 wire p_wiredtx__MAIN_CODE6 = c_wiredtx_main_code[6];
 wire p_wiredtx__MAIN_CODE7 = c_wiredtx_main_code[7];
 wire p_wiredtx__POST_CODE0 = c_wiredtx_post_code[0];
 wire p_wiredtx__POST_CODE1 = c_wiredtx_post_code[1];
 wire p_wiredtx__POST_CODE2 = c_wiredtx_post_code[2];
 wire p_wiredtx__POST_CODE3 = c_wiredtx_post_code[3];
 wire p_wiredtx__POST_CODE4 = c_wiredtx_post_code[4];
 wire p_wiredtx__POST_CODE5 = c_wiredtx_post_code[5];
 wire p_wiredtx__POST_CODE6 = c_wiredtx_post_code[6];
 wire p_wiredtx__POST_CODE7 = c_wiredtx_post_code[7];
 assign TX_MAIN_P = 1'b0;
 assign TX_MAIN_N = 1'b0;
 assign TX_POST_P = 1'b0;
 assign TX_POST_N = 1'b0;
 assign WTX_TAP_P = 1'b0;
 assign WTX_TAP_N = 1'b0;
 assign WTX_RUN = 1'b0;
 assign WTX_EXT_DATA = 1'b0;
 wire p_steer_4__IN = VSS;
 wire p_steer_5__IN = VSS;
 wire p_attached_tx_interlock__REQ_MAIN = c_txpad_req_main;
 wire p_attached_tx_interlock__REQ_POST = c_txpad_req_post;
 wire p_attached_tx_interlock__REQ_TMDS = VSS;
 wire p_attached_tx_interlock__REQ_DETECT = c_txpad_req_detect;
 wire p_attached_tx_interlock__REQ_TERM = c_txpad_req_term;
 wire p_attached_tx_interlock__RESET = island_off[0];
 wire p_attached_tx_interlock__QUALIFIED = island_on[0];
 wire p_attached_tx_interlock__SUPPLY_OK = s_pg_wired_tx;
 assign TX_EN_MAIN = 1'b0;
 assign TX_EN_POST = 1'b0;
 assign TX_EN_DETECT = 1'b0;
 assign TX_EN_TERM = 1'b0;
 wire p_cascode_pump__CB_EN = c_wiredtx_cascode_boost;
 wire p_term_buffer__ENABLE = island_on[0];
 wire p_txpad_bias__EN = TX_EN_TERM;
 wire p_txpad_bias__EN_DET = TX_EN_DETECT;
 wire p_usb_txdrv__CMD_P = WTX_TAP_P;
 wire p_usb_txdrv__CMD_N = WTX_TAP_N;
 wire p_usb_txdrv__HS_EN = c_usb_hs_en;
 wire p_usb_txdrv__HS_DRV = c_usb_hs_drv;
 wire p_usb_txdrv__FS_EN = c_usb_fs_en;
 wire p_usb_txdrv__TX_DP = c_usb_tx_dp;
 wire p_usb_txdrv__TX_DN = c_usb_tx_dn;
 wire p_usb_txdrv__TX_OE = c_usb_tx_oe;
 wire p_usb_txdrv__ISLAND_OFF = island_off[0];
 wire p_usb_txdrv__HS_STR0 = c_usb_hs_str[0];
 wire p_usb_txdrv__HS_STR1 = c_usb_hs_str[1];
 assign USB_HS_P = 1'b0;
 assign USB_HS_N = 1'b0;
 assign USB_FS_HIGH_P = 1'b0;
 assign USB_FS_HIGH_N = 1'b0;
 assign USB_FS_LOW_P = 1'b0;
 assign USB_FS_LOW_N = 1'b0;
 wire p_hsbias__EN = c_hsbias_en;
 wire p_hsbias__C0 = c_hsbias_c[0];
 wire p_hsbias__C1 = c_hsbias_c[1];
 wire p_hsbias__C2 = c_hsbias_c[2];
 wire p_hsbias__C3 = c_hsbias_c[3];
 wire p_hsbias__C4 = c_hsbias_c[4];
 wire p_hsbias__C5 = c_hsbias_c[5];
 wire p_hsbias__C6 = c_hsbias_c[6];
 wire p_hsbias__C7 = c_hsbias_c[7];
 wire p_wtx_fallback_control__L_BRANCH0 = c_wtxfb_branch[0];
 wire p_wtx_fallback_control__L_BRANCH1 = c_wtxfb_branch[1];
 wire p_wtx_fallback_control__L_STATE0 = c_wtxfb_state[0];
 wire p_wtx_fallback_control__L_STATE1 = c_wtxfb_state[1];
 wire p_wtx_fallback_control__L_IDLE = c_wtxfb_idle;
 wire p_wtx_fallback_control__L_STAGE_TMDS = c_wtxfb_stage_tmds;
 wire p_wtx_fallback_control__L_EXT_ENABLE = c_wiredtx_ext;
 wire p_wtx_fallback_control__ISO_wired = ISO_wired_tx;
 wire p_wtx_fallback_control__FORCE_LEAF = atb0_sw[21];
 assign wired_on_ext = 1'b0;
 assign WTX_FORCE_SELECTED = 1'b0;
 wire p_char_ro33__EN = c_char_en[0];
 assign CHAR_RO33_CK = 1'b0;
 wire p_char_ro50__EN = c_char_en[1];
 assign CHAR_RO50_CK = 1'b0;
 wire p_char_cmldiv__EN = c_char_en[2];
 assign CHAR_CMLDIV_CK = 1'b0;
 wire p_atb0_leaf22__SEL = WTX_FORCE_SELECTED;
 wire p_atb1_leaf7__SEL = atb1_sw[6];
 wire p_atb1_leaf10__SEL = atb1_sw[9];
 wire p_atb1_leaf22__SEL = atb1_sw[21];
 wire p_atb1_leaf23__SEL = atb1_sw[22];
 wire p_atb1_leaf24__SEL = atb1_sw[23];
 wire p_atb1_leaf26__SEL = atb1_sw[25];
 wire p_atb1_leaf27__SEL = atb1_sw[26];
 wire p_atb1_leaf28__SEL = atb1_sw[27];
 wire p_atb1_leaf40__SEL = atb1_sw[39];
 wire p_atb1_leaf59__SEL = atb1_sw[58];
 wire p_atb1_leaf60__SEL = atb1_sw[59];
endmodule
