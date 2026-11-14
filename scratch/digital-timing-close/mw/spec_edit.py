#!/usr/bin/env python3
"""Mode-walk register-map rework (digital r6, 2026-11-13/14): one-off, re-runnable migration of
spec/analog-architecture.json:control_fields and spec/debug-controls.json. It always starts from the
git HEAD^{base} versions (BASE below), so running it twice gives the same files. After it:
python3 rtl/gen/gen_regfile.py.  Design notes: scratch/digital-timing-close/NOTES.md "r6"."""
import json, subprocess, sys
SV = '/home/ubuntu/svalbard'; P = SV + '/projects/programmable_transceiver_platform'
BASE = '8e5e71c'   # last commit before the rework
def load(rel): return json.loads(subprocess.check_output(['git', '-C', SV, 'show', f'{BASE}:projects/programmable_transceiver_platform/{rel}']))
arch = json.loads(open(P + '/spec/analog-architecture.json').read())     # only control_fields is replaced
A = load('spec/analog-architecture.json')['control_fields']
D = load('spec/debug-controls.json')
C = D['controls']

def num(bits, default=0, maximum=None, minimum=0, **kw):
    return dict(bits=bits, default=default, minimum=minimum, maximum=(1 << bits) - 1 if maximum is None else maximum, unit='code', **kw)
def enum(values, default, bits=None, **kw):
    b = bits or max(1, (len(values) - 1).bit_length())
    return dict(bits=b, default=default, values=values, **kw)
def keep(group, names, src=A):
    src[group]['fields'] = {k: v for k, v in src[group]['fields'].items() if k in names}
def drop(group, names, src=A):
    for n in names: del src[group]['fields'][n]

# ---------------------------------------------------------------- deletions (no consumer anywhere)
DEL_A = ['bias.trim', 'clockmux.state', 'clocktree.state', 'lna.gain', 'pga_i.gain', 'pga_i.offset', 'pga_i.state',
         'pga_q.gain', 'pga_q.offset', 'pga_q.state', 'quadrature.config', 'quadrature.state', 'refbuf.enable',
         'refinput.select', 'rxfilter_i.coefficients', 'rxfilter_i.state', 'rxfilter_q.coefficients', 'rxfilter_q.state',
         'tmds.config', 'tmds.idle', 'tmds.state', 'txfilter_i.coefficients', 'txfilter_i.state',
         'txfilter_q.coefficients', 'txfilter_q.state', 'txmix_i.enable', 'txmix_q.enable', 'txsum.enable',
         'wirepll.config', 'wirepll.state']
for g in DEL_A: del A[g]
for g in ['debug.wclk_obs', 'debug.wdbg_obs', 'consolidation.pll', 'consolidation.quadrature']: del C[g]
keep('adc_i.config', ['input_test']); keep('adc_q.config', ['input_test'])
keep('dac_i.config', ['hold_zero']); keep('dac_q.config', ['hold_zero'])
drop('debug.clk_select', ['rf_lo'], C)
C['debug.clk_select']['fallback_routes'] = [r for r in C['debug.clk_select']['fallback_routes']]
drop('debug.bias_override', ['master', 'rf', 'wired', 'pll', 'conv', 'debug'], C)
drop('debug.replica', ['vco_coarse', 'vco_divider_log2'], C)
drop('consolidation.bbfilter', ['bw', 'gain', 'finite_zeros', 'qtrim'], C)
C['consolidation.bbfilter']['description'] = ('Shared I/Q baseband filter mode (both channels): direction drives bbfilter en / dir_tx '
    '(c_bbfilter_x_en = direction != isolated, c_bbfilter_dir_tx = direction == tx or bb_tap inject_tx_mixer); rx_direct is filter-less RX; '
    'tx_dac_direct drives txmix sel_dac. Per-channel cutoff, gain, Q and DC-offset trims are bbfilter_i.trim / bbfilter_q.trim.')

# ---------------------------------------------------------------- always-on
C['core.aosc']['fields']['enable']['default'] = 0
C['core.aosc']['description'] = ('Always-on oscillator pt_aosc EN = macro port c_aosc_en (consumers: fc_src[4], the supply/clock monitor time base and '
    'debug observation). Live; RESET 0 (always-on audit F2: nothing needs the oscillator before SPI is up and the analog safe-state evidence is at EN = 0). '
    'Software can pulse the field 1 -> 0 -> 1 to leave the stuck state F3. While an RF payload runs (ENABLE=1 with payload_iq = 1) the register file forces the output to 0.')
