# Second pass of spec_edit.py (exec'd inside it): fields of the sub-agent modules pt_monitor, pt_usb, pt_wtx_ctl, pt_wrx_ctl.
# ---------------------------------------------------------------- supply / clock monitor (rtl/pt_monitor.sv)
A['monitor.config'] = dict(update='stopped', description='Supply / clock monitor rtl/pt_monitor.sv (D-FAULT): fault = any armed requirement that is pending, tripped (sticky cause) or unobservable (monitor clock lost). Reset: nothing armed, fault = 0; writing every requirement to 0 releases fault with no clock at all (no-brick rule). Time base: the always-on oscillator (core.aosc.enable must be 1), 16.7-25 ns per tick. The window comparators for supply_high / supply_low do not exist (build demand pt_supply_window): supply monitoring is island power-good only.', fields=dict(
    require_reference=num(1, live=True, description='reference clock (ref_clk) must be toggling'),
    require_input_clock=num(1, live=True, description='host-forwarded clock H2D_CLK must be toggling (the FPGA must keep it free-running)'),
    require_rf_lock=num(1, live=True, description='frequency counter a must be in lock (debug.freq_count_a: e.g. source lc_prescale for the LO)'),
    require_wire_lock=num(1, live=True, description='frequency counter b must be in lock (debug.freq_count_b: e.g. a ring FBCK)'),
    required_supply_mask=num(6, 0, live=True, description='bit k = island k power-good required (0 wired, 1 rf, 2 pll, 4 conv, 5 debug; bit 3 has no switch and is ignored). Reset 0: islands are off at reset.'),
    loss_timeout_ticks=num(12, 16, minimum=8, description='monitor-clock ticks without an edge (clocks) or with a bad level (locks, supplies) before a qualified requirement trips. Minimum 8.'),
    qualification_ticks=num(16, 19, description='a pending requirement must be good for this many units of 64 ticks before it counts (reset 19 = at least 20 us).')))
# ---------------------------------------------------------------- USB (rtl/pt_usb.sv; MW-18, D-USB)
bi['usb'] = ['wired']
A['usb.config'] = dict(update='stopped', description='USB pad direct-stream logic rtl/pt_usb.sv (protocol in the FPGA). TX symbols {dn, dp} from the transport quads, RX = pt_detect comparators oversampled; FS/LS fully on chip, HS data through pt_wiredtx + the pt_usb_txdrv pre-driver (build demand).', fields=dict(
    hs_symbol=num(1, description='HS branch: 1 = the symbol stream drives the HS gates statically (chirp), 0 = packet mode'),
    force_enable=num(1, live=True, description='drive force_symbol instead of the stream (termination calibration, chirp over SPI)'),
    force_symbol=num(2, 3, live=True, description='{dn, dp}: 01 D+ high, 10 D- high, 00 SE0, 11 released'),
    tx_divider=num(8, 3, description='tx clock cycles per symbol - 1 (48 MHz: FS 3, LS 31)'),
    bbm=num(2, 0, description='extra break-before-make cycles (gap = 1 + bbm tx clocks)'),
    rx_enable=num(1, live=True, description='line receive / oversampling on'),
    rx_differential=num(1, description='1 = J/K from the differential comparators while a line is high, 0 = single-ended only'),
    rx_echo=num(1, description='1 = keep recording while this chip drives'),
    rx_divider=num(8, 3, minimum=3, description='rx clock cycles per bit - 1'),
    rx_quiet=num(5, 8, description='unchanged bits that end a receive burst'),
    debounce_se=num(8, 9, description='line-state debounce, samples - 1'),
    debounce_diff=num(4, 1, description='envelope debounce, samples - 1')))
drop('usbfs.config', ['output_r_code'])
del A['usbfs.state'], A['usbhs.state']
for r in D['rules']:
    strip_conds(r, gone)
    if r['id'] == 'rf_wired_payload_exclusive': r['then_all'].append(['usbdrive.state.state', 'ne', 'active'])
D['hardware_trim']['fields']['usbhs.config.current_code'] = dict(keep=None, source='analog/wired_tx/README.md', reason='HS driver current is set by usbhs.bias.code (pt_wtx_hsbias); kept in the spec for the system model, reads 0')
for g, n in (('digital.guard_config', None), ('digital.hop_config', None)):
    for f in A[g]['fields']:
        D['hardware_trim']['fields'][f'{g}.{f}'] = dict(keep=None, source='spec/fpga-offload-audit', reason='FPGA-side scheduling parameter: no on-chip consumer; kept in the spec for the system model, reads 0')
