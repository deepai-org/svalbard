#!/usr/bin/env python3
"""Digital's answer in integration/top/ctl_ports.txt: fills the 'register field' column (and the encoding where the
macro decode differs from the proposal) for every port whose field did not exist. Re-runnable."""
P='/home/ubuntu/svalbard/projects/programmable_transceiver_platform/integration/top/ctl_ports.txt'
D='direct'
M={ # port: (encoding or None = keep, field)
 'c_lna_gain_lo':('lna.match.gain_lo, or bit 5 of lna.agc.code<k> while the opcode-4 fast gain is active (k = LNA index)','lna.match.gain_lo+lna.agc.code0'),
 'c_lna_att':('lna.match.att, or bits 4:0 of lna.agc.code<k> while the opcode-4 fast gain is active','lna.match.att+lna.agc.code0'),
 'c_lna_lobias':(D,'lna.bias.lo'),
 'c_bbfilter_i_cut':(D,'bbfilter_i.trim.cut'),'c_bbfilter_q_cut':(D,'bbfilter_q.trim.cut'),
 'c_bbfilter_i_gain':('k[5:0] of the 17-entry LUT of the dB index (0..16 = -6..+42 dB; opcode-4 PGA index while active); 0 while the rf island is off','bbfilter_i.trim.gain'),
 'c_bbfilter_q_gain':('as _i_','bbfilter_q.trim.gain'),
 'c_bbfilter_i_gainc':('{gainc1, gainc0} of the same LUT','bbfilter_i.trim.gain'),'c_bbfilter_q_gainc':('as _i_','bbfilter_q.trim.gain'),
 'c_bbfilter_i_qt':(D,'bbfilter_i.trim.qt'),'c_bbfilter_q_qt':(D,'bbfilter_q.trim.qt'),
 'c_bbfilter_i_dcf':(D,'bbfilter_i.trim.dcf'),'c_bbfilter_q_dcf':(D,'bbfilter_q.trim.dcf'),
 'c_adc_ilen':(D,'adc.config.interleave'),'c_adc_acq':(D,'adc.config.acquisition'),
 'c_rfdriver_g':(D,'rfdriver.gain.code'),
 'c_rfdriver_mute':('(rfdriver.mute.mute (fault-forced to 1) OR the transport mute) & island_on[1]','rfdriver.mute.mute'),
 'c_lo_ext':(None,'rfpll.config.lo_mode'),'c_lo_int':(None,'rfpll.config.lo_mode'),'c_lo_cmlsel':(None,'rfpll.config.lo_mode'),
 'c_qvco_en':(None,'rfpll.state.state+rfpll.config.lo_mode'),'c_lo_mmd_en':(None,'rfpll.state.state+rfpll.config.lo_mode'),
 'c_lo_pfdcp_en':(None,'rfpll.state.state+rfpll.config.lo_mode'),'c_lo_vreg_en':(None,'rfpll.state.state+rfpll.config.lo_mode'),
 'c_qvco_band':(D,'rfpll.config.vco_coarse'),'c_qvco_atb_en':(D,'rfpll.config.atb_enable'),'c_lo_pre':(D,'rfpll.config.lo_preset'),
 'c_lo_mmd_n':(D,'rfpll.config.lo_n'),'c_lo_icp':(D,'rfpll.config.lo_icp'),
 'c_refvcm_en':(None,'rfpll.config.lo_mode+refinput.state.state'),
 'c_rx_ref_en':(None,'refinput.state.state+rfpll.config.lo_mode'),
 'c_clockmux_ps':(None,'clockmux.config.ring_ref'),
 'c_prescale_en':(None,'clockmux.config.host_prescale'),'c_prescale_d':(None,'clockmux.config.host_prescale'),
 'c_prescale_conv_en':(None,'clockmux.config.conv_prescale'),'c_prescale_conv_d':(None,'clockmux.config.conv_prescale'),
 'c_prescale_hf_en':(None,'clockmux.config.hf_prescale'),'c_prescale_hf_d':(None,'clockmux.config.hf_prescale'),
 'c_wordclk_d10':('slicer.capture.rate_mode == half','slicer.capture.rate_mode'),'c_wordclk_d20':('slicer.capture.rate_mode == full','slicer.capture.rate_mode'),
 'c_pll_tx_en':(None,'ring_l.config.enable'),'c_pll_tx_n4':(None,'ring_l.config.modulus'),'c_pll_tx_n8':(None,'ring_l.config.modulus'),
 'c_pll_tx_band':(D,'ring_l.config.band'),
 'c_pll_cdr_en':('((cdr.state == active) OR ring_c.config.line_pll) & island_on[2] & vreg_rx_ok (D-HF: host_follow enables the ring without cdr.state)','cdr.state.state+ring_c.config.line_pll'),
 'c_cdr_en':('((cdr.state == active) OR ring_c.config.line_pll) & island_on[2]','cdr.state.state+ring_c.config.line_pll'),
 'c_pll_cdr_n4':(None,'ring_c.config.modulus'),'c_pll_cdr_n8':(None,'ring_c.config.modulus'),'c_pll_cdr_n5':(None,'ring_c.config.modulus'),'c_pll_cdr_n10':(None,'ring_c.config.modulus'),
 'c_pll_cdr_kp':(D,'ring_c.config.kp'),'c_pll_cdr_band':(D,'ring_c.config.band'),'c_cdr_pfd_mode':(D,'ring_c.config.line_pll'),
 'c_cdr_otr':(D,'cdr.ac3.otr'),
 'c_cdr_fup':('rtl/pt_wrx_ctl.sv frequency loop: FUP pulse (automatic from frequency counter b, or manual by register)','wrx.loop.fll_auto+wrx.loop.fll_manual_trigger'),
 'c_cdr_fdn':('rtl/pt_wrx_ctl.sv frequency loop: FDN pulse','wrx.loop.fll_auto+wrx.loop.fll_manual_trigger'),
 'c_char_en':('{cmldiv_enable, ro50_enable, ro33_enable}','debug.replica.ro33_enable+debug.replica.ro50_enable+debug.replica.cmldiv_enable'),
 'c_clk_obs_n':(D,'debug.clk_obs.divider_log2'),
 'c_term_hs_en':(D,'termination.config.hs_enable'),'c_term_hs_term_en':(D,'termination.config.hs_term_enable'),'c_term_hs_trim':(D,'termination.config.hs_trim'),
 'c_ctle_peak':(D,'ctle.config.peak'),'c_ctle_lf_zero':(D,'ctle.config.lf_zero'),
 'c_vthdac_en':(D,'slicer.threshold.vth_enable'),
 'c_vthdac_a':('slicer.threshold.vth_a, or the IX-11 in-band value (transport opcode 5) until ENABLE = 0','slicer.threshold.vth_a'),
 'c_vthdac_b':('slicer.threshold.vth_b, or the IX-11 in-band value (transport opcode 6) until ENABLE = 0','slicer.threshold.vth_b'),
 **{f'c_slicer_trim_{s}{k}':(D,f'slicer.offset.trim_{s}{k}') for s in 'de' for k in range(4)},
 **{f'c_slicer_vsel_e{k}':(D,f'slicer.threshold.vsel_e{k}') for k in range(4)},
 'c_wrx_cap_rcs':(D,'slicer.capture.rcsel'),
 'c_wrx_cap_b2':('slicer.capture.rate_mode == half','slicer.capture.rate_mode'),'c_wrx_cap_b1':('slicer.capture.rate_mode == full','slicer.capture.rate_mode'),
 'c_wrx_cap_psel':('rtl/pt_wrx_ctl.sv phase picker (automatic, or wrx.picker.manual_psel)','wrx.picker.auto+wrx.picker.manual_psel'),
 'c_wrx_cap_slipp':('pt_wrx_ctl slip tag + (automatic with the PSEL 3 -> 4 step, or one per change of manual_slip_plus)','wrx.picker.auto+wrx.picker.manual_slip_plus'),
 'c_wrx_cap_slipm':('pt_wrx_ctl slip tag -','wrx.picker.auto+wrx.picker.manual_slip_minus'),
 'c_wiredtx_post_pol':(D,'wiredtx.config.post_polarity'),
 'c_txpad_req_term':('txpad.config.term_request through the pad sequencer (rtl/pt_wtx_ctl.sv)','txpad.config.term_request'),
 'c_usb_hs_drv':('rtl/pt_usb.sv: 1 while an HS packet is in the serializer (word-granular)','usbdrive.select.branch+usbhs.config.tx_enable'),
 'c_usb_tx_dp':('rtl/pt_usb.sv: FS/LS line level D+ / chirp from the direct-stream symbols or usb.config.force_symbol','usb.config.force_symbol+digital.transport_config.direct_stream_enable'),
 'c_usb_tx_dn':('rtl/pt_usb.sv: FS/LS line level D-','usb.config.force_symbol+digital.transport_config.direct_stream_enable'),
 'c_usb_tx_oe':('rtl/pt_usb.sv: output enable for TX_DP / TX_DN','usb.config.force_enable+digital.transport_config.direct_stream_enable'),
 'c_usb_hs_str':(D,'usbhs.config.drive_strength'),
}
out=[];seen=set()
for l in open(P):
    if l.startswith('c_'):
        c=[x.strip() for x in l.rstrip('\n').split('|')]
        while len(c)<6: c.append('')
        if c[0] in M:
            enc,f=M[c[0]]; seen.add(c[0])
            if enc is not None: c[3]=enc
            c[4]=f
            if c[5].startswith('new field') or c[5].startswith('new per') or c[5].startswith('new debug'): c[5]='(was: '+c[5]+')'
        l=' | '.join(c).rstrip()+'\n'
    out.append(l)
assert not set(M)-seen, set(M)-seen
open(P,'w').write(''.join(out))
