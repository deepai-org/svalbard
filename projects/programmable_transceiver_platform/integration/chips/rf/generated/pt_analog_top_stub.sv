// pt_analog_top_stub of pt_rf: GENERATED from rf/chip.conn by check_top.py rf --write (stub for sim/tb_top_*.sv). Do not edit.
`default_nettype wire
module pt_analog_top_stub(
 output wire [9:0] ADCI_CODE,
 output wire [9:0] ADCI_CODEB,
 output wire ADCI_DONE,
 output wire ADCI_DONEB,
 output wire ADCI_OVL,
 output wire ADCI_OVLB,
 output wire ADCI_PH,
 output wire [9:0] ADCQ_CODE,
 output wire [9:0] ADCQ_CODEB,
 output wire ADCQ_DONE,
 output wire ADCQ_DONEB,
 output wire ADCQ_OVL,
 output wire ADCQ_OVLB,
 output wire ADCQ_PH,
 inout wire ATB0,
 inout wire ATB1,
 inout wire AUX_CLK_N,
 inout wire AUX_CLK_P,
 output wire AUX_PRESENT,
 inout wire BB_I_N,
 inout wire BB_I_P,
 inout wire BB_Q_N,
 inout wire BB_Q_P,
 output wire CONV_CLK,
 output wire LO_FB,
 output wire PLL_CDR_FBCK,
 output wire PLL_CDR_LOCK,
 output wire PLL_TX_LOCK,
 output wire PRE_CK,
 output wire REFBUF_READY,
 inout wire REF_IN,
 inout wire REF_IN_N,
 inout wire RF_RX_N,
 inout wire RF_RX_P,
 inout wire RF_TX_N,
 inout wire RF_TX_P,
 output wire RING_OSC_CK,
 output wire VCO_REPLICA_CK,
 inout wire VDD,
 inout wire VSS,
 input wire atb0_en,
 input wire [1:0] atb0_grp,
 input wire [57:0] atb0_sw,
 input wire atb1_en,
 input wire [4:0] atb1_grp,
 input wire [57:0] atb1_sw,
 input wire [1:0] c_adc_acq,
 input wire c_adc_i_en,
 input wire [1:0] c_adc_i_test,
 input wire c_adc_ilen,
 input wire c_adc_q_en,
 input wire [1:0] c_adc_q_test,
 input wire c_aosc_en,
 input wire c_bb_tap_i_bias_en,
 input wire c_bb_tap_inj_en,
 input wire c_bb_tap_obs_en,
 input wire c_bb_tap_q_bias_en,
 input wire c_bbfilter_byp_s1,
 input wire c_bbfilter_byp_s23,
 input wire c_bbfilter_dir_tx,
 input wire [6:0] c_bbfilter_i_cut,
 input wire [8:0] c_bbfilter_i_dcf,
 input wire c_bbfilter_i_en,
 input wire [5:0] c_bbfilter_i_gain,
 input wire [1:0] c_bbfilter_i_gainc,
 input wire [3:0] c_bbfilter_i_qt,
 input wire c_bbfilter_inj,
 input wire [1:0] c_bbfilter_obs_sel,
 input wire [6:0] c_bbfilter_q_cut,
 input wire [8:0] c_bbfilter_q_dcf,
 input wire c_bbfilter_q_en,
 input wire [5:0] c_bbfilter_q_gain,
 input wire [1:0] c_bbfilter_q_gainc,
 input wire [3:0] c_bbfilter_q_qt,
 input wire c_bbfilter_rx_direct,
 input wire c_bgap_ena,
 input wire [15:0] c_bgap_trim,
 input wire c_bias_dist_en_conv,
 input wire c_bias_dist_en_debug,
 input wire c_bias_dist_en_pll,
 input wire c_bias_dist_en_rf,
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
 input wire [2:0] c_cdr_g,
 input wire [5:0] c_cdr_otr,
 input wire c_cdr_pfd_mode,
 input wire c_cdr_ref_sel,
 input wire c_clk_obs_en,
 input wire [2:0] c_clk_obs_n,
 input wire c_clk_obs_off,
 input wire [3:0] c_clk_obs_s,
 input wire [3:0] c_clockmux_cs,
 input wire [1:0] c_clockmux_hs,
 input wire [2:0] c_clockmux_ps,
 input wire [2:0] c_clockmux_ss,
 input wire [3:0] c_clockmux_ws,
 input wire c_dac_i_en,
 input wire c_dac_i_hold_zero,
 input wire c_dac_q_en,
 input wire c_dac_q_hold_zero,
 input wire [4:0] c_lna_att,
 input wire c_lna_byp,
 input wire [3:0] c_lna_ct,
 input wire c_lna_en,
 input wire c_lna_gain_lo,
 input wire c_lna_lobias,
 input wire c_lna_rt,
 input wire c_lna_se,
 input wire c_lo_cmlsel,
 input wire c_lo_ext,
 input wire [1:0] c_lo_icp,
 input wire c_lo_int,
 input wire c_lo_mmd_en,
 input wire [5:0] c_lo_mmd_n,
 input wire c_lo_obs_en,
 input wire c_lo_pfdcp_en,
 input wire c_lo_pre,
 input wire c_lo_vreg_en,
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
 input wire [3:0] c_prescale_conv_d,
 input wire c_prescale_conv_en,
 input wire [3:0] c_prescale_d,
 input wire c_prescale_en,
 input wire [3:0] c_prescale_hf_d,
 input wire c_prescale_hf_en,
 input wire c_qvco_atb_en,
 input wire [3:0] c_qvco_band,
 input wire c_qvco_en,
 input wire c_refbuf_en,
 input wire c_refbuf_ovr,
 input wire c_refvcm_en,
 input wire c_rfdriver_bypass,
 input wire c_rfdriver_en,
 input wire [3:0] c_rfdriver_g,
 input wire c_rfdriver_mute,
 input wire c_rfdriver_se,
 input wire c_ring_osc_en,
 input wire c_rx_ref_en,
 input wire c_rxmix_hib,
 input wire c_rxmix_i_en,
 input wire [5:0] c_rxmix_i_ofs,
 input wire c_rxmix_q_en,
 input wire [5:0] c_rxmix_q_ofs,
 input wire c_txmix_i_en,
 input wire c_txmix_q_en,
 input wire c_txmix_sat,
 input wire c_txmix_sel_dac,
 input wire c_txsum_en,
 input wire c_vco_replica_en,
 output wire clk_obs,
 output wire [4:0] fc_src,
 input wire h2d_clk,
 output wire host_word_clk,
 input wire [5:0] island_en,
 input wire [5:0] island_off,
 input wire [5:0] island_on,
 output wire por_n,
 output wire ref_clk,
 output wire rf_rx_clk,
 input wire rf_tx_clk_out,
 input wire [23:0] rf_tx_sample,
 input wire rx_en_aux,
 output wire s_pg_conv,
 output wire s_pg_debug,
 output wire s_pg_lo,
 output wire s_pg_lod,
 output wire s_pg_pll,
 output wire s_pg_rf_rx,
 output wire s_pg_rf_tx,
 output wire s_ref_present
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
 wire [1:0] CDRPH;
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
 wire [1:0] TXPH;
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
 wire BIAS_lna;
 wire BIAS_rxmix_i;
 wire BIAS_rxmix_q;
 wire BIAS_bbfilter_i;
 wire BIAS_bbfilter_q;
 wire BIAS_txmix_i;
 wire BIAS_txmix_q;
 wire BIAS_rfdriver;
 wire BIAS_adc_i;
 wire BIAS_adc_q;
 wire BIAS_dac_i;
 wire BIAS_dac_q;
 wire BIAS_refbuf;
 wire BIAS_pll_ring_rx;
 wire BIAS_cdr;
 wire BIAS_qvco;
 wire BIAS_lo_pfdcp;
 wire BIAS_bb_tap_i;
 wire BIAS_bb_tap_q;
 wire ATBN_rf_ibias;
 wire ATBN_conv_ibias;
 wire ESD_RAIL_rf_rx;
 wire ESD_RAIL_rf_tx;
 wire ESD_RAIL_bb;
 wire RFA_I_P;
 wire RFA_I_N;
 wire RFA_Q_P;
 wire RFA_Q_N;
 wire ATBN_lna_bias;
 wire ATBN_rf_vcm;
 wire LNA_SRC_P;
 wire LNA_SRC_N;
 wire LNA_TANK_P;
 wire LNA_TANK_N;
 wire LNA_TAIL;
 wire LNA_VTK;
 wire LO_IP;
 wire LO_IN;
 wire BBI_RX_P;
 wire BBI_RX_N;
 wire ATBN_rxmix_bias;
 wire LO_QP;
 wire LO_QN;
 wire BBQ_RX_P;
 wire BBQ_RX_N;
 wire DACI_P;
 wire DACI_N;
 wire BBI_INJ_P;
 wire BBI_INJ_N;
 wire ADCI_P;
 wire ADCI_N;
 wire BBI_TX_P;
 wire BBI_TX_N;
 wire BBI_OBS_P;
 wire BBI_OBS_N;
 wire ATBN_pga_bias;
 wire ATBN_bbfilter_bias;
 wire DACQ_P;
 wire DACQ_N;
 wire BBQ_INJ_P;
 wire BBQ_INJ_N;
 wire ADCQ_P;
 wire ADCQ_N;
 wire BBQ_TX_P;
 wire BBQ_TX_N;
 wire BBQ_OBS_P;
 wire BBQ_OBS_N;
 wire VREF_CONV;
 wire CONV_CLK_C;
 wire ATBN_adc_bias;
 wire ATBN_dac_bias;
 wire TXI_P;
 wire TXI_N;
 wire ATBN_txmix_bias;
 wire TXQ_P;
 wire TXQ_N;
 wire TXS_P;
 wire TXS_N;
 wire ATBN_rfdriver_bias;
 wire LOI_IP;
 wire LOI_IN;
 wire LOI_QP;
 wire LOI_QN;
 wire ATBN_quadrature_bias;
 wire LO_VTUNE;
 wire LO_CP;
 wire LO_OBS;
 wire PRE_CONV_CK;
 wire PREF;
 wire CDR_REF;
 wire CDR_HOLD;
 wire CDR_VCTRL;
 wire LO_OBS_D;
 wire RAIL_conv = VDD, RAIL_debug = VDD, RAIL_lo = VDD, RAIL_lod = VDD, RAIL_pll = VDD, RAIL_rf_rx = VDD, RAIL_rf_tx = VDD, VDD_LO = VDD, VREG_CDR = VDD, VREG_TX = VDD;
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
 wire p_core_bias__ON_rf = island_on[1];
 wire p_core_bias__ON_pll = island_on[2];
 wire p_core_bias__ON_conv = island_on[4];
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
 wire p_core_bias__C_core_refchain_dist_en_rf = c_bias_dist_en_rf;
 wire p_core_bias__C_core_refchain_dist_en_conv = c_bias_dist_en_conv;
 wire p_core_bias__C_core_refchain_dist_en_pll = c_bias_dist_en_pll;
 wire p_core_bias__C_core_refchain_dist_en_debug = c_bias_dist_en_debug;
 wire p_core_bias__EN_lna = c_lna_en;
 wire p_core_bias__EN_rxmix_i = c_rxmix_i_en;
 wire p_core_bias__EN_rxmix_q = c_rxmix_q_en;
 wire p_core_bias__EN_bbfilter_i = c_bbfilter_i_en;
 wire p_core_bias__EN_bbfilter_q = c_bbfilter_q_en;
 wire p_core_bias__EN_txmix_i = c_txmix_i_en;
 wire p_core_bias__EN_txmix_q = c_txmix_q_en;
 wire p_core_bias__EN_rfdriver = c_rfdriver_en;
 wire p_core_bias__EN_adc_i = c_adc_i_en;
 wire p_core_bias__EN_adc_q = c_adc_q_en;
 wire p_core_bias__EN_dac_i = c_dac_i_en;
 wire p_core_bias__EN_dac_q = c_dac_q_en;
 wire p_core_bias__EN_refbuf = c_refbuf_en;
 wire p_core_bias__EN_pll_ring_tx = c_pll_tx_en;
 wire p_core_bias__EN_pll_ring_rx = c_pll_cdr_en;
 wire p_core_bias__EN_cdr = c_cdr_en;
 wire p_core_bias__EN_qvco = c_qvco_en;
 wire p_core_bias__EN_lo_pfdcp = c_lo_pfdcp_en;
 wire p_core_bias__EN_bb_tap_i = c_bb_tap_i_bias_en;
 wire p_core_bias__EN_bb_tap_q = c_bb_tap_q_bias_en;
 wire p_isw_rf_tx__EN = island_en[1];
 assign s_pg_rf_tx = island_en[1];
 wire p_isw_debug__EN = island_en[5];
 assign s_pg_debug = island_en[5];
 wire p_isw_lod__EN = island_en[1];
 assign s_pg_lod = island_en[1];
 wire p_isw_rf_rx__EN = island_en[1];
 assign s_pg_rf_rx = island_en[1];
 wire p_isw_conv__EN = island_en[4];
 assign s_pg_conv = island_en[4];
 wire p_isw_lo__EN = island_en[1];
 assign s_pg_lo = island_en[1];
 wire p_lna__en = c_lna_en;
 wire p_lna__gain_lo = c_lna_gain_lo;
 wire p_lna__byp = c_lna_byp;
 wire p_lna__ct0 = c_lna_ct[0];
 wire p_lna__ct1 = c_lna_ct[1];
 wire p_lna__ct2 = c_lna_ct[2];
 wire p_lna__ct3 = c_lna_ct[3];
 wire p_lna__se = c_lna_se;
 wire p_lna__rt = c_lna_rt;
 wire p_lna__att0 = c_lna_att[0];
 wire p_lna__att1 = c_lna_att[1];
 wire p_lna__att2 = c_lna_att[2];
 wire p_lna__att3 = c_lna_att[3];
 wire p_lna__att4 = c_lna_att[4];
 wire p_lna__lobias = c_lna_lobias;
 wire p_lna__island_off = island_off[1];
 wire p_rxmix_i__en = c_rxmix_i_en;
 wire p_rxmix_i__ofs0 = c_rxmix_i_ofs[0];
 wire p_rxmix_i__ofs1 = c_rxmix_i_ofs[1];
 wire p_rxmix_i__ofs2 = c_rxmix_i_ofs[2];
 wire p_rxmix_i__ofs3 = c_rxmix_i_ofs[3];
 wire p_rxmix_i__ofs4 = c_rxmix_i_ofs[4];
 wire p_rxmix_i__ofs_sign = c_rxmix_i_ofs[5];
 wire p_rxmix_i__island_off = island_off[1];
 wire p_rxmix_i__hib = c_rxmix_hib;
 wire p_rxmix_q__en = c_rxmix_q_en;
 wire p_rxmix_q__ofs0 = c_rxmix_q_ofs[0];
 wire p_rxmix_q__ofs1 = c_rxmix_q_ofs[1];
 wire p_rxmix_q__ofs2 = c_rxmix_q_ofs[2];
 wire p_rxmix_q__ofs3 = c_rxmix_q_ofs[3];
 wire p_rxmix_q__ofs4 = c_rxmix_q_ofs[4];
 wire p_rxmix_q__ofs_sign = c_rxmix_q_ofs[5];
 wire p_rxmix_q__island_off = island_off[1];
 wire p_rxmix_q__hib = c_rxmix_hib;
 wire p_bbfilter_i__en = c_bbfilter_i_en;
 wire p_bbfilter_i__dir_tx = c_bbfilter_dir_tx;
 wire p_bbfilter_i__inj = c_bbfilter_inj;
 wire p_bbfilter_i__rx_direct = c_bbfilter_rx_direct;
 wire p_bbfilter_i__byp_s1 = c_bbfilter_byp_s1;
 wire p_bbfilter_i__byp_s23 = c_bbfilter_byp_s23;
 wire p_bbfilter_i__obs_sel0 = c_bbfilter_obs_sel[0];
 wire p_bbfilter_i__obs_sel1 = c_bbfilter_obs_sel[1];
 wire p_bbfilter_i__bw0 = c_bbfilter_i_cut[3];
 wire p_bbfilter_i__bw1 = c_bbfilter_i_cut[4];
 wire p_bbfilter_i__bw2 = c_bbfilter_i_cut[5];
 wire p_bbfilter_i__bw3 = c_bbfilter_i_cut[6];
 wire p_bbfilter_i__fc_fine0 = c_bbfilter_i_cut[0];
 wire p_bbfilter_i__fc_fine1 = c_bbfilter_i_cut[1];
 wire p_bbfilter_i__fc_fine2 = c_bbfilter_i_cut[2];
 wire p_bbfilter_i__gain0 = c_bbfilter_i_gain[0];
 wire p_bbfilter_i__gain1 = c_bbfilter_i_gain[1];
 wire p_bbfilter_i__gain2 = c_bbfilter_i_gain[2];
 wire p_bbfilter_i__gain3 = c_bbfilter_i_gain[3];
 wire p_bbfilter_i__gain4 = c_bbfilter_i_gain[4];
 wire p_bbfilter_i__gain5 = c_bbfilter_i_gain[5];
 wire p_bbfilter_i__gainc0 = c_bbfilter_i_gainc[0];
 wire p_bbfilter_i__gainc1 = c_bbfilter_i_gainc[1];
 wire p_bbfilter_i__qt0 = c_bbfilter_i_qt[0];
 wire p_bbfilter_i__qt1 = c_bbfilter_i_qt[1];
 wire p_bbfilter_i__qt2 = c_bbfilter_i_qt[2];
 wire p_bbfilter_i__qt3 = c_bbfilter_i_qt[3];
 wire p_bbfilter_i__dcf0 = c_bbfilter_i_dcf[0];
 wire p_bbfilter_i__dcf1 = c_bbfilter_i_dcf[1];
 wire p_bbfilter_i__dcf2 = c_bbfilter_i_dcf[2];
 wire p_bbfilter_i__dcf3 = c_bbfilter_i_dcf[3];
 wire p_bbfilter_i__dcf4 = c_bbfilter_i_dcf[4];
 wire p_bbfilter_i__dcf5 = c_bbfilter_i_dcf[5];
 wire p_bbfilter_i__dcf6 = c_bbfilter_i_dcf[6];
 wire p_bbfilter_i__dcf7 = c_bbfilter_i_dcf[7];
 wire p_bbfilter_i__dcf_sign = c_bbfilter_i_dcf[8];
 wire p_bbfilter_i__island_off = island_off[1];
 wire p_bbfilter_q__en = c_bbfilter_q_en;
 wire p_bbfilter_q__dir_tx = c_bbfilter_dir_tx;
 wire p_bbfilter_q__inj = c_bbfilter_inj;
 wire p_bbfilter_q__rx_direct = c_bbfilter_rx_direct;
 wire p_bbfilter_q__byp_s1 = c_bbfilter_byp_s1;
 wire p_bbfilter_q__byp_s23 = c_bbfilter_byp_s23;
 wire p_bbfilter_q__obs_sel0 = c_bbfilter_obs_sel[0];
 wire p_bbfilter_q__obs_sel1 = c_bbfilter_obs_sel[1];
 wire p_bbfilter_q__bw0 = c_bbfilter_q_cut[3];
 wire p_bbfilter_q__bw1 = c_bbfilter_q_cut[4];
 wire p_bbfilter_q__bw2 = c_bbfilter_q_cut[5];
 wire p_bbfilter_q__bw3 = c_bbfilter_q_cut[6];
 wire p_bbfilter_q__fc_fine0 = c_bbfilter_q_cut[0];
 wire p_bbfilter_q__fc_fine1 = c_bbfilter_q_cut[1];
 wire p_bbfilter_q__fc_fine2 = c_bbfilter_q_cut[2];
 wire p_bbfilter_q__gain0 = c_bbfilter_q_gain[0];
 wire p_bbfilter_q__gain1 = c_bbfilter_q_gain[1];
 wire p_bbfilter_q__gain2 = c_bbfilter_q_gain[2];
 wire p_bbfilter_q__gain3 = c_bbfilter_q_gain[3];
 wire p_bbfilter_q__gain4 = c_bbfilter_q_gain[4];
 wire p_bbfilter_q__gain5 = c_bbfilter_q_gain[5];
 wire p_bbfilter_q__gainc0 = c_bbfilter_q_gainc[0];
 wire p_bbfilter_q__gainc1 = c_bbfilter_q_gainc[1];
 wire p_bbfilter_q__qt0 = c_bbfilter_q_qt[0];
 wire p_bbfilter_q__qt1 = c_bbfilter_q_qt[1];
 wire p_bbfilter_q__qt2 = c_bbfilter_q_qt[2];
 wire p_bbfilter_q__qt3 = c_bbfilter_q_qt[3];
 wire p_bbfilter_q__dcf0 = c_bbfilter_q_dcf[0];
 wire p_bbfilter_q__dcf1 = c_bbfilter_q_dcf[1];
 wire p_bbfilter_q__dcf2 = c_bbfilter_q_dcf[2];
 wire p_bbfilter_q__dcf3 = c_bbfilter_q_dcf[3];
 wire p_bbfilter_q__dcf4 = c_bbfilter_q_dcf[4];
 wire p_bbfilter_q__dcf5 = c_bbfilter_q_dcf[5];
 wire p_bbfilter_q__dcf6 = c_bbfilter_q_dcf[6];
 wire p_bbfilter_q__dcf7 = c_bbfilter_q_dcf[7];
 wire p_bbfilter_q__dcf_sign = c_bbfilter_q_dcf[8];
 wire p_bbfilter_q__island_off = island_off[1];
 wire p_bb_tap_i__obs_en = c_bb_tap_obs_en;
 wire p_bb_tap_i__inj_en = c_bb_tap_inj_en;
 wire p_bb_tap_i__island_off = island_off[5];
 wire p_bb_tap_q__obs_en = c_bb_tap_obs_en;
 wire p_bb_tap_q__inj_en = c_bb_tap_inj_en;
 wire p_bb_tap_q__island_off = island_off[5];
 wire p_adc_i__CLK = CONV_CLK_C;
 wire p_adc_i__ACQ0 = c_adc_acq[0];
 wire p_adc_i__ACQ1 = c_adc_acq[1];
 wire p_adc_i__EN = c_adc_i_en;
 wire p_adc_i__ILEN = c_adc_ilen;
 wire p_adc_i__TEST0 = c_adc_i_test[0];
 wire p_adc_i__TEST1 = c_adc_i_test[1];
 assign ADCI_CODE[0] = 1'b0;
 assign ADCI_CODE[1] = 1'b0;
 assign ADCI_CODE[2] = 1'b0;
 assign ADCI_CODE[3] = 1'b0;
 assign ADCI_CODE[4] = 1'b0;
 assign ADCI_CODE[5] = 1'b0;
 assign ADCI_CODE[6] = 1'b0;
 assign ADCI_CODE[7] = 1'b0;
 assign ADCI_CODE[8] = 1'b0;
 assign ADCI_CODE[9] = 1'b0;
 assign ADCI_DONE = 1'b0;
 assign ADCI_OVL = 1'b0;
 assign ADCI_CODEB[0] = 1'b0;
 assign ADCI_CODEB[1] = 1'b0;
 assign ADCI_CODEB[2] = 1'b0;
 assign ADCI_CODEB[3] = 1'b0;
 assign ADCI_CODEB[4] = 1'b0;
 assign ADCI_CODEB[5] = 1'b0;
 assign ADCI_CODEB[6] = 1'b0;
 assign ADCI_CODEB[7] = 1'b0;
 assign ADCI_CODEB[8] = 1'b0;
 assign ADCI_CODEB[9] = 1'b0;
 assign ADCI_DONEB = 1'b0;
 assign ADCI_OVLB = 1'b0;
 assign ADCI_PH = 1'b0;
 wire p_adc_q__CLK = CONV_CLK_C;
 wire p_adc_q__ACQ0 = c_adc_acq[0];
 wire p_adc_q__ACQ1 = c_adc_acq[1];
 wire p_adc_q__EN = c_adc_q_en;
 wire p_adc_q__ILEN = c_adc_ilen;
 wire p_adc_q__TEST0 = c_adc_q_test[0];
 wire p_adc_q__TEST1 = c_adc_q_test[1];
 assign ADCQ_CODE[0] = 1'b0;
 assign ADCQ_CODE[1] = 1'b0;
 assign ADCQ_CODE[2] = 1'b0;
 assign ADCQ_CODE[3] = 1'b0;
 assign ADCQ_CODE[4] = 1'b0;
 assign ADCQ_CODE[5] = 1'b0;
 assign ADCQ_CODE[6] = 1'b0;
 assign ADCQ_CODE[7] = 1'b0;
 assign ADCQ_CODE[8] = 1'b0;
 assign ADCQ_CODE[9] = 1'b0;
 assign ADCQ_DONE = 1'b0;
 assign ADCQ_OVL = 1'b0;
 assign ADCQ_CODEB[0] = 1'b0;
 assign ADCQ_CODEB[1] = 1'b0;
 assign ADCQ_CODEB[2] = 1'b0;
 assign ADCQ_CODEB[3] = 1'b0;
 assign ADCQ_CODEB[4] = 1'b0;
 assign ADCQ_CODEB[5] = 1'b0;
 assign ADCQ_CODEB[6] = 1'b0;
 assign ADCQ_CODEB[7] = 1'b0;
 assign ADCQ_CODEB[8] = 1'b0;
 assign ADCQ_CODEB[9] = 1'b0;
 assign ADCQ_DONEB = 1'b0;
 assign ADCQ_OVLB = 1'b0;
 assign ADCQ_PH = 1'b0;
 wire p_iso_conv_clk__A = CONV_CLK;
 wire p_iso_conv_clk__ISO = island_off[2];
 assign CONV_CLK_C = CONV_CLK & ~island_off[2];
 wire p_dac_i__CLK = rf_tx_clk_out;
 wire p_dac_i__EN = c_dac_i_en;
 wire p_dac_i__HOLD_ZERO = c_dac_i_hold_zero;
 wire p_dac_i__CODE0 = rf_tx_sample[2];
 wire p_dac_i__CODE1 = rf_tx_sample[3];
 wire p_dac_i__CODE2 = rf_tx_sample[4];
 wire p_dac_i__CODE3 = rf_tx_sample[5];
 wire p_dac_i__CODE4 = rf_tx_sample[6];
 wire p_dac_i__CODE5 = rf_tx_sample[7];
 wire p_dac_i__CODE6 = rf_tx_sample[8];
 wire p_dac_i__CODE7 = rf_tx_sample[9];
 wire p_dac_i__CODE8 = rf_tx_sample[10];
 wire p_dac_i__CODE9 = rf_tx_sample[11];
 wire p_dac_q__CLK = rf_tx_clk_out;
 wire p_dac_q__EN = c_dac_q_en;
 wire p_dac_q__HOLD_ZERO = c_dac_q_hold_zero;
 wire p_dac_q__CODE0 = rf_tx_sample[14];
 wire p_dac_q__CODE1 = rf_tx_sample[15];
 wire p_dac_q__CODE2 = rf_tx_sample[16];
 wire p_dac_q__CODE3 = rf_tx_sample[17];
 wire p_dac_q__CODE4 = rf_tx_sample[18];
 wire p_dac_q__CODE5 = rf_tx_sample[19];
 wire p_dac_q__CODE6 = rf_tx_sample[20];
 wire p_dac_q__CODE7 = rf_tx_sample[21];
 wire p_dac_q__CODE8 = rf_tx_sample[22];
 wire p_dac_q__CODE9 = rf_tx_sample[23];
 wire p_refbuf__EN = c_refbuf_en;
 wire p_refbuf__OVR = c_refbuf_ovr;
 assign REFBUF_READY = 1'b0;
 wire p_iso_rf_rx_clk__A = CONV_CLK;
 wire p_iso_rf_rx_clk__ISO = island_off[2];
 assign rf_rx_clk = CONV_CLK & ~island_off[2];
 wire p_txmix_i__en = c_txmix_i_en;
 wire p_txmix_i__sel_dac = c_txmix_sel_dac;
 wire p_txmix_i__sat = c_txmix_sat;
 wire p_txmix_q__en = c_txmix_q_en;
 wire p_txmix_q__sel_dac = c_txmix_sel_dac;
 wire p_txmix_q__sat = c_txmix_sat;
 wire p_txsum__en = c_txsum_en;
 wire p_rfdriver__en = c_rfdriver_en;
 wire p_rfdriver__mute = c_rfdriver_mute;
 wire p_rfdriver__bypass = c_rfdriver_bypass;
 wire p_rfdriver__g0 = c_rfdriver_g[0];
 wire p_rfdriver__g1 = c_rfdriver_g[1];
 wire p_rfdriver__g2 = c_rfdriver_g[2];
 wire p_rfdriver__g3 = c_rfdriver_g[3];
 wire p_rfdriver__se = c_rfdriver_se;
 wire p_lo_ext__EXT = c_lo_ext;
 wire p_lo_ext__INT = c_lo_int;
 wire p_lo_ext__CMLSEL = c_lo_cmlsel;
 wire p_lo_vreg__EN = c_lo_vreg_en;
 wire p_qvco__EN = c_qvco_en;
 wire p_qvco__CMLSEL = c_lo_cmlsel;
 wire p_qvco__BAND0 = c_qvco_band[0];
 wire p_qvco__BAND1 = c_qvco_band[1];
 wire p_qvco__BAND2 = c_qvco_band[2];
 wire p_qvco__BAND3 = c_qvco_band[3];
 wire p_qvco__ATB_EN = c_qvco_atb_en;
 wire p_lo_mmd__EN = c_lo_mmd_en;
 wire p_lo_mmd__N0 = c_lo_mmd_n[0];
 wire p_lo_mmd__N1 = c_lo_mmd_n[1];
 wire p_lo_mmd__N2 = c_lo_mmd_n[2];
 wire p_lo_mmd__N3 = c_lo_mmd_n[3];
 wire p_lo_mmd__N4 = c_lo_mmd_n[4];
 wire p_lo_mmd__N5 = c_lo_mmd_n[5];
 assign LO_FB = 1'b0;
 wire p_lo_mmd_qdum__EN = c_lo_mmd_en;
 wire p_lo_pfdcp__REF = ref_clk;
 wire p_lo_pfdcp__FB = LO_FB;
 wire p_lo_pfdcp__EN = c_lo_pfdcp_en;
 wire p_lo_pfdcp__PRE = c_lo_pre;
 wire p_lo_pfdcp__ICP0 = c_lo_icp[0];
 wire p_lo_pfdcp__ICP1 = c_lo_icp[1];
 wire p_lo_obs__EN = c_lo_obs_en;
 assign LO_OBS = 1'b0;
 wire p_lo_obs_q__EN = VSS;
 wire p_clockmux__PLLW = TXPH[0];
 wire p_clockmux__REF = ref_clk;
 wire p_clockmux__AUX = AUX_CK_P;
 wire p_clockmux__WCK = AUX_CK_P;
 wire p_clockmux__H2D = h2d_clk;
 wire p_clockmux__WSI = CDRPH[0];
 wire p_clockmux__CONV_INT = PRE_CONV_CK;
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
 wire p_clockmux__CS_INT = c_clockmux_cs[0];
 wire p_clockmux__CS_REF = c_clockmux_cs[1];
 wire p_clockmux__CS_AUX = c_clockmux_cs[2];
 wire p_clockmux__CS_HF = c_clockmux_cs[3];
 wire p_clockmux__HS_INT = c_clockmux_hs[0];
 wire p_clockmux__HS_HF = c_clockmux_hs[1];
 assign PREF = 1'b0;
 assign WIRE_CK = 1'b0;
 assign WSMP_CK = 1'b0;
 assign CONV_CLK = 1'b0;
 assign HOST_CLK = 1'b0;
 wire p_prescale_conv__CK_IN = WIRE_CK;
 wire p_prescale_conv__EN = c_prescale_conv_en;
 wire p_prescale_conv__D2 = c_prescale_conv_d[0];
 wire p_prescale_conv__D4 = c_prescale_conv_d[1];
 wire p_prescale_conv__D8 = c_prescale_conv_d[2];
 wire p_prescale_conv__D16 = c_prescale_conv_d[3];
 assign PRE_CONV_CK = 1'b0;
 wire p_pll_tx__REF = PREF;
 wire p_pll_tx__EN = c_pll_tx_en;
 wire p_pll_tx__N4 = c_pll_tx_n4;
 wire p_pll_tx__N8 = c_pll_tx_n8;
 wire p_pll_tx__HOLD = VSS;
 assign TXPH[0] = 1'b0;
 assign TXPH[1] = 1'b0;
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
 assign PLL_CDR_LOCK = 1'b0;
 assign PLL_CDR_FBCK = 1'b0;
 wire p_pll_cdr__KP0 = c_pll_cdr_kp[0];
 wire p_pll_cdr__KP1 = c_pll_cdr_kp[1];
 wire p_pll_cdr__KP2 = c_pll_cdr_kp[2];
 wire p_pll_cdr__FU0 = VSS;
 wire p_pll_cdr__FU1 = VSS;
 wire p_pll_cdr__FU2 = VSS;
 wire p_pll_cdr__FU3 = VSS;
 wire p_pll_cdr__FD0 = VSS;
 wire p_pll_cdr__FD1 = VSS;
 wire p_pll_cdr__FD2 = VSS;
 wire p_pll_cdr__FD3 = VSS;
 wire p_pll_cdr__BAND = c_pll_cdr_band;
 wire p_cdr__cdr_en = c_cdr_en;
 wire p_cdr__pfd_mode = c_cdr_pfd_mode;
 wire p_cdr__ref_sel = c_cdr_ref_sel;
 wire p_cdr__g0 = c_cdr_g[0];
 wire p_cdr__g1 = c_cdr_g[1];
 wire p_cdr__g2 = c_cdr_g[2];
 wire p_cdr__UP0 = VSS;
 wire p_cdr__UP1 = VSS;
 wire p_cdr__UP2 = VSS;
 wire p_cdr__UP3 = VSS;
 wire p_cdr__DN0 = VSS;
 wire p_cdr__DN1 = VSS;
 wire p_cdr__DN2 = VSS;
 wire p_cdr__DN3 = VSS;
 wire p_cdr__FUP = VSS;
 wire p_cdr__FDN = VSS;
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
 wire p_iso_lo_obs__A = LO_OBS;
 wire p_iso_lo_obs__ISO = island_off[1];
 assign LO_OBS_D = LO_OBS & ~island_off[1];
 wire p_clk_obs__IN0 = VSS;
 wire p_clk_obs__IN1 = LO_OBS_D;
 wire p_clk_obs__IN2 = OBS4_wire;
 wire p_clk_obs__IN3 = OBS4_wsmp;
 wire p_clk_obs__IN4 = rf_rx_clk;
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
 wire p_clk_obs__IN15A = VSS;
 wire p_clk_obs__IN15B = VSS;
 wire p_clk_obs__IN15C = VSS;
 wire p_clk_obs__S0 = c_clk_obs_s[0];
 wire p_clk_obs__S1 = c_clk_obs_s[1];
 wire p_clk_obs__S2 = c_clk_obs_s[2];
 wire p_clk_obs__S3 = c_clk_obs_s[3];
 wire p_clk_obs__N0 = c_clk_obs_n[0];
 wire p_clk_obs__N1 = c_clk_obs_n[1];
 wire p_clk_obs__N2 = c_clk_obs_n[2];
 wire p_clk_obs__EN = c_clk_obs_en;
 assign CLK_OBS_DBG = 1'b0;
 wire p_atb0_leaf14__SEL = atb0_sw[13];
 wire p_atb0_leaf35__SEL = atb0_sw[34];
 wire p_atb0_leaf36__SEL = atb0_sw[35];
 wire p_atb1_leaf8__SEL = atb1_sw[7];
 wire p_atb1_leaf11__SEL = atb1_sw[10];
 wire p_atb1_leaf14__SEL = atb1_sw[13];
 wire p_atb1_leaf15__SEL = atb1_sw[14];
 wire p_atb1_leaf16__SEL = atb1_sw[15];
 wire p_atb1_leaf17__SEL = atb1_sw[16];
 wire p_atb1_leaf18__SEL = atb1_sw[17];
 wire p_atb1_leaf19__SEL = atb1_sw[18];
 wire p_atb1_leaf20__SEL = atb1_sw[19];
 wire p_atb1_leaf21__SEL = atb1_sw[20];
 wire p_atb1_leaf33__SEL = atb1_sw[32];
 wire p_atb1_leaf35__SEL = atb1_sw[34];
 wire p_atb1_leaf36__SEL = atb1_sw[35];
 wire p_atb1_leaf38__SEL = atb1_sw[37];
 wire p_atb1_leaf39__SEL = atb1_sw[38];
endmodule