C['core.refchain']['description'] += (' Bandgap-before-consumers interlock (always-on audit F5, in RTL: rtl/pt_ctl_decode.sv pt_bgap_interlock): the macro holds '
    'c_biasgen_ref_sel_vbg and every c_bias_dist_en_* at 0 until bgap_ena has been 1 for 128 SCLK cycles (>= 12.8 us at <= 10 MHz, 25.6 us at 5 MHz); '
    'bgap_ena = 0 clears it. The fields themselves read back as written.')
for n in D['atb_nodes']:
    if n['code'] == 4:
        n.update(name='reserved_4', hardware=False, note='RESERVED (always-on audit F11): was monitor_por_threshold. No hardware; never bind to the POR vcap / por_unbuf nodes. The code number is kept so later codes do not move; the register file rejects it on both buses.')
for g in D['atb_groups']['atb1']:
    g['codes'] = [c for c in g['codes'] if c != 4]

# ---------------------------------------------------------------- RF receive
A['lna.match']['fields']['gain_lo'] = num(1, description='lna port gain_lo = attenuator code bit 5 (RC-16j/p: current-steering attenuator, code = {gain_lo, att[4:0]}). Reset 0.')
A['lna.match']['description'] = 'LNA tank tune, input options and attenuator (RC-16e/g/j/p): ctrim ct0..ct3, rterm, se, attenuator code {gain_lo, att[4:0]}.'
A['lna.bias'] = dict(update='stopped', description='RC-16k LNA programmable bias.', fields=dict(
    lo=num(1, description='lna port lobias: 1 = reduced LNA bias (11.7 mA) for rf_tx / duplex. Commit rule lna_reduced_bias_with_tx: required whenever the RF driver is active with the LNA not off (power ceiling 240 mA). The published rxmix `hib` pin is driven with NOT lo (RC-16l).')))
A['lna.agc'] = dict(update='stopped', description='RXR-D2 fast gain (transport opcode 4) LNA table: attenuator code {gain_lo, att[4:0]} applied for LNA index 0..3 while an in-band gain is active (replaces the hard-wired DT-8 map, RC-16p: the level table of the current-steering attenuator is not final, so the table is programmable). PGA index 0..16 uses the bbfilter dB index directly.', fields={
    f'code{k}': num(6, 2 if k == 0 else 0, description=f'attenuator code for opcode-4 LNA index {k}' + (' (reset 2 = the old -6 dB step)' if k == 0 else '')) for k in range(4)})
for ch in 'iq':
    A[f'bbfilter_{ch}.trim'] = dict(update='live_trim', description=f'bbfilter_{ch} per-channel trims (MW-4, FS-2, analog/rf_rx/chip-top-pins.md section 3). Live.', fields=dict(
        cut=num(7, 8, live=True, description='cap code m = {bw[3:0], fc_fine[2:0]} (larger = lower cutoff), reset 8. Commit rule bbfilter_low_cap_needs_q: m <= 1 requires qt >= 6.'),
        gain=num(5, 2, maximum=16, live=True, description='PGA dB index 0..16 = -6..+42 dB in 3 dB steps; the macro LUT (rtl/pt_ctl_decode.sv, netlists.GAIN_TABLE) drives k = gain[5:0] and gainc[1:0]. Reset 2 = 0 dB (k = 4). The opcode-4 fast gain overrides it while active.'),
        qt=num(4, 6, live=True, description='Q trim qt3..qt0, reset 6.'),
        dcf=num(9, 0, live=True, direct=True, description='fine DC-offset DAC, sign-magnitude: bit 8 = dcf_sign, bits 7:0 = dcf7..dcf0 (about 0.4 mV/LSB). Direct live trim.')))
A['adc.config'] = dict(update='stopped', description='Both ADCs (staged AP4 contract, analog/converters/INTEGRATION.md).', fields=dict(
    interleave=num(1, description='ILEN of adc_i and adc_q: 1 = two interleaved cores (40 MS/s at 40 MHz), 0 = core A only. The macro takes core A on even and core B on odd CONV_CLK edges counted from the start.'),
    acquisition=num(2, description='ACQ1:0 of both ADCs: 0 nominal window, 1 short, 2 long, 3 = CLK high time.')))

