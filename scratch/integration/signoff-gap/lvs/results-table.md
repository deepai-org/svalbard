| Block (top cell) | GDS | Devices ref / read-back | Magic read-back + netgen | KLayout deck (2nd extractor) | Note |
|---|---|---|---|---|---|
| pt_lna | rf_rx/generated/lna.gds | 835 / 835 | match | MOS+R match; not recognised: MIM |  |
| pt_rxmix_i | rf_rx/generated/rxmix_i.gds | 1186 / 1186 | match | MOS+R match; not recognised: MIM |  |
| pt_bbfilter_i | rf_rx/generated/bbfilter_i.gds | 1647 / 1647 | match | MOS+R match; not recognised: MIM, nd2ps diode |  |
| pt_bb_tap | rf_rx/generated/bb_tap.gds | 152 / 152 | match | MOS+R match; not recognised: MIM, nd2ps diode |  |
| pt_txmix_i | rf_tx/generated/txmix_i.gds | 62 / 62 | match | match |  |
| pt_txsum | rf_tx/generated/txsum.gds | 16 / 16 | match | match |  |
| pt_rfdriver | rf_tx/generated/rfdriver.gds | 855 / 855 | match | MOS+R match; not recognised: nd2ps diode |  |
| pt_adc_i | converters/generated/adc_i.gds | 3727 / 3727 | match | MOS+R match; not recognised: MIM |  |
| pt_adc_q | converters/generated/adc_q.gds | 3735 / 3735 | match | MOS+R match; not recognised: MIM, nd2ps diode |  |
| pt_dac_i | converters/generated/dac_i.gds | 7524 / 7524 | match | MOS+R match; not recognised: MIM, nd2ps diode |  |
| pt_dac_q | converters/generated/dac_q.gds | 7524 / 7524 | match | MOS+R match; not recognised: MIM, nd2ps diode |  |
| pt_refbuf | converters/generated/refbuf.gds | 56 / 56 | match | MOS+R match; not recognised: MIM |  |
| pt_pll_vreg2 | pll_vreg/generated/pt_pll_vreg2.gds | 230 / 230 | match | MOS+R match; not recognised: nd2ps diode |  |
| pt_clockmux | timing/generated/clockmux.gds | 150 / 150 | match | match |  |
| pt_aosc | timing/generated/aosc.gds | 34 / 34 | match | match |  |
| pt_pll_ring | timing/generated/pll_ring.gds | 789 / 789 | match | MOS+R match; not recognised: nd2ps diode |  |
| pt_polyphase | timing/generated/polyphase.gds | 86 / 86 | match | match |  |
| pt_clk_obs16 | timing/generated/clk_obs16.gds | 505 / 505 | match | MOS+R match; not recognised: nd2ps diode |  |
| pt_obs_pre4 | timing/generated/obs_pre4.gds | 41 / 41 | match | match |  |
| pt_ring_osc | timing/generated/ring_osc.gds | 55 / 55 | match | MOS+R match; not recognised: nd2ps diode |  |
| pt_pll_ring_core | timing/generated/pll_ring_core.gds | 530 / 530 | match | MOS+R match; not recognised: nd2ps diode |  |
| pt_lo_mmd_qdum | timing/generated/lo_mmd_qdum.gds | 44 / 44 | match | MOS+R match; not recognised: MIM, nd2ps diode |  |
| pt_wordclk | timing/generated/wordclk.gds | 210 / 210 | match | match |  |
| pt_prescale | timing/generated/prescale.gds | 98 / 98 | match | match |  |
| pt_lo_lf | timing/generated/lo_lf.gds | 91 / 91 | match | MOS+R match; not recognised: MIM |  |
| pt_lo_obs | timing/generated/lo_obs.gds | 75 / 75 | match | match |  |
| pt_lo_pfdcp | timing/generated/lo_pfdcp.gds | 151 / 151 | match | MOS+R match; not recognised: MIM, nd2ps diode |  |
| pt_diff_clk_rx | timing/generated/diff_clk_rx.gds | 127 / 127 | match | MOS+R match; not recognised: MIM |  |
| pt_clk_obs | timing/generated/clk_obs.gds | 400 / 400 | match | MOS+R match; not recognised: nd2ps diode |  |
| pt_lo_ext | timing/generated/lo_ext.gds | 481 / 481 | match | MOS+R match; not recognised: MIM, nd2ps diode |  |
| pt_vco_replica | timing/generated/vco_replica.gds | 219 / 219 | match | match |  |
| pt_lo_mmd | timing/generated/lo_mmd.gds | 528 / 528 | match | MOS+R match; not recognised: MIM, nd2ps diode |  |
| pt_lc_qvco5 | timing/generated/lcvco/pt_lc_qvco5.gds | 974 / 974 | match (core) | MOS+R match; not recognised: MIM, nd2ps diode | core subcell only (974 devices, read from the top GDS); the top `pt_lc_qvco5` has no netlist and no ports; spiral hookup read back as IP-IN and QP-QN only |
| pt_rxlevel | wired_rx/generated/rxlevel.gds | 70 / 70 | match | match |  |
| pt_cdr | wired_rx/generated/cdr.gds | 407 / 407 | match | MOS+R match; not recognised: nd2ps diode |  |
| pt_ctle | wired_rx/generated/ctle.gds | 268 / 268 | match | MOS+R match; not recognised: nd2ps diode |  |
| pt_ptrim | wired_rx/generated/ptrim.gds | 670 / 670 | match | MOS+R match; not recognised: nd2ps diode |  |
| pt_rxselect | wired_rx/generated/rxselect.gds | 26 / 26 | match | match |  |
| pt_wmon_sel | wired_rx/generated/wmon_sel.gds | 47 / 47 | match | match |  |
| pt_termination | wired_rx/generated/termination.gds | 146 / 146 | match | MOS+R match; not recognised: nd2ps diode |  |
| pt_vthdac | wired_rx/generated/vthdac.gds | 166 / 166 | match | match |  |
| pt_detect | wired_rx/generated/detect.gds | 439 / 439 | match | MOS+R match; not recognised: nd2ps diode |  |
| pt_wrx_cap | wired_rx/generated/wrx_cap.gds | 6304 / 6304 | match | MOS+R match; not recognised: nd2ps diode |  |
| pt_slicer | wired_rx/generated/slicer.gds | 864 / 864 | match | MOS+R match; not recognised: nd2ps diode |  |
| pt_wtx_hsbias | wired_tx/generated/hsbias.gds | 53 / 53 | match | match |  |
| pt_wiredtx | wired_tx/generated/wiredtx.gds | 2274 / 2274 | match | MOS+R match; not recognised: nd2ps diode |  |
| tx_steering_buffer_flat | pads/generated/steering-buffer-compact/tx_steering_buffer_flat.gds | 128 / 128 | match | match |  |
| buffer_compensated_flat | pads/generated/termination-buffer-candidate/compact-array/buffer_compensated_flat.gds | 282 / 282 | match | MOS+R match; not recognised: MIM |  |
| pad_tlp_flat | pads/generated/tlp-site/pad_tlp_flat.gds | 8 / 8 | match | match |  |
| pad_rf_pair | pads/generated/stress-safe-families/rf-pair/pad.gds | 388 / 388 | match | MOS match; ppolyf_u_1k_6p0 length +0.59 %; MIM/diodes not recognised |  |
| pad_rftxpad | pads/generated/stress-safe-families/rf-tx/pad.gds | 388 / 388 | match | MOS match; ppolyf_u_1k_6p0 length +0.59 %; MIM/diodes not recognised |  |
| pad_single_leg | pads/generated/stress-safe-families/single-leg/pad.gds | 388 / 388 | match | MOS match; ppolyf_u_1k_6p0 length +0.59 %; MIM/diodes not recognised |  |
| pad_refpad | pads/generated/stress-safe-families/reference/combined.gds | 405 / 404 | match on devices and nets | MOS match; ppolyf_u_1k_6p0 length +0.59 %; MIM/diodes not recognised | simulated netlist also has one script-added `diode_nw2ps_06v0` well-diode model (not a drawn device); layout exposes pin ESD_RAIL that the reference subckt does not |
| pad_hspad | pads/generated/stress-safe-families/wired-receive-hs/pad_hspad.gds | 509 / 508 | match on devices and nets | MOS match; ppolyf_u_1k_6p0 length +0.59 %; MIM/diodes not recognised | simulated netlist also has one script-added `diode_nw2ps_06v0` well-diode model (not a drawn device); layout exposes pin ESD_RAIL that the reference subckt does not |
| pad_wirepad | pads/generated/stress-safe-families/wired-receive-usb/combined.gds | 740 / 739 | match on devices and nets | MOS match; ppolyf_u_1k_6p0 length +0.59 %; MIM/diodes not recognised | simulated netlist also has one script-added `diode_nw2ps_06v0` well-diode model (not a drawn device); layout exposes pin ESD_RAIL that the reference subckt does not |
| pad_txpad | pads/generated/stress-safe-families/wired-transmit/combined.gds | 596 / 595 | match on devices and nets | MOS match; ppolyf_u_1k_6p0 length +0.59 %; MIM/diodes not recognised | simulated netlist also has one script-added `diode_nw2ps_06v0` well-diode model (not a drawn device); layout exposes pin ESD_RAIL that the reference subckt does not |
| pt_rxmix_q | rf_rx/generated/rxmix_q.gds | 1186 / 1186 | match | MOS+R match; not recognised: MIM |  |
| pt_bbfilter_q | rf_rx/generated/bbfilter_q.gds | 1647 / 1647 | match | MOS+R match; not recognised: MIM, nd2ps diode |  |
| pt_txmix_q | rf_tx/generated/txmix_q.gds | 62 / 62 | match | match |  |
| pt_wtx_fallback_control | bringup_control/generated/pt_wtx_fallback_control.gds | 50 / 50 | match | match |  |
| gf180mcu_ocd_ip__por | core_support/por/gds/gf180mcu_ocd_ip__por.gds.gz | 494 / 494 | match | MOS+R match; not recognised: MIM |  |
| pt_core_bias | scratch/core-bias-routing-20261110-compact/pt_core_bias_routed.gds | 0 / 4147 | match per leaf (see note) | no flat reference | top = routing LVS with black boxes (already from GDS); 9 leaf masters read back from the routed GDS: 7 match, bandgap matches with the documented PNP name alias, biasgen identical to the vendored patched tapeout GDS |
| isw_wired | scratch/island-support-20261108-075605/layout/isw_wired.gds | 3560 / 3560 | match | match |  |
| isw_rf | scratch/island-support-20261108-075605/layout/isw_rf.gds | 2554 / 2554 | match | match |  |
| isw_pll | scratch/island-support-20261108-075605/layout/isw_pll.gds | 2736 / 2736 | match | match |  |
| isw_conv | scratch/island-support-20261108-075605/layout/isw_conv.gds | 1346 / 1346 | match | match |  |
| isw_debug | scratch/island-support-20261108-075605/layout/isw_debug.gds | 1790 / 1790 | match | match |  |
| iso_clamp | scratch/island-support-20261108-075605/layout/iso_clamp.gds | 6 / 6 | match | match |  |
| atb_leaf_s | scratch/island-support-20261108-075605/layout/atb_leaf_s.gds | 7 / 7 | match | match |  |
| atb_leaf_f | scratch/island-support-20261108-075605/layout/atb_leaf_f.gds | 7 / 7 | match | match |  |
| atb_grp | scratch/island-support-20261108-075605/layout/atb_grp.gds | 20 / 20 | match | match |  |
| pt_decap_tile | decap/generated/pt_decap_tile.gds | 22 / 22 | match | match |  |
| atb_pad | scratch/island-support-20261108-075605/layout/atb_pad.gds | 22 / 22 | match | match |  |
| pt_pll_vreg | pll_vreg/generated/pt_pll_vreg.gds | 196 / 196 | match | MOS+R match; not recognised: nd2ps diode |  |