# ---------------------------------------------------------------- wired TX launch (rtl/pt_wtx_ctl.sv)
A['ring_l.config']['fields']['lock_time'] = num(8, 255, description='tx_ring_ready timer: (code + 1) x 64 REF cycles after the ring enable (reset 255 = 328 us at 50 MHz).')
A['ring_l.config']['fields']['ready_select'] = enum(['timer', 'timer_or_counter', 'counter', 'override'], 'timer', description='what releases the serializer (WT25: not the LOCK pin): the timer, frequency counter a in lock, or override (ready while enabled).')
del A['clocktree.config']
drop('consolidation.wiredtx_stage', ['bits_per_cycle'], C)
# ---------------------------------------------------------------- wired RX control plane (rtl/pt_wrx_ctl.sv; D-CDRCTL)
drop('cdr.config', [k for k in A['cdr.config']['fields'] if k not in ('nominal_rate_khz', 'acquisition_timeout_ui')])
D['hardware_trim']['fields']['cdr.config.acquisition_timeout_ui'] = dict(keep=None, source='spec/fpga-offload-audit', reason='host-side acquisition timeout: no on-chip consumer; kept in the spec for the system model, reads 0')
del A['cdr.ac3']['fields']['integral_enable']
drop('detect.config', ['counter_reset', 'enable', 'test_timeout_ticks'])
bi['wrx'] = []
A['wrx.loop'] = dict(update='stopped', description='Wired RX CDR control plane rtl/pt_wrx_ctl.sv (MW-10, D-CDRCTL): frequency loop on pt_cdr FUP/FDN from frequency counter b (source cdr_ring_fbck), full-rate phase picker (capture PSEL / slip tags), word qualification = wire_rx_valid. The block runs while the CDR and the slicer are active. Every automatic function has a register-forced manual mode.', fields=dict(
    restart=num(1, live=True, description='any change restarts the frequency loop and the word qualification'),
    freq_source=enum(['fll_done', 'ring_lock', 'counter_lock', 'forced'], 'fll_done', description='what declares the ring frequency good (hand-over to the phase loop)'),
    fll_auto=num(1, 0, description='automatic frequency loop (reset 0: manual; the FUP / FDN polarity and gain are not analog-verified yet)'), fll_invert=num(1, description='swap FUP / FDN of the automatic loop'),
    fll_shift=num(3, 3, description='pulse length = counts << shift reference cycles'),
    fll_tolerance=num(8, 3, description='counts per window: inside twice in a row = done'),
    fll_loss=num(12, 0, description='counts: re-acquire above this error; 0 = never'),
    fll_manual_trigger=num(1, live=True, description='any change: one manual pulse'), fll_manual_up=num(1, live=True, description='1 = FUP, 0 = FDN'),
    fll_manual_length=num(8, live=True, description='manual pulse length (<< fll_shift reference cycles)')))
A['wrx.picker'] = dict(update='stopped', description='pt_wrx_ctl phase picker and word qualification.', fields=dict(
    auto=num(1, description='automatic full-rate phase picker (0 = PSEL from manual_psel)'), invert=num(1, description='swap early / late'),
    threshold=num(6, 24, description='early/late accumulator threshold for one PSEL step'), hold=num(4, 4, description='words to wait after a step'),
    manual_psel=num(3, live=True, description='capture PSEL[2:0] in manual mode'),
    manual_slip_plus=num(1, live=True, description='any change: one SLIPP tag'), manual_slip_minus=num(1, live=True, description='any change: one SLIPM tag'),
    edge_half=num(1, description='the edge word belongs to DX[19:0] (0) or DX[39:20] (1)'),
    violation_threshold=num(5, description='a word is bad when its edge violations exceed this'),
    idle_words=num(4, 2, description='all-equal words in a row that mean idle; 0 = off'),
    lock_exp=num(4, 10, description='2^n consecutive good words to assert wire_rx_valid'), loss_exp=num(2, 1, description='2^n consecutive bad words to drop it'),
    valid_mode=enum(['qualified', 'frequency_only', 'forced_1', 'forced_0'], 'qualified', live=True, description='wire_rx_valid source')))