# ---------------------------------------------------------------- RF transmit
A['rfdriver.gain']['fields']['code'] = num(4, 12, description='rfdriver ports g3..g0 (was the top nibble of an 8-bit code, default 192 -> 12).')

# ---------------------------------------------------------------- LO
A['rfpll.config'] = dict(update='stopped', description='RF LO (MW-1a, MW-7a, analog/timing/LO-INTEGRATION.md section 4). Integer-N under register control: f_LO = 2 N f_ref; band search by software with freq_count source lc_prescale (lo_mmd.FB).', fields=dict(
    lo_mode=enum(['off', 'external_passive', 'internal', 'external_cml'], 'off', description='pt_lo_ext EXT/INT/CMLSEL: off 000 (LO nodes clamped), external_passive 100, internal 010 (on-chip QVCO), external_cml 111 (external LO through the CML driver, die-1 baseline). In both external modes REF_IN / AUX_CLK carry the LO: the macro forces their clock receivers off. Break-before-make; change only with the mixers disabled, wait >= 20 us.'),
    vco_coarse=num(4, description='pt_lc_qvco5 BAND[3:0], 15 = lowest frequency.'),
    lo_n=num(6, description='pt_lo_mmd N[5:0], valid 16..63 (VCO/FB = 2 N); 0 at reset (divider off anyway).'),
    lo_icp=num(2, description='pt_lo_pfdcp ICP[1:0]: Icp = 25 uA x (1 + ICP0 + 2 ICP1); 0 = lowest loop gain.'),
    lo_preset=num(1, description='pt_lo_pfdcp PRE: 1 = PFD held in reset, VTUNE at the preset voltage (band search).'),
    atb_enable=num(1, description='pt_lc_qvco5 ATB_EN (VTUNE / tail taps onto the analog test bus).')))

# ---------------------------------------------------------------- clocks
A['clockmux.config'] = dict(update='stopped', description='Clock selects that are not in debug.clk_select (MW-2a, analog/timing/README.md register-map glue). One-hot decode in the macro; 0 = stopped; switch through stopped.', fields=dict(
    ring_ref=enum(['stopped', 'ref', 'aux', 'h2d'], 'stopped', description='ring-PLL reference clockmux PS_REF/PS_AUX/PS_H2D (PREF feeds both rings). h2d = host_follow reference.'),
    host_prescale=enum(['stopped', 2, 4, 8, 16], 'stopped', description='pt_prescale (line ring -> HOST_INT and the macro ct_wclk): EN + one-hot D2/D4/D8/D16.'),
    conv_prescale=enum(['stopped', 2, 4, 8, 16], 'stopped', description='prescale_conv (line ring -> CONV_INT).'),
    hf_prescale=enum(['stopped', 2, 4, 8, 16], 'stopped', description='prescale_hf (CDR ring -> HF, host_follow).')))
A['ring_l.config'] = dict(update='stopped', description='Line / TX ring PLL pt_pll_ring_core instance pll_tx (MW-16, WT26, D-PLLEN).', fields=dict(
    enable=num(1, description='ring enable. c_pll_tx_en = enable & island_on[pll] & vreg_tx_ok.'),
    modulus=enum([16, 8, 4], 16, description='feedback modulus: N8 = (8), N4 = (4), neither = 16.'),
    band=num(1, 1, description='BAND (AC3-W13), reset 1 = high band.')))
A['ring_c.config'] = dict(update='stopped', description='CDR ring PLL pt_pll_ring instance pll_cdr and pt_cdr mode (MW-10, D-HF).', fields=dict(
    line_pll=num(1, description='pt_cdr pfd_mode: 0 = wired CDR (ring enabled by cdr.state = active), 1 = line PLL / host_follow: the ring and pt_cdr are enabled by this bit alone (cdr.state may stay off, so the RF/wired payload exclusion rule does not block host_follow in RF modes).'),
    modulus=enum([16, 8, 4, 10, 5], 16, description='feedback modulus one-hot N4/N8/N5/N10 (16 = none).'),
    band=num(1, 1, description='BAND, reset 1 = high band.'),
    kp=num(3, description='pt_pll_ring KP[2:0] CDR proportional gain; 0 = proportional path off.')))
