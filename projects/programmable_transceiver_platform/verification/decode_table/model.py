"""Expected port values from ctl_ports.txt / owners' files. F = active field values, all islands on, no fault, reset seen."""
GAIN = [(2,0,0),(3,0,0),(4,0,0),(6,0,0),(8,0,0),(12,0,0),(17,0,0),(24,0,0),(35,0,0),(12,1,0),(17,1,0),(24,1,0),(35,1,0),(12,1,1),(17,1,1),(25,1,1),(36,1,1)]  # chip-top-pins.md LUT: k, gainc0, gainc1
def onehot(code, codes): return sum((code == c) << i for i, c in enumerate(codes))
def expect(F, D, O):
    """O: observed outputs used as inputs of the model where the contract refers to another macro output (rx_en_aux)."""
    f = lambda n: F[n]; E = {}; A = 2
    for n in ('ena', 'ref_sel_coarse', 'ref_sel_fine'): E['c_biasgen_' + n] = f('core.biasgen.' + n)
    E['c_biasgen_ref_sel_vbg'] = f('core.biasgen.ref_sel_vbg') & D['bg_ok']
    for n in ('idac2_source', 'idac1_source', 'bandgap_sink1', 'bandgap_sink2', 'voltgen_source', 'voltgen_sink1', 'voltgen_sink2'): E['c_biasgen_' + n] = f('core.biasgen.' + n)
    E['c_aosc_en'] = f('core.aosc.enable'); E['c_bgap_ena'] = f('core.refchain.bgap_ena'); E['c_bgap_trim'] = (1 << f('core.refchain.bgap_trim')) - 1
    for n in ('rf', 'conv', 'pll', 'wire', 'debug'): E['c_bias_dist_en_' + n] = f('core.refchain.dist_en_' + n) & D['bg_ok']
    # RF receive
    fast = D['rx_gain_active']; code = f('lna.agc.code%d' % (D['rx_gain'] >> 5)) if fast else (f('lna.match.gain_lo') << 5) | f('lna.match.att')
    E['c_lna_en'] = int(f('lna.state.state') == A); E['c_lna_gain_lo'] = code >> 5; E['c_lna_att'] = code & 31
    E['c_lna_byp'] = f('debug.rf_rx_bypass.lna'); E['c_lna_ct'] = f('lna.match.ctrim'); E['c_lna_se'] = f('lna.match.se'); E['c_lna_rt'] = f('lna.match.rterm'); E['c_lna_lobias'] = f('lna.bias.lo')
    for c in 'iq':
        E[f'c_rxmix_{c}_en'] = int(f(f'rxmix_{c}.state.state') == A); E[f'c_rxmix_{c}_ofs'] = f(f'rxmix.offset.{c}_code')
        E[f'c_bbfilter_{c}_en'] = int(f('consolidation.bbfilter.direction') != 0)
        idx = min(D['rx_gain'] & 31, 16) if fast else f(f'bbfilter_{c}.trim.gain'); k, g0, g1 = GAIN[idx]
        E[f'c_bbfilter_{c}_gain'] = k; E[f'c_bbfilter_{c}_gainc'] = g0 | (g1 << 1)
        for n in ('cut', 'qt', 'dcf'): E[f'c_bbfilter_{c}_{n}'] = f(f'bbfilter_{c}.trim.{n}')
        E[f'c_bb_tap_{c}_bias_en'] = int(f('debug.bb_tap.mode') != 0)
    tap = f('debug.bb_tap.mode')   # off observe_rx_mixer observe_rx_filter observe_rx_pga inject_rx observe_tx inject_tx_filter inject_tx_mixer
    E['c_bbfilter_dir_tx'] = int(f('consolidation.bbfilter.direction') == 2 or tap == 7); E['c_bbfilter_inj'] = int(tap in (4, 6, 7))
    E['c_bbfilter_obs_sel'] = {1: 1, 3: 2, 2: 3, 5: 3}.get(tap, 0); E['c_bbfilter_rx_direct'] = f('consolidation.bbfilter.rx_direct')
    E['c_bbfilter_byp_s1'] = f('debug.rf_bb_bypass.pga') | int(tap == 7); E['c_bbfilter_byp_s23'] = f('debug.rf_bb_bypass.rxfilter') | int(tap == 7)
    E['c_bb_tap_obs_en'] = int(tap in (1, 2, 3, 5)); E['c_bb_tap_inj_en'] = int(tap in (4, 6, 7))
    wm = f('debug.wmon_select.select'); E['c_bb_tap_wmon_bias_en'] = E['c_wmon_obs_en'] = E['c_wmon_en'] = int(wm != 0); E['c_wmon_sel'] = (wm - 1) if wm else 0
    # converters
    for c in 'iq':
        E[f'c_adc_{c}_en'] = int(f(f'adc_{c}.state.state') == A); E[f'c_adc_{c}_test'] = f(f'adc_{c}.config.input_test')
        E[f'c_dac_{c}_en'] = int(f(f'dac_{c}.state.state') == A); E[f'c_dac_{c}_hold_zero'] = f(f'dac_{c}.config.hold_zero')
    E['c_adc_ilen'] = f('adc.config.interleave'); E['c_adc_acq'] = f('adc.config.acquisition'); E['c_refbuf_en'] = int(f('refbuf.state.state') == A); E['c_refbuf_ovr'] = f('debug.bias_override.refbuf')
    # RF transmit
    for n in ('txmix_i', 'txmix_q', 'txsum', 'rfdriver'): E[f'c_{n}_en'] = int(f(n + '.state.state') == A)
    E['c_txmix_sel_dac'] = f('consolidation.bbfilter.tx_dac_direct'); E['c_txmix_sat'] = f('consolidation.txmix.sat_mode')
    E['c_rfdriver_mute'] = f('rfdriver.mute.mute') | D['rf_mute']; E['c_rfdriver_bypass'] = f('debug.rf_tx_bypass.rfdriver'); E['c_rfdriver_g'] = f('rfdriver.gain.code'); E['c_rfdriver_se'] = f('rfdriver.gain.single_ended')
    # LO
    m = f('rfpll.config.lo_mode'); E['c_lo_ext'] = int(m in (1, 3)); E['c_lo_int'] = int(m in (2, 3)); E['c_lo_cmlsel'] = int(m == 3)
    syn = int(f('rfpll.state.state') == A and m == 2)
    for n in ('c_qvco_en', 'c_lo_mmd_en', 'c_lo_pfdcp_en', 'c_lo_vreg_en'): E[n] = syn
    E['c_qvco_band'] = f('rfpll.config.vco_coarse'); E['c_qvco_atb_en'] = f('rfpll.config.atb_enable'); E['c_lo_pre'] = f('rfpll.config.lo_preset')
    E['c_lo_mmd_n'] = f('rfpll.config.lo_n'); E['c_lo_icp'] = f('rfpll.config.lo_icp')
    src = f('debug.clk_obs.source'); E['c_lo_obs_en'] = int(src == 1)
    E['c_rx_ref_en'] = int(f('refinput.state.state') == A and m not in (1, 3))
    E['c_refvcm_en'] = E['c_lo_ext'] | E['c_rx_ref_en'] | O['rx_en_aux']
    # clocks
    E['c_clockmux_ps'] = onehot(f('clockmux.config.ring_ref'), (1, 2, 3))
    E['c_clockmux_ws'] = onehot(f('debug.clk_select.wire_line'), (1, 2, 3, 4)); E['c_clockmux_ss'] = onehot(f('debug.clk_select.wire_sample'), (1, 2, 4))
    E['c_clockmux_cs'] = onehot(f('debug.clk_select.conv_sample'), (1, 2, 3, 5)); E['c_clockmux_hs'] = onehot(f('debug.clk_select.host_clk'), (1, 5))
    for p, n in (('c_prescale', 'host'), ('c_prescale_conv', 'conv'), ('c_prescale_hf', 'hf')):
        c = f(f'clockmux.config.{n}_prescale'); E[p + '_en'] = int(c != 0); E[p + '_d'] = onehot(c, (1, 2, 3, 4))
    sl = int(f('slicer.state.state') == A); rate = f('slicer.capture.rate_mode')
    E['c_wordclk_en'] = E['c_wrx_cap_en'] = E['c_slicer_en'] = sl
    E['c_wordclk_d10'] = E['c_wrx_cap_b2'] = int(rate == 1); E['c_wordclk_d20'] = E['c_wrx_cap_b1'] = int(rate == 2)
    E['c_pllvreg_byp_tx'] = f('pllvreg.config.tx_bypass'); E['c_pllvreg_byp_cdr'] = f('pllvreg.config.rx_bypass')
    E['c_pll_tx_en'] = f('ring_l.config.enable') & D['vreg_tx_ok']; E['c_pll_tx_n4'] = int(f('ring_l.config.modulus') == 2); E['c_pll_tx_n8'] = int(f('ring_l.config.modulus') == 1)
    E['c_pll_tx_band'] = f('ring_l.config.band')
    con = int(f('cdr.state.state') == A or f('ring_c.config.line_pll')); cm = f('ring_c.config.modulus')   # 16 8 4 10 5
    E['c_pll_cdr_en'] = con & D['vreg_rx_ok']; E['c_cdr_en'] = con
    E['c_pll_cdr_n8'] = int(cm == 1); E['c_pll_cdr_n4'] = int(cm == 2); E['c_pll_cdr_n10'] = int(cm == 3); E['c_pll_cdr_n5'] = int(cm == 4)
    E['c_pll_cdr_kp'] = f('ring_c.config.kp'); E['c_pll_cdr_band'] = f('ring_c.config.band'); E['c_cdr_pfd_mode'] = f('ring_c.config.line_pll')
    E['c_cdr_ref_sel'] = f('cdr.ac3.fll_ref_wck'); E['c_cdr_g'] = f('cdr.ac3.loop_bw'); E['c_cdr_otr'] = f('cdr.ac3.otr')
    E['c_char_en'] = f('debug.replica.ro33_enable') | f('debug.replica.ro50_enable') << 1 | f('debug.replica.cmldiv_enable') << 2
    E['c_ring_osc_en'] = f('debug.replica.ringosc_enable'); E['c_vco_replica_en'] = f('debug.replica.vco_enable')
    E['c_clk_obs_en'] = int(src != 0); E['c_clk_obs_off'] = int(src == 0); E['c_clk_obs_s'] = min(src, 15); E['c_clk_obs_n'] = f('debug.clk_obs.divider_log2')
    E['c_obs_pre4_en'] = onehot(src, (2, 3, 5, 6, 8, 14))
    # wired receive
    pl = f('termination.config.p_load'); d100 = f('termination.config.differential_100_enable')
    E['c_term_en'] = int(pl != 0 or d100); E['c_term_mode'] = None if (d100 and pl) else 2 if d100 else {0: 0, 1: 3, 2: 1}[pl]
    E['c_term_hs_en'] = f('termination.config.hs_enable'); E['c_term_hs_term_en'] = f('termination.config.hs_term_enable'); E['c_term_hs_trim'] = f('termination.config.hs_trim')
    E['c_rxlevel_en'] = int(f('rxlevel.config.path') != 0); E['c_rxlevel_half'] = int(f('rxlevel.config.path') == 2)
    E['c_ctle_en'] = int(f('ctle.state.state') == A); E['c_ctle_bypass'] = f('debug.wire_bypass.ctle'); E['c_ctle_peak'] = f('ctle.config.peak'); E['c_ctle_lf_zero'] = f('ctle.config.lf_zero')
    E['c_rxselect_en'] = int(f('rxselect.state.state') == A); E['c_rxselect_direct'] = f('rxselect.select.branch')
    E['c_detect_en'] = int(f('detect.state.state') == A); E['c_detect_thr'] = f('detect.config.low_threshold_code'); E['c_detect_se'] = f('detect.config.high_threshold_code')
    E['c_detect_src_tx'] = f('consolidation.detect.src_tx'); E['c_detect_inject'] = f('detect.config.test_current_enable')
    E['c_vthdac_en'] = f('slicer.threshold.vth_enable')
    E['c_vthdac_a'] = D['vth_a'] if D['vth_fast'] & 1 else f('slicer.threshold.vth_a'); E['c_vthdac_b'] = D['vth_b'] if D['vth_fast'] & 2 else f('slicer.threshold.vth_b')
    for s in ('d0', 'd1', 'd2', 'd3', 'e0', 'e1', 'e2', 'e3'): E['c_slicer_trim_' + s] = f('slicer.offset.trim_' + s)
    for k in range(4): E[f'c_slicer_vsel_e{k}'] = f(f'slicer.threshold.vsel_e{k}')
    for k in range(8): E[f'c_ptrim_t{k}'] = f(f'cdr.phase_trim.p{k}')
    E['c_wrx_cap_rcs'] = f('slicer.capture.rcsel')
    # wired transmit / USB static
    rm = f('consolidation.wiredtx_stage.rate_mode'); E['c_wiredtx_mode_h'] = int(rm == 1); E['c_wiredtx_mode_f'] = int(rm == 2)
    E['c_wiredtx_ext'] = f('debug.wtx_ext.enable'); E['c_wiredtx_post_pol'] = f('wiredtx.config.post_polarity')
    E['c_wiredtx_main_code'] = f('wiredtx.config.current_code'); E['c_wiredtx_post_code'] = f('wiredtx.config.postcursor_code')
    E['c_hsbias_en'] = f('usbhs.bias.enable'); E['c_hsbias_c'] = f('usbhs.bias.code')
    E['c_wtxfb_branch'] = f('txpad.config.branch'); E['c_wtxfb_state'] = f('wiredtx.state.state'); E['c_wtxfb_idle'] = f('wiredtx.idle.idle'); E['c_wtxfb_stage_tmds'] = f('consolidation.wiredtx_stage.stage')
    ub = f('usbdrive.select.branch')   # off hs fsls
    E['c_usb_hs_en'] = int(ub == 1 and f('usbhs.config.tx_enable')); E['c_usb_fs_en'] = int(ub == 2 and f('usbfs.config.drive_enable'))
    E['c_usb_hs_str'] = f('usbhs.config.drive_strength')
    for n in ('pullup_p', 'pullup_n', 'pulldown_p', 'pulldown_n', 'ls_slow'): E['c_usb_' + n] = f('usbfs.config.' + n)
    E['c_usb_term_trim'] = f('usbhs.config.term_trim') if f('usbhs.config.term_enable') else 0
    return E
DYNAMIC = {'c_wiredtx_ser_en', 'c_wiredtx_bias_en', 'c_txpad_req_main', 'c_txpad_req_post', 'c_txpad_req_detect', 'c_txpad_req_term', 'c_usb_hs_drv', 'c_usb_tx_dp', 'c_usb_tx_dn',
           'c_usb_tx_oe', 'c_cdr_fup', 'c_cdr_fdn', 'c_wrx_cap_psel', 'c_wrx_cap_slipp', 'c_wrx_cap_slipm'}