A['slicer.capture']['fields']['raw_lane'] = enum(['data', 'edge', 'both_half'], 'data', description='IX-12 ingress lane: data quad DX, edge quad {EW, EW}, or {EW, DX[19:0]} of the first half word.')
A['digital.transport_config']['fields']['linecode'] = num(1, description='IX-2 8b/10b wired line-code offload (stopped-only).')
A['digital.transport_config']['fields']['direct_stream_enable']['description'] = 'USB direct stream: the wired transport quads carry line symbols to / from rtl/pt_usb.sv instead of the serializer / capture.'
# ---------------------------------------------------------------- status registers and observation lists
sg = D['status_registers']['groups']
def st(bits, port, meaning): return dict(bits=bits, port=port, meaning=meaning)
sg['status.monitor'] = dict(description='Supply / clock monitor rtl/pt_monitor.sv. Independent bits, not a coherent snapshot.', fields=dict(
    cause=st(10, 'mon_cause', 'sticky trip cause: 0 reference, 1 input clock, 2 rf lock, 3 wire lock, 4+k supply k'),
    cause_mon_clk=st(1, 'mon_cause_clk', 'sticky: the monitor clock (aosc) stopped while armed'),
    ready=st(1, 'mon_ready', 'armed, everything qualified, no fault'), mon_dead=st(1, 'mon_dead', 'live: no monitor clock'),
    ref_alive=st(1, 'mon_ref_alive', 'live'), in_alive=st(1, 'mon_in_alive', 'live'), fault=st(1, 'mon_fault', 'live fault level (monitor OR the external fault pin)'),
    qualified=st(10, 'mon_qualified', 'live: requirement qualified')))
sg['status.wired'] = dict(description='Wired TX launch (pt_wtx_ctl) and RX control plane (pt_wrx_ctl) state. Raw multi-bit values are diagnostics (may tear by one update).', fields=dict(
    tx_state=st(3, 'wtx_state', '0 off, 1 flush, 2 pad, 3 run, 4 drain, 5 pad-off'), tx_seq_fault=st(1, 'wtx_seq_fault', 'pad sequencer fault'),
    tx_ring_ready=st(1, 'wtx_ring_ready', 'TX ring declared ready'), rx_state=st(3, 'wrx_state', '0 off 1 manual 2 wait 3 pulse 4 settle 5 fll done 6 freq ok 7 locked'),
    rx_flags=st(8, 'wrx_flags', '{slm_seen, slp_seen, idle, sig_ok, wclk_alive, freq_ok, fll_lost, fll_done}'),
    rx_fll_error=st(14, 'wrx_fll_err', 'last accepted counter error, two\'s complement'),
    rx_violations=st(5, 'wrx_viol', 'edge violations in the last word'), rx_fll_windows=st(8, 'wrx_fll_win', 'accepted windows, saturating'),
    rx_pick_acc=st(8, 'wrx_pick_acc', 'picker accumulator'), rx_slips=st(8, 'wrx_slip_cnt', 'slip tags sent, wraps')))
sg['status.usb'] = dict(description='USB line state and direct-stream status (rtl/pt_usb.sv).', fields=dict(
    line=st(2, 'usb_line', 'debounced {SE_N, SE_P}'), flags=st(7, 'usb_flags', '{disconnect, squelch, diff, se1, se0, k, j}'),
    stream=st(5, 'usb_stream', '{tx_armed, tx_blocked, tx_underrun, tx_busy, rx_active}')))
D['obs_status'] = ['island_pgood_wired', 'island_pgood_rf', 'island_pgood_pll', 'island_pgood_usb', 'island_pgood_conv', 'island_pgood_debug',
    'pll_tx_lock', 'ref_present', 'bandgap_ok', 'refbuf_ready', 'monitor_fault', 'por_n', 'cdr_freq_ok', 'cdr_fll_lost', 'adc_i_done', 'adc_q_done',
    'adc_i_overload', 'adc_q_overload', 'rf_rx_valid', 'reset_seen', 'rf_mute', 'wire_rx_valid', 'wire_tx_request', 'wire_idle', 'aux_present', 'wtx_ext_present',
    'capture_done', 'playback_enable', 'capture_enable', 'payload_enable', 'host_rx_clk_div', 'aosc_div']