A['refinput.state']['description'] = 'REF_IN receiver rx_ref_in (always-on rail): c_rx_ref_en = (state == active) and lo_mode is not external.'

# ---------------------------------------------------------------- wired receive
A['ctle.config'] = dict(update=A['ctle.config'].get('update', 'stopped'), fields=dict(
    peak=num(3, description='ctle_peak2..0.'), lf_zero=num(3, description='lf_zero2..0 (IX-13 low-frequency zero).')))
t = A['termination.config']['fields']
for n in ('n_load', 'trim_n', 'trim_p'): del t[n]
t['hs_enable'] = num(1, description='HS pair bias on (pt_termination hs_en; without it the CTLE input sits at 0 V, MW-9).')
t['hs_term_enable'] = num(1, description='HS pair termination on (hs_term_en).')
t['hs_trim'] = num(4, 5, description='HS pair termination trim hs_trim3..0, reset 5 (PD27).')
d = A['detect.config']['fields']
del d['current_code']
d['high_threshold_code'] = num(2, description='det_thr1..0'); d['low_threshold_code'] = num(2, description='det_se1..0')
A['slicer.offset'] = dict(update='live_trim', description='Per-sampler offset trims (MW-32): 10 bits per sampler {f3,f2,f1,f0,n2,n1,n0,p2,p1,p0}. Direct live trims.', fields={
    f'trim_{s}{k}': num(10, live=True, direct=True) for s in 'de' for k in range(4)})
A['slicer.threshold'] = dict(update='live_trim', description='IX-10 edge-sampler threshold DAC pt_vthdac and per-sampler threshold select (100BASE-TX raw path). vth_a / vth_b can also be loaded in band by the IX-11 fast threshold command.', fields=dict(
    vth_enable=num(1, description='pt_vthdac vth_en'),
    vth_a=num(8, 128, live=True, direct=True, description='threshold DAC A'), vth_b=num(8, 128, live=True, direct=True, description='threshold DAC B'),
    **{f'vsel_e{k}': num(2, description=f'slicer vsel_e{k}_1:0') for k in range(4)}))
A['slicer.capture'] = dict(update='stopped', description='pt_wrx_cap static controls.', fields=dict(
    rcsel=num(1, description='RCS'),
    rate_mode=enum(['quarter', 'half', 'full'], 'quarter', description='RX bits per ring cycle 4 / 2 / 1: capture B2 = half, B1 = full; pt_wordclk D10 = half, D20 = full.')))
del A['cdr.config']['fields']['cap_rcsel']
drop('cdr.config', ['burst_acquire_rows', 'burst_enable', 'burst_min_edges'])

# ---------------------------------------------------------------- wired transmit
w = A['wiredtx.config']['fields']
del w['source_termination_enable']
w['post_polarity'] = num(1, description='POST_POL post-cursor polarity (IX-9).')
A['txpad.config']['fields']['term_request'] = num(1, description='TX pad termination request (interlock REQ_TERM).')
del A['usbhs.config']['fields']['disconnect_code'], A['usbhs.config']['fields']['rx_enable'], A['usbhs.config']['fields']['squelch_code']

# ---------------------------------------------------------------- observation
co = C['debug.clk_obs']['fields']
co['source'].pop('forbidden', None)
co['divider_log2'] = dict(bits=3, default=0, minimum=0, maximum=7, unit='log2')
C['debug.clk_obs']['description'] = ('CLK_OBS source and power-of-two divider (pt_clk_obs16 on the debug island). off = pad tristated and the node pulled down (c_clk_obs_off). '
    'Fast sources (wire_line, wire_sample, ref_in, aux_clk, wclk_in, pll_vco, cdr_recovered) go through their own /4 prescaler pt_obs_pre4, enabled one-hot with the source (PD22: WCLK_OBS is folded into CLK_OBS). '
    'Codes 15-17 select input 15 (characterization cells, not placed on die 1: reads low).')
C['debug.dbg_obs']['description'] = ('DBG_OBS0/1 digital status mux: 0 = tristate, 1 = constant 0, 2 = constant 1, 3 = commit toggle, 4+n = obs_status[n], 36 = live combined reset level rst_n, '
    '37+n = wire_status[n] (PD22: WDBG_OBS is folded into DBG_OBS). Any reset returns the select to 0.')
