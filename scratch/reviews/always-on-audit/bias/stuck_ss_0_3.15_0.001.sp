* audit deck
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice ss
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice res_ss
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice mimcap_ss
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice diode_ss
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice bjt_ss
.temp 0
.option gmin=1e-14 reltol=1e-3 method=gear

.include /work/bias/pt_core_bias.spice
VDD VDD 0 pwl(0 0 0.001 3.15)
ERAIL_rf RAIL_rf 0 VDD 0 1
ERAIL_conv RAIL_conv 0 VDD 0 1
ERAIL_pll RAIL_pll 0 VDD 0 1
ERAIL_wired RAIL_wired 0 VDD 0 1
ERAIL_debug RAIL_debug 0 VDD 0 1
EON_rf ON_rf 0 VDD 0 1
EON_conv ON_conv 0 VDD 0 1
EON_pll ON_pll 0 VDD 0 1
EON_wired ON_wired 0 VDD 0 1
EON_debug ON_debug 0 VDD 0 1
EC_core_biasgen_ena C_core_biasgen_ena 0 VDD 0 1
EC_core_biasgen_ref_sel_vbg C_core_biasgen_ref_sel_vbg 0 VDD 0 1
EC_core_biasgen_ref_sel_coarse C_core_biasgen_ref_sel_coarse 0 VDD 0 1
VC_core_biasgen_ref_sel_fine C_core_biasgen_ref_sel_fine 0 0
VC_core_biasgen_idac2_source_0 C_core_biasgen_idac2_source_0 0 0
EC_core_biasgen_idac2_source_1 C_core_biasgen_idac2_source_1 0 VDD 0 1
VC_core_biasgen_idac2_source_2 C_core_biasgen_idac2_source_2 0 0
EC_core_biasgen_idac2_source_3 C_core_biasgen_idac2_source_3 0 VDD 0 1
VC_core_biasgen_idac2_source_4 C_core_biasgen_idac2_source_4 0 0
VC_core_biasgen_idac1_source_0 C_core_biasgen_idac1_source_0 0 0
VC_core_biasgen_idac1_source_1 C_core_biasgen_idac1_source_1 0 0
VC_core_biasgen_idac1_source_2 C_core_biasgen_idac1_source_2 0 0
VC_core_biasgen_idac1_source_3 C_core_biasgen_idac1_source_3 0 0
VC_core_biasgen_idac1_source_4 C_core_biasgen_idac1_source_4 0 0
EC_core_biasgen_bandgap_sink1_0 C_core_biasgen_bandgap_sink1_0 0 VDD 0 1
EC_core_biasgen_bandgap_sink1_1 C_core_biasgen_bandgap_sink1_1 0 VDD 0 1
EC_core_biasgen_bandgap_sink1_2 C_core_biasgen_bandgap_sink1_2 0 VDD 0 1
EC_core_biasgen_bandgap_sink2_0 C_core_biasgen_bandgap_sink2_0 0 VDD 0 1
EC_core_biasgen_bandgap_sink2_1 C_core_biasgen_bandgap_sink2_1 0 VDD 0 1
VC_core_biasgen_voltgen_source_0 C_core_biasgen_voltgen_source_0 0 0
VC_core_biasgen_voltgen_source_1 C_core_biasgen_voltgen_source_1 0 0
VC_core_biasgen_voltgen_source_2 C_core_biasgen_voltgen_source_2 0 0
VC_core_biasgen_voltgen_source_3 C_core_biasgen_voltgen_source_3 0 0
VC_core_biasgen_voltgen_source_4 C_core_biasgen_voltgen_source_4 0 0
VC_core_biasgen_voltgen_sink1_0 C_core_biasgen_voltgen_sink1_0 0 0
VC_core_biasgen_voltgen_sink1_1 C_core_biasgen_voltgen_sink1_1 0 0
VC_core_biasgen_voltgen_sink1_2 C_core_biasgen_voltgen_sink1_2 0 0
VC_core_biasgen_voltgen_sink2_0 C_core_biasgen_voltgen_sink2_0 0 0
VC_core_biasgen_voltgen_sink2_1 C_core_biasgen_voltgen_sink2_1 0 0
VC_core_biasgen_voltgen_sink2_2 C_core_biasgen_voltgen_sink2_2 0 0
EC_core_refchain_bgap_ena C_core_refchain_bgap_ena 0 VDD 0 1
EC_core_refchain_bgap_trim_0 C_core_refchain_bgap_trim_0 0 VDD 0 1
EC_core_refchain_bgap_trim_1 C_core_refchain_bgap_trim_1 0 VDD 0 1
EC_core_refchain_bgap_trim_2 C_core_refchain_bgap_trim_2 0 VDD 0 1
EC_core_refchain_bgap_trim_3 C_core_refchain_bgap_trim_3 0 VDD 0 1
EC_core_refchain_bgap_trim_4 C_core_refchain_bgap_trim_4 0 VDD 0 1
EC_core_refchain_bgap_trim_5 C_core_refchain_bgap_trim_5 0 VDD 0 1
EC_core_refchain_bgap_trim_6 C_core_refchain_bgap_trim_6 0 VDD 0 1
EC_core_refchain_bgap_trim_7 C_core_refchain_bgap_trim_7 0 VDD 0 1
VC_core_refchain_bgap_trim_8 C_core_refchain_bgap_trim_8 0 0
VC_core_refchain_bgap_trim_9 C_core_refchain_bgap_trim_9 0 0
VC_core_refchain_bgap_trim_10 C_core_refchain_bgap_trim_10 0 0
VC_core_refchain_bgap_trim_11 C_core_refchain_bgap_trim_11 0 0
VC_core_refchain_bgap_trim_12 C_core_refchain_bgap_trim_12 0 0
VC_core_refchain_bgap_trim_13 C_core_refchain_bgap_trim_13 0 0
VC_core_refchain_bgap_trim_14 C_core_refchain_bgap_trim_14 0 0
VC_core_refchain_bgap_trim_15 C_core_refchain_bgap_trim_15 0 0
EC_core_refchain_dist_en_rf C_core_refchain_dist_en_rf 0 VDD 0 1
EC_core_refchain_dist_en_conv C_core_refchain_dist_en_conv 0 VDD 0 1
EC_core_refchain_dist_en_pll C_core_refchain_dist_en_pll 0 VDD 0 1
EC_core_refchain_dist_en_wire C_core_refchain_dist_en_wire 0 VDD 0 1
EC_core_refchain_dist_en_debug C_core_refchain_dist_en_debug 0 VDD 0 1
EEN_lna EN_lna 0 VDD 0 1
EEN_rxmix_i EN_rxmix_i 0 VDD 0 1
EEN_rxmix_q EN_rxmix_q 0 VDD 0 1
EEN_bbfilter_i EN_bbfilter_i 0 VDD 0 1
EEN_bbfilter_q EN_bbfilter_q 0 VDD 0 1
EEN_txmix_i EN_txmix_i 0 VDD 0 1
EEN_txmix_q EN_txmix_q 0 VDD 0 1
EEN_rfdriver EN_rfdriver 0 VDD 0 1
EEN_adc_i EN_adc_i 0 VDD 0 1
EEN_adc_q EN_adc_q 0 VDD 0 1
EEN_dac_i EN_dac_i 0 VDD 0 1
EEN_dac_q EN_dac_q 0 VDD 0 1
EEN_refbuf EN_refbuf 0 VDD 0 1
EEN_pll_ring_tx EN_pll_ring_tx 0 VDD 0 1
EEN_pll_ring_rx EN_pll_ring_rx 0 VDD 0 1
EEN_pll_ring_host EN_pll_ring_host 0 VDD 0 1
EEN_ctle EN_ctle 0 VDD 0 1
EEN_detect EN_detect 0 VDD 0 1
EEN_wiredtx EN_wiredtx 0 VDD 0 1
EEN_bb_tap_i EN_bb_tap_i 0 VDD 0 1
EEN_bb_tap_q EN_bb_tap_q 0 VDD 0 1
EEN_bb_tap_wmon EN_bb_tap_wmon 0 VDD 0 1
X1 VDD 0 RAIL_rf RAIL_conv RAIL_pll RAIL_wired RAIL_debug ON_rf ON_conv ON_pll ON_wired ON_debug C_core_biasgen_ena C_core_biasgen_ref_sel_vbg C_core_biasgen_ref_sel_coarse C_core_biasgen_ref_sel_fine C_core_biasgen_idac2_source_0 C_core_biasgen_idac2_source_1 C_core_biasgen_idac2_source_2 C_core_biasgen_idac2_source_3 C_core_biasgen_idac2_source_4 C_core_biasgen_idac1_source_0 C_core_biasgen_idac1_source_1 C_core_biasgen_idac1_source_2 C_core_biasgen_idac1_source_3 C_core_biasgen_idac1_source_4 C_core_biasgen_bandgap_sink1_0 C_core_biasgen_bandgap_sink1_1 C_core_biasgen_bandgap_sink1_2 C_core_biasgen_bandgap_sink2_0 C_core_biasgen_bandgap_sink2_1 C_core_biasgen_voltgen_source_0 C_core_biasgen_voltgen_source_1 C_core_biasgen_voltgen_source_2 C_core_biasgen_voltgen_source_3 C_core_biasgen_voltgen_source_4 C_core_biasgen_voltgen_sink1_0 C_core_biasgen_voltgen_sink1_1 C_core_biasgen_voltgen_sink1_2 C_core_biasgen_voltgen_sink2_0 C_core_biasgen_voltgen_sink2_1 C_core_biasgen_voltgen_sink2_2 C_core_refchain_bgap_ena C_core_refchain_bgap_trim_0 C_core_refchain_bgap_trim_1 C_core_refchain_bgap_trim_2 C_core_refchain_bgap_trim_3 C_core_refchain_bgap_trim_4 C_core_refchain_bgap_trim_5 C_core_refchain_bgap_trim_6 C_core_refchain_bgap_trim_7 C_core_refchain_bgap_trim_8 C_core_refchain_bgap_trim_9 C_core_refchain_bgap_trim_10 C_core_refchain_bgap_trim_11 C_core_refchain_bgap_trim_12 C_core_refchain_bgap_trim_13 C_core_refchain_bgap_trim_14 C_core_refchain_bgap_trim_15 C_core_refchain_dist_en_rf C_core_refchain_dist_en_conv C_core_refchain_dist_en_pll C_core_refchain_dist_en_wire C_core_refchain_dist_en_debug EN_lna BIAS_lna EN_rxmix_i BIAS_rxmix_i EN_rxmix_q BIAS_rxmix_q EN_bbfilter_i BIAS_bbfilter_i EN_bbfilter_q BIAS_bbfilter_q EN_txmix_i BIAS_txmix_i EN_txmix_q BIAS_txmix_q EN_rfdriver BIAS_rfdriver EN_adc_i BIAS_adc_i EN_adc_q BIAS_adc_q EN_dac_i BIAS_dac_i EN_dac_q BIAS_dac_q EN_refbuf BIAS_refbuf EN_pll_ring_tx BIAS_pll_ring_tx EN_pll_ring_rx BIAS_pll_ring_rx EN_pll_ring_host BIAS_pll_ring_host BIAS_lc_vco_reserved EN_ctle BIAS_ctle EN_detect BIAS_detect EN_wiredtx BIAS_wiredtx EN_bb_tap_i BIAS_bb_tap_i EN_bb_tap_q BIAS_bb_tap_q EN_bb_tap_wmon BIAS_bb_tap_wmon ROOT_REF VREF0 VCM TRK_RF TRK_WIRE TRK_PLL TRK_CONV VBG TRK_DEBUG IDAC1 VGEN_SOURCE VGEN_SINK1 VGEN_SINK2 pt_core_bias
Vm_BIAS_lna BIAS_lna d_BIAS_lna 0
XN_BIAS_lna d_BIAS_lna d_BIAS_lna 0 0 nfet_03v3 w=4u l=2u
Vm_BIAS_rxmix_i BIAS_rxmix_i d_BIAS_rxmix_i 0
XN_BIAS_rxmix_i d_BIAS_rxmix_i d_BIAS_rxmix_i 0 0 nfet_03v3 w=4u l=2u
Vm_BIAS_rxmix_q BIAS_rxmix_q d_BIAS_rxmix_q 0
XN_BIAS_rxmix_q d_BIAS_rxmix_q d_BIAS_rxmix_q 0 0 nfet_03v3 w=4u l=2u
Vm_BIAS_bbfilter_i BIAS_bbfilter_i d_BIAS_bbfilter_i 0
XN_BIAS_bbfilter_i d_BIAS_bbfilter_i d_BIAS_bbfilter_i 0 0 nfet_03v3 w=4u l=2u
Vm_BIAS_bbfilter_q BIAS_bbfilter_q d_BIAS_bbfilter_q 0
XN_BIAS_bbfilter_q d_BIAS_bbfilter_q d_BIAS_bbfilter_q 0 0 nfet_03v3 w=4u l=2u
Vm_BIAS_txmix_i BIAS_txmix_i d_BIAS_txmix_i 0
XN_BIAS_txmix_i d_BIAS_txmix_i d_BIAS_txmix_i 0 0 nfet_03v3 w=4u l=2u
Vm_BIAS_txmix_q BIAS_txmix_q d_BIAS_txmix_q 0
XN_BIAS_txmix_q d_BIAS_txmix_q d_BIAS_txmix_q 0 0 nfet_03v3 w=4u l=2u
Vm_BIAS_rfdriver BIAS_rfdriver d_BIAS_rfdriver 0
XN_BIAS_rfdriver d_BIAS_rfdriver d_BIAS_rfdriver 0 0 nfet_03v3 w=4u l=2u
Vm_BIAS_adc_i BIAS_adc_i d_BIAS_adc_i 0
XN_BIAS_adc_i d_BIAS_adc_i d_BIAS_adc_i 0 0 nfet_03v3 w=4u l=2u
Vm_BIAS_adc_q BIAS_adc_q d_BIAS_adc_q 0
XN_BIAS_adc_q d_BIAS_adc_q d_BIAS_adc_q 0 0 nfet_03v3 w=4u l=2u
Vm_BIAS_dac_i BIAS_dac_i d_BIAS_dac_i 0
XN_BIAS_dac_i d_BIAS_dac_i d_BIAS_dac_i 0 0 nfet_03v3 w=4u l=2u
Vm_BIAS_dac_q BIAS_dac_q d_BIAS_dac_q 0
XN_BIAS_dac_q d_BIAS_dac_q d_BIAS_dac_q 0 0 nfet_03v3 w=4u l=2u
Vm_BIAS_refbuf BIAS_refbuf d_BIAS_refbuf 0
XN_BIAS_refbuf d_BIAS_refbuf d_BIAS_refbuf 0 0 nfet_03v3 w=4u l=2u
Vm_BIAS_pll_ring_tx BIAS_pll_ring_tx d_BIAS_pll_ring_tx 0
XN_BIAS_pll_ring_tx d_BIAS_pll_ring_tx d_BIAS_pll_ring_tx 0 0 nfet_03v3 w=4u l=2u
Vm_BIAS_pll_ring_rx BIAS_pll_ring_rx d_BIAS_pll_ring_rx 0
XN_BIAS_pll_ring_rx d_BIAS_pll_ring_rx d_BIAS_pll_ring_rx 0 0 nfet_03v3 w=4u l=2u
Vm_BIAS_pll_ring_host BIAS_pll_ring_host d_BIAS_pll_ring_host 0
XN_BIAS_pll_ring_host d_BIAS_pll_ring_host d_BIAS_pll_ring_host 0 0 nfet_03v3 w=4u l=2u
Vm_BIAS_lc_vco_reserved BIAS_lc_vco_reserved d_BIAS_lc_vco_reserved 0
XN_BIAS_lc_vco_reserved d_BIAS_lc_vco_reserved d_BIAS_lc_vco_reserved 0 0 nfet_03v3 w=4u l=2u
Vm_BIAS_ctle BIAS_ctle d_BIAS_ctle 0
XN_BIAS_ctle d_BIAS_ctle d_BIAS_ctle 0 0 nfet_03v3 w=4u l=2u
Vm_BIAS_detect BIAS_detect d_BIAS_detect 0
XN_BIAS_detect d_BIAS_detect d_BIAS_detect 0 0 nfet_03v3 w=4u l=2u
Vm_BIAS_wiredtx BIAS_wiredtx d_BIAS_wiredtx 0
XN_BIAS_wiredtx d_BIAS_wiredtx d_BIAS_wiredtx 0 0 nfet_03v3 w=4u l=2u
Vm_BIAS_bb_tap_i BIAS_bb_tap_i d_BIAS_bb_tap_i 0
XN_BIAS_bb_tap_i d_BIAS_bb_tap_i d_BIAS_bb_tap_i 0 0 nfet_03v3 w=4u l=2u
Vm_BIAS_bb_tap_q BIAS_bb_tap_q d_BIAS_bb_tap_q 0
XN_BIAS_bb_tap_q d_BIAS_bb_tap_q d_BIAS_bb_tap_q 0 0 nfet_03v3 w=4u l=2u
Vm_BIAS_bb_tap_wmon BIAS_bb_tap_wmon d_BIAS_bb_tap_wmon 0
XN_BIAS_bb_tap_wmon d_BIAS_bb_tap_wmon d_BIAS_bb_tap_wmon 0 0 nfet_03v3 w=4u l=2u
RIDAC1 IDAC1 0 1e9
RVGEN_SOURCE VGEN_SOURCE 0 1e9
RVGEN_SINK1 VGEN_SINK1 0 1e9
RVGEN_SINK2 VGEN_SINK2 0 1e9
.tran 1.2e-06 0.0024 0 6e-07
.control
run
meas tran i_bias_lna find i(vm_bias_lna) at=0.002388
meas tran i_bias_rxmix_i find i(vm_bias_rxmix_i) at=0.002388
meas tran i_bias_rxmix_q find i(vm_bias_rxmix_q) at=0.002388
meas tran i_bias_bbfilter_i find i(vm_bias_bbfilter_i) at=0.002388
meas tran i_bias_bbfilter_q find i(vm_bias_bbfilter_q) at=0.002388
meas tran i_bias_txmix_i find i(vm_bias_txmix_i) at=0.002388
meas tran i_bias_txmix_q find i(vm_bias_txmix_q) at=0.002388
meas tran i_bias_rfdriver find i(vm_bias_rfdriver) at=0.002388
meas tran i_bias_adc_i find i(vm_bias_adc_i) at=0.002388
meas tran i_bias_adc_q find i(vm_bias_adc_q) at=0.002388
meas tran i_bias_dac_i find i(vm_bias_dac_i) at=0.002388
meas tran i_bias_dac_q find i(vm_bias_dac_q) at=0.002388
meas tran i_bias_refbuf find i(vm_bias_refbuf) at=0.002388
meas tran i_bias_pll_ring_tx find i(vm_bias_pll_ring_tx) at=0.002388
meas tran i_bias_pll_ring_rx find i(vm_bias_pll_ring_rx) at=0.002388
meas tran i_bias_pll_ring_host find i(vm_bias_pll_ring_host) at=0.002388
meas tran i_bias_lc_vco_reserved find i(vm_bias_lc_vco_reserved) at=0.002388
meas tran i_bias_ctle find i(vm_bias_ctle) at=0.002388
meas tran i_bias_detect find i(vm_bias_detect) at=0.002388
meas tran i_bias_wiredtx find i(vm_bias_wiredtx) at=0.002388
meas tran i_bias_bb_tap_i find i(vm_bias_bb_tap_i) at=0.002388
meas tran i_bias_bb_tap_q find i(vm_bias_bb_tap_q) at=0.002388
meas tran i_bias_bb_tap_wmon find i(vm_bias_bb_tap_wmon) at=0.002388
meas tran v_vbg find v(vbg) at=0.002388
meas tran v_root_ref find v(root_ref) at=0.002388
meas tran v_vref0 find v(vref0) at=0.002388
meas tran v_vcm find v(vcm) at=0.002388
meas tran v_trk_rf find v(trk_rf) at=0.002388
meas tran v_trk_conv find v(trk_conv) at=0.002388
meas tran v_trk_pll find v(trk_pll) at=0.002388
meas tran v_trk_wire find v(trk_wire) at=0.002388
meas tran v_trk_debug find v(trk_debug) at=0.002388
meas tran ivdd_end find i(vdd) at=0.002388
meas tran ivdd_pk min i(vdd)
meas tran vbg_pk max v(vbg)
meas tran vbg_pp pp v(vbg) from=0.00216 to=0.002388
.endc
.end