D['wire_status'] = ['cdr_freq_ok', 'cdr_fll_lost', 'wrx_sig_ok', 'wrx_idle', 'usb_j', 'usb_k', 'usb_se0', 'usb_diff', 'usb_squelch', 'detect_diff',
    'usb_disconnect', 'pll_cdr_lock', 'wire_rx_valid', 'wire_tx_request', 'wire_idle', 'wtx_ext_data']
for r in D['rules']:
    strip_conds(r, gone); assert r['then_all'] and (r.get('if_any') or r.get('if_all')), r['id']
D['break_before_make'] = [n for n in D['break_before_make'] if not gone(n)]
D['hardware_trim']['fields'] = {k: v for k, v in D['hardware_trim']['fields'].items() if not gone(k)}
# ---------------------------------------------------------------- chip-top updates of 2026-11-14 (6f2cd39, 0006a99): republished cells, CP4-2/3
A['cdr.ac3']['fields']['otr'] = num(6, description='pt_cdr r13 OTA offset trim: otr[4:0] + sign (bit 5), 1/8 vote LSB, per-die calibration.')
for n in ('ro33_enable', 'ro50_enable', 'cmldiv_enable'):
    C['debug.replica']['fields'][n] = num(1, description='characterization speed cell enable (CLK_OBS code 15 ORs the three outputs: enable one at a time)')
A['usbhs.config']['fields']['drive_strength'] = num(2, 1, description='pt_usb_txdrv HS drive strength, reset 1 (USB-INTEGRATION.md).')
ext = ['external_passive', 'external_cml']
D['rules'].append({'id': 'lo_pads_vs_forwarded_clock', 'class': 'pad', 'if_any': [['rfpll.config.lo_mode', 'in', ext]],
    'then_all': [[f'debug.clk_select.{f}', 'nin', ['aux_clk', 'wclk_in']] for f in ('wire_line', 'wire_sample', 'conv_sample', 'host_clk')] +
                [['debug.clk_obs.source', 'nin', ['aux_clk', 'wclk_in']]],
    'reason': 'CP4-3: the forwarded wire clock WCLK_IN shares the AUX_CLK pad pair, which carries the Q leg of an external LO. An external LO mode excludes every use of that pair as a clock input (rf_wired_payload_exclusive does not cover all-fallback RF receive).'})
# ---------------------------------------------------------------- TOP-25 / ten islands (5b19766)
bi['rfpll'] = ['rf']      # the LO synthesizer and pt_lo_ext sit on the lo / lod islands = rf enable group (PD2-2), not pll
A['rfpll.config']['description'] += ' Island: the LO cells are on the lo / lod islands of the rf enable group (island_on[1]).'
for n in D['atb_nodes']:
    if n['code'] == 33: n['island'] = 'rf'       # quadrature_bias = pt_lo_ext node (rf enable group)
    if n['code'] == 58: n['island'] = 'debug'    # vco_replica is on the debug island
for r in D['rules']:
    if r['id'] == 'usb_drive_vs_wired_path':     # HS data goes through pt_wiredtx + pt_usb_txdrv and FS/LS uses its word clock: the serializer may run, the TX pad branch may not
        r['then_all'] = [c for c in r['then_all'] if c[0] != 'wiredtx.state.state']
D['rules'].append({'id': 'forwarded_clock_needs_debug_island', 'class': 'legality',
    'if_any': [[f'debug.clk_select.{f}', 'in', ['aux_clk', 'wclk_in']] for f in ('wire_line', 'wire_sample', 'conv_sample', 'host_clk')],
    'then_all': [['debug.island_power.debug', 'eq', 1]],
    'reason': 'CP4-3 / TOP-25: the AUX_CLK receiver (forwarded wire clock, auxiliary clock) is on the debug island.'})
for r in D['rules']:
    if r['id'] == 'wiredtx_serial_needs_serial_branch':   # with a USB branch selected the serializer runs for the USB path and the TX pad stays off
        r['if_all'].append(['usbdrive.select.branch', 'eq', 'off'])