for s in ('sel0', 'sel1'): C['debug.dbg_obs']['fields'][s]['maximum'] = 36 + 16

# ---------------------------------------------------------------- islands of blocks
bi = D['block_islands']
bi.update({'bbfilter_i': ['rf'], 'bbfilter_q': ['rf'], 'adc': ['conv'], 'ring_l': ['pll'], 'ring_c': ['pll'], 'refinput': [], 'usbfs': ['wired']})

# ---------------------------------------------------------------- rules / lists
def strip_conds(rule, pred):
    for k in ('if_any', 'if_all', 'then_all'):
        if rule.get(k): rule[k] = [c for c in rule[k] if not pred(c[0])]
gone = lambda n: n.rsplit('.', 1)[0] not in {**A, **C} or n.rsplit('.', 1)[1] not in {**A, **C}[n.rsplit('.', 1)[0]]['fields']
rules = []
for r in D['rules']:
    if r['id'] in ('pll_state_needs_owner',): continue
    strip_conds(r, gone)
    assert r['then_all'] and (r.get('if_any') or r.get('if_all')), r['id']
    rules.append(r)
rules += [
    {'id': 'lna_reduced_bias_with_tx', 'class': 'legality', 'if_any': [['rfdriver.state.state', 'eq', 'active']], 'if_all': [['lna.state.state', 'ne', 'off']], 'then_all': [['lna.bias.lo', 'eq', 1]],
     'reason': 'RC-16k/q: reduced LNA bias whenever the TX chain is on (240 mA ceiling).'},
    {'id': 'bbfilter_i_low_cap_needs_q', 'class': 'legality', 'if_any': [['bbfilter_i.trim.cut', 'in', [0, 1]]], 'then_all': [['bbfilter_i.trim.qt', 'nin', [0, 1, 2, 3, 4, 5]]], 'reason': 'FS-2 stability validator: cap code <= 1 requires q_trim >= 6.'},
    {'id': 'bbfilter_q_low_cap_needs_q', 'class': 'legality', 'if_any': [['bbfilter_q.trim.cut', 'in', [0, 1]]], 'then_all': [['bbfilter_q.trim.qt', 'nin', [0, 1, 2, 3, 4, 5]]], 'reason': 'FS-2 stability validator.'},
    {'id': 'lo_internal_needs_valid_n', 'class': 'legality', 'if_any': [['rfpll.state.state', 'eq', 'active']], 'if_all': [['rfpll.config.lo_mode', 'eq', 'internal']], 'then_all': [['rfpll.config.lo_n', 'nin', list(range(16))]], 'reason': 'pt_lo_mmd: N < 16 is not a valid ratio.'},
]
D['rules'] = rules
D['break_before_make'] = [n for n in D['break_before_make'] if not gone(n)] + ['rfpll.config.lo_mode', 'clockmux.config.ring_ref',
    'clockmux.config.host_prescale', 'clockmux.config.conv_prescale', 'clockmux.config.hf_prescale']
ff = D['fault_forced']['fields']
for k in ('txmix_i', 'txmix_q', 'txsum'):
    del ff[f'{k}.enable.enable']; ff[f'{k}.state.state'] = 'off'
ht = D['hardware_trim']
ht['fields'] = {k: v for k, v in ht['fields'].items() if not gone(k) and k not in ('rfdriver.gain.code', 'detect.config.high_threshold_code', 'detect.config.low_threshold_code') and not k.startswith('rfpll.config.')}
ht['forbidden'] = {k: v for k, v in ht['forbidden'].items() if not gone(k)}
exec(open(SV + '/scratch/digital-timing-close/mw/spec_edit2.py').read()) if __import__('os').path.exists(SV + '/scratch/digital-timing-close/mw/spec_edit2.py') else None
arch['control_fields'] = A
open(P + '/spec/analog-architecture.json', 'w').write(json.dumps(arch, indent=2, ensure_ascii=True) + '\n')
open(P + '/spec/debug-controls.json', 'w').write(json.dumps(D, indent=2, ensure_ascii=True) + '\n')
print('spec written:', len(A), 'analog groups,', len(C), 'debug groups')