# ---------------------------------------------------------------- independent review of 3cff484 (scratch/reviews/dg6-review), 2026-11-14
A['cdr.ac3']['fields']['loop_bw']['maximum'] = 7        # finding 2: pt_cdr g[2:0], design point g = 7 (wired_rx README); was limited to 0..3
A['cdr.ac3']['fields']['loop_bw']['description'] = 'pt_cdr g[2:0]: pump unit-leg current / loop bandwidth code 0..7 (analog/wired_rx/README.md; reset 2).'
for k in range(8): A['cdr.phase_trim']['fields'][f'p{k}']['islands'] = ['pll', 'wired']   # finding 3: pt_ptrim is on the wired_cap island
for f in ('wire_line', 'wire_sample'): C['debug.clk_select']['fields'][f]['islands'] = ['pll']   # finding 10: the only consumer is pt_clockmux (pll)
A['detect.config']['fields']['low_threshold_code']['description'] = 'pt_detect det_thr1..0 (analog/wired_rx/PINS.md section 4); code 3 = disconnect level for the USB logic'
A['detect.config']['fields']['high_threshold_code']['description'] = 'pt_detect det_se1..0'
for r in D['rules']:                                    # finding 9: the two other users of the AUX_CLK receiver
    if r['id'] == 'lo_pads_vs_forwarded_clock': r['then_all'] += [['clockmux.config.ring_ref', 'ne', 'aux'], ['cdr.ac3.fll_ref_wck', 'eq', 0]]
    if r['id'] == 'forwarded_clock_needs_debug_island': r['if_any'] += [['clockmux.config.ring_ref', 'eq', 'aux'], ['cdr.ac3.fll_ref_wck', 'eq', 1]]
C['core.refchain']['description'] = C['core.refchain']['description'].replace('128 SCLK cycles (>= 12.8 us at <= 10 MHz, 25.6 us at 5 MHz)', '256 SCLK cycles (>= 10 us for SCLK <= 25 MHz; 51 us at the 5 MHz limit: the consumers switch on in the eighth SPI transaction after the commit)')
# ---------------------------------------------------------------- block_observation ledger: retired pads and renamed status bits
_OBS = {'pll_lock': 'pll_tx_lock', 'bias_ready': 'bandgap_ok', 'cdr_qualified': 'cdr_freq_ok', 'cdr_loss': 'cdr_fll_lost'}
_WIRE = {'pll_lock': 'pll_cdr_lock', 'cdr_qualified': 'cdr_freq_ok', 'cdr_loss': 'cdr_fll_lost', 'cdr_rx_state0': 'wrx_sig_ok', 'cdr_rx_state1': 'wrx_idle',
         'slicer_data': 'wrx_sig_ok', 'slicer_early': 'wrx_sig_ok', 'slicer_late': 'wrx_sig_ok', 'electrical_quiet': 'wrx_idle',
         'detect_event': 'detect_diff', 'detect_timeout': 'detect_diff'}
def _walk(x):
    if isinstance(x, dict):
        if x.get('path') == 'wdbg_obs':      # PD22: WDBG_OBS retired, wire_status is observed on DBG_OBS (codes 37+n)
            x['path'] = 'dbg_obs'; x['select'] = _WIRE.get(x['select'], x['select'])
            if x['select'] in ('wrx_sig_ok', 'wrx_idle', 'detect_diff'):
                x['note'] = (x.get('note', '') + ' r6: the per-sampler / detector status bit named here had no producer (D-STATUS); the nearest real status of the macro is observed instead.').strip()
        elif x.get('path') == 'dbg_obs': x['select'] = _OBS.get(x['select'], x['select'])
        elif x.get('path') == 'wclk_obs': x['path'] = 'clk_obs'      # PD22: WCLK_OBS folded into CLK_OBS
        if isinstance(x.get('expected'), str): x['expected'] = x['expected'].replace('WDBG_OBS', 'DBG_OBS').replace('WCLK_OBS', 'CLK_OBS')
        for v in x.values(): _walk(v)
    elif isinstance(x, list):
        for v in x: _walk(v)
_walk(D['block_observation'])
def _walk2(x):
    if isinstance(x, dict):
        m = x.get('mode')
        if isinstance(m, dict) and 'consolidation.pll.owner' in m:      # the shared-PLL owner field is gone: per-ring / LO fields
            m.pop('consolidation.pll.owner')   # (the ledger's mode check only knows debug controls; the ring / LO enables are analog fields)
        for k, v in list(x.items()):
            if isinstance(v, list): x[k] = [e for e in v if not (isinstance(e, dict) and e.get('select') == 'monitor_por_threshold')]   # ATB code 4 is reserved (audit F11)
        for v in x.values(): _walk2(v)
    elif isinstance(x, list):
        for v in x: _walk2(v)
_walk2(D['block_observation'])
