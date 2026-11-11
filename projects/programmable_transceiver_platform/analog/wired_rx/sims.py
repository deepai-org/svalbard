from pathlib import Path
"""Testbenches for the wired-receive family (schematic or extracted netlist).

Each `tb_<block>` returns a list of (case_name, deck_text, analyse_fn).  The
deck instantiates the block by port *name*, so the same bench runs on the
schematic (.spice) and on the Magic extraction (.ext.spice).  analyse_fn
receives (log_text, data_path) and returns a metrics dict.
"""
import math
import numpy as np

from wrx_flow import sim_header, parse_meas


def inst(sub, mapping, name='XDUT'):
    missing = [p for p in sub.ports if p not in mapping]
    if missing:
        raise KeyError(f'{sub.name}: unmapped ports {missing}')
    return f'{name} ' + ' '.join(mapping[p] for p in sub.ports) + f' {sub.name}'


def deck(sub, netfile, body, control, corner='typical', temp=27, title='tb'):
    return '\n'.join([f'* {title}', sim_header(corner, temp), f'.include {netfile}', body,
                      '.control', control, '.endc', '.end', ''])


def load(path):
    d = np.loadtxt(path)
    return d


def at(d, col, t):
    i = min(np.searchsorted(d[:, 0], t), len(d) - 1)
    return float(d[i, col])


def crossings(t, v, level, rising=True):
    s = v - level
    idx = np.where((s[:-1] < 0) & (s[1:] >= 0))[0] if rising else np.where((s[:-1] > 0) & (s[1:] <= 0))[0]
    return [t[i] + (t[i + 1] - t[i]) * (-s[i]) / (s[i + 1] - s[i]) for i in idx]


def pwl(points):
    return 'PWL(' + ' '.join(f'{t:.9e} {v:.5g}' for t, v in points) + ')'   # ps resolution on long windows


def step_src(name, node, seq, vdd, t_edge=100e-12):
    """seq: list of (t, bit). Returns a PWL voltage source line."""
    pts = [(0, vdd * seq[0][1])]
    for t, b in seq[1:]:
        pts += [(t, pts[-1][1]), (t + t_edge, vdd * b)]
    return f'{name} {node} 0 {pwl(pts)}'


# ------------------------------------------------------------------ termination
def tb_termination(sub, netfile, corner='typical', temp=27, vdd=3.3):
    V = vdd
    # mode sequence: off(en=0) -> 01 (vcm) -> 11 (gnd) -> 10 (diff) -> en=0
    t = [0, 50e-9, 300e-9, 500e-9, 700e-9]
    en = [(0, 0), (t[1], 1), (t[4], 0)]
    m0 = [(0, 0), (t[1], 1), (t[3], 0)]
    m1 = [(0, 0), (t[2], 1)]
    m = dict(VDD_WIRE_SW='vdd', VSS='0', term_en='en', term_mode0='m0', term_mode1='m1',
             TERM_ENABLE='te', DIFF_ENABLE='de', TERM_VCM='vcm',
             term_trim0='vdd', term_trim1='0', term_trim2='vdd', TERM_TRIM0='tr0', TERM_TRIM1='tr1', TERM_TRIM2='tr2',
             # r3 HS pair (pad_hspad): hs_en with the USB enable, hs_term_en from 100 ns, trim code 0101
             hs_en='en', hs_term_en='hte', hs_trim0='vdd', hs_trim1='0', hs_trim2='vdd', hs_trim3='0',
             HS_TERM_ENABLE='hte_o', HS_TERM_TRIM0='htr0', HS_TERM_TRIM1='htr1', HS_TERM_TRIM2='htr2',
             HS_TERM_TRIM3='htr3', HS_TERM_VCM='hvcm', HS_VBIAS='hvb')
    m = {k: v for k, v in m.items() if k in sub.ports}       # r1 netlists have no trim ports
    hs = 'HS_VBIAS' in sub.ports
    body = '\n'.join([
        f'VDD vdd 0 {V}', step_src('VEN', 'en', en, V), step_src('VM0', 'm0', m0, V), step_src('VM1', 'm1', m1, V),
        # pad bank model on TERM_VCM: two legs of 24 ohm + switch into a 25 ohm (100 ohm diff, AC-coupled) line;
        # common-mode load only: legs are a DC-isolated source here, plus 17.8 mA HS driver current in USB mode
        'CL1 te 0 300f', 'CL2 de 0 200f',
        'Iusb 0 vcm PWL(0 0 400n 0 400.1n 17.8m 450n 17.8m 450.1n 0)',
        # HS loads: pad bank gates (~0.3 pF each), 2 x 40 kohm RX bias resistors behind the MIM (DC 0), 1 pF CM on VCM
        *(['VHTE hte 0 PWL(0 0 100n 0 100.1n {V})'.format(V=V), 'CH1 hte_o 0 300f', 'CH2 hvcm 0 1p', 'CH3 hvb 0 0.4p']
          + [f'CHT{k} htr{k} 0 300f' for k in range(4)] if hs else []),
        inst(sub, m)])
    ctl = '\n'.join([
        'tran 0.2n 900n', 'set wr_singlescale', 'wrdata tran.txt v(vcm) v(te) v(de) i(VDD)',
        'meas tran vcm_div find v(vcm) at=290n', 'meas tran vcm_gnd_17m8 find v(vcm) at=440n',
        'meas tran vcm_gnd find v(vcm) at=390n', 'meas tran te_div find v(te) at=290n', 'meas tran de_div find v(de) at=290n',
        'meas tran te_gnd find v(te) at=440n', 'meas tran de_diff find v(de) at=690n', 'meas tran te_diff find v(te) at=690n',
        'meas tran vcm_diff find v(vcm) at=690n', 'meas tran idd_div avg i(VDD) from=250n to=290n',
        'meas tran idd_off avg i(VDD) from=800n to=890n', 'meas tran idd_reset avg i(VDD) from=10n to=45n',
        'meas tran te_off find v(te) at=890n', 'meas tran vcm_off find v(vcm) at=890n',
        'meas tran t_settle when v(vcm)=1.14 rise=1 td=50n'] +
        (['meas tran tr0_on find v(tr0) at=290n', 'meas tran tr1_on find v(tr1) at=290n',
          'meas tran tr2_on find v(tr2) at=290n', 'meas tran tr0_off find v(tr0) at=890n'] if 'TERM_TRIM0' in sub.ports else []) +
        (['meas tran hvcm_on find v(hvcm) at=290n', 'meas tran hvb_on find v(hvb) at=290n',
          'meas tran hte_on find v(hte_o) at=290n', 'meas tran hte_pre find v(hte_o) at=90n',
          'meas tran htr0_on find v(htr0) at=290n', 'meas tran htr1_on find v(htr1) at=290n',
          'meas tran htr2_on find v(htr2) at=290n', 'meas tran htr3_on find v(htr3) at=290n',
          'meas tran htr0_pre find v(htr0) at=90n', 'meas tran hvcm_off find v(hvcm) at=890n',
          'meas tran hvb_off find v(hvb) at=890n', 'meas tran hte_off find v(hte_o) at=890n',
          'meas tran t_hvb when v(hvb)=0.9 rise=1 td=50n'] if 'HS_VBIAS' in sub.ports else []))

    def analyse(log, data):
        r = parse_meas(log)
        r['vcm_gnd_ron_ohm'] = (r['vcm_gnd_17m8'] - r['vcm_gnd']) / 17.8e-3 if 'vcm_gnd_17m8' in r else None
        r['vcm_settle_ns'] = (r['t_settle'] - 50e-9) * 1e9 if 't_settle' in r else None
        r['pass'] = bool(abs(r.get('vcm_div', 0) - 1.2) < .1 and r.get('te_div', 0) > .9 * V and r.get('de_div', 1) < .1
                         and r.get('vcm_gnd_ron_ohm', 99) < 3 and r.get('de_diff', 0) > .9 * V and r.get('te_diff', 1) < .1
                         and r.get('te_off', 1) < .1 and abs(r.get('idd_off', 1)) < 1e-6)
        if 'HS_VBIAS' in sub.ports:      # r3 HS pair: PD27 VCM 0.3-0.5 V; VBIAS 0.9-1.1 V (CTLE r2 CM window is
            # 0.8-1.2 V at ss, 0.8-1.4/1.6 V tt/ff); trim 0101 gated by the enables
            r['hvb_settle_ns'] = (r['t_hvb'] - 50e-9) * 1e9 if 't_hvb' in r else None
            r['pass'] = bool(r['pass'] and 0.3 <= r.get('hvcm_on', 0) <= 0.5 and 0.9 <= r.get('hvb_on', 0) <= 1.1
                             and r.get('hte_on', 0) > .9 * V and r.get('hte_pre', 1) < .1 and r.get('htr0_pre', 1) < .1
                             and r.get('htr0_on', 0) > .9 * V and r.get('htr1_on', 1) < .1 and r.get('htr2_on', 0) > .9 * V
                             and r.get('htr3_on', 1) < .1 and r.get('hvcm_off', 1) < .02 and r.get('hvb_off', 1) < .02
                             and r.get('hte_off', 1) < .1)
        if 'TERM_TRIM0' in sub.ports:    # r2: trim code 101 passed while enabled, all low when disabled
            r['pass'] = bool(r['pass'] and r.get('tr0_on', 0) > .9 * V and r.get('tr1_on', 1) < .1
                             and r.get('tr2_on', 0) > .9 * V and r.get('tr0_off', 1) < .1)
        return r
    return [('modes', deck(sub, netfile, body, ctl, corner, temp, 'termination modes'), analyse)]


# ------------------------------------------------------------------ rxlevel
def tb_rxlevel(sub, netfile, corner='typical', temp=27, vdd=3.3):
    V = vdd
    en = [(0, 0), (20e-9, 1), (300e-9, 0)]
    half = [(0, 0), (100e-9, 1), (200e-9, 0)]
    m = dict(VDD_WIRE_SW='vdd', VSS='0', rxlevel_en='en', rxlevel_half='half',
             DIV_ENABLE='div', BYPASS_ENABLE='byp')
    body = '\n'.join([f'VDD vdd 0 {V}', step_src('VEN', 'en', en, V), step_src('VH', 'half', half, V),
                      # load: pad gates (4x 20/0.7 6V NMOS per leg x2 legs for bypass; 1x for divider select+ground)
                      'CB byp 0 1p', 'CD div 0 0.4p', inst(sub, m)])
    ctl = '\n'.join(['tran 0.1n 400n', 'set wr_singlescale', 'wrdata tran.txt v(byp) v(div) i(VDD)',
                     'meas tran byp_on find v(byp) at=90n', 'meas tran div_on find v(div) at=190n',
                     'meas tran t_byp_fall when v(byp)=0.3 fall=1', 'meas tran t_div_rise when v(div)=0.3 rise=1',
                     'meas tran t_div_fall when v(div)=0.3 fall=1', 'meas tran t_byp_rise2 when v(byp)=0.3 rise=2',
                     'meas tran byp_off find v(byp) at=390n', 'meas tran div_off find v(div) at=390n',
                     'meas tran idd_static avg i(VDD) from=150n to=190n', 'meas tran idd_off avg i(VDD) from=350n to=390n',
                     'meas tran both_on_max max v(byp) from=95n to=110n'])

    def analyse(log, data):
        r = parse_meas(log)
        r['bbm_gap_byp_to_div_ns'] = (r['t_div_rise'] - r['t_byp_fall']) * 1e9 if 't_div_rise' in r else None
        r['bbm_gap_div_to_byp_ns'] = (r['t_byp_rise2'] - r['t_div_fall']) * 1e9 if 't_byp_rise2' in r else None
        r['pass'] = bool(r.get('byp_on', 0) > .9 * V and r.get('div_on', 0) > .9 * V
                         and (r['bbm_gap_byp_to_div_ns'] or -1) > 0 and (r['bbm_gap_div_to_byp_ns'] or -1) > 0
                         and r.get('byp_off', 1) < .1 and r.get('div_off', 1) < .1 and abs(r.get('idd_off', 1)) < 1e-6)
        return r
    return [('bbm', deck(sub, netfile, body, ctl, corner, temp, 'rxlevel break-before-make'), analyse)]


# ------------------------------------------------------------------ rxselect / wmon_sel (TG muxes)
def _mux_ac(sub, netfile, mapping_on, src_on, src_off, out, load_f, corner, temp, vdd, cm, title):
    body = '\n'.join([f'VDD vdd 0 {vdd}', *[f'V{k} {k} 0 {v}' for k, v in mapping_on['ctl'].items()],
                      f'Vsrc_on s_on 0 DC {cm} AC 1', f'Rsrc_on s_on {src_on} 25', f'Vsrc_off s_off 0 DC {cm} AC 0',
                      f'Rsrc_off s_off {src_off} 25', f'CL {out} 0 {load_f}', *mapping_on['extra'],
                      inst(sub, mapping_on['map'])])
    ctl = '\n'.join(['op', f'print v({out}) i(VDD)', 'ac dec 40 1e6 1e11', f'let g=db(v({out}))',
                     'meas ac g0 find g at=1e6', 'let gt=g0-3', 'meas ac bw3db when g=gt fall=1',
                     'meas ac g1g find g at=1e9', 'set wr_singlescale', f'wrdata ac.txt db(v({out}))'])
    return deck(sub, netfile, body, ctl, corner, temp, title)


def tb_rxselect(sub, netfile, corner='typical', temp=27, vdd=3.3):
    cases = []
    for direct, on, off, cm in ((0, ('CTLE_P', 'ctp'), ('RX_P', 'rxp'), 1.0), (1, ('RX_P', 'rxp'), ('CTLE_P', 'ctp'), .2)):
        m = dict(VDD_WIRE_SW='vdd', VSS='0', rxselect_en='en', rxselect_direct='dir', CTLE_P='ctp', CTLE_N='ctn',
                 RX_P='rxp', RX_N='rxn', SL_P='slp', SL_N='sln')
        spec = dict(ctl={'en': vdd, 'dir': vdd * direct}, map=m,
                    extra=[f'VCN ctn 0 {cm}', f'VRN rxn 0 {cm}', 'CLN sln 0 150f'])
        d = _mux_ac(sub, netfile, spec, on[1], off[1], 'slp', '150f', corner, temp, vdd, cm, f'rxselect dir={direct}')

        def analyse(log, data, cm=cm):
            r = parse_meas(log)
            r['pass'] = bool(r.get('g0', -99) > -1 and r.get('bw3db', 0) > 1.5e9)
            return r
        cases.append((f'ac_direct{direct}', d, analyse))
    # disabled: isolation and clamp
    m = dict(VDD_WIRE_SW='vdd', VSS='0', rxselect_en='en', rxselect_direct='dir', CTLE_P='ctp', CTLE_N='ctn',
             RX_P='rxp', RX_N='rxn', SL_P='slp', SL_N='sln')
    spec = dict(ctl={'en': 0, 'dir': 0}, map=m, extra=['VCN ctn 0 1.0', 'VRN rxn 0 1.0', 'CLN sln 0 150f'])
    d = _mux_ac(sub, netfile, spec, 'ctp', 'rxp', 'slp', '150f', corner, temp, vdd, 1.0, 'rxselect off')

    def off(log, data):
        r = parse_meas(log)
        r['pass'] = bool(r.get('g1g', 0) < -20)
        return r
    cases.append(('ac_off', d, off))
    return cases


def tb_wmon_sel(sub, netfile, corner='typical', temp=27, vdd=3.3):
    m = dict(VDD_WIRE_SW='vdd', VSS='0', wmon_en='en', wmon_sel0='s0', wmon_sel1='s1', RX_P='rxp', RX_N='rxn',
             CTLE_P='ctp', CTLE_N='ctn', WMON_IN='wm')
    cases = []
    for code, on, cm in ((0, 'rxp', .2), (2, 'ctp', 1.0), (3, 'ctn', 1.0)):
        others = [n for n in ('rxp', 'rxn', 'ctp', 'ctn') if n != on]
        spec = dict(ctl={'en': vdd, 's0': vdd * (code & 1), 's1': vdd * (code >> 1)}, map=m,
                    extra=[f'V{n} {n} 0 {cm}' for n in others[1:]])
        d = _mux_ac(sub, netfile, spec, on, others[0], 'wm', '300f', corner, temp, vdd, cm, f'wmon_sel {code}')

        def analyse(log, data):
            r = parse_meas(log)
            r['pass'] = bool(r.get('g0', -99) > -1 and r.get('bw3db', 0) > 300e6)
            return r
        cases.append((f'ac_sel{code}', d, analyse))
    spec = dict(ctl={'en': 0, 's0': 0, 's1': 0}, map=m, extra=['Vrxn rxn 0 1', 'Vctn ctn 0 1'])
    d = _mux_ac(sub, netfile, spec, 'rxp', 'ctp', 'wm', '300f', corner, temp, vdd, 1.0, 'wmon_sel off')

    def off(log, data):
        r = parse_meas(log)
        r['pass'] = bool(r.get('g1g', 0) < -20)
        return r
    cases.append(('ac_off', d, off))
    return cases


# ------------------------------------------------------------------ ctle
def tb_ctle(sub, netfile, corner='typical', temp=27, vdd=3.3, cm=1.0):
    cases = []
    base = dict(VDD_WIRE_SW='vdd', VSS='0', IBIAS='ib', ctle_en='en', wire_ctle_bypass='byp', ctle_peak0='p0',
                ctle_peak1='p1', ctle_peak2='p2', RX_P='inp', RX_N='inn', CTLE_P='outp', CTLE_N='outn',
                atb_ctle_pbias='pb', atb_ctle_src='src', lf_zero0='lz0', lf_zero1='lz1', lf_zero2='lz2')
    ncode = 8 if 'ctle_peak2' in sub.ports else 4       # r2: 3-bit peaking code
    nlfz = 8 if 'lf_zero0' in sub.ports else 0          # r3 (IX-13): LF zero bank at peak code 7
    for en, byp, code, lfz in ([(1, 0, k, 0) for k in range(ncode)] + [(0, 1, 0, 0), (0, 0, 0, 0)]
                               + [(1, 0, 7, z) for z in range(1, nlfz)] + ([(1, 0, 0, 7)] if nlfz else [])):
        body = '\n'.join([f'VDD vdd 0 {vdd}', 'RIB vdd ib 260k', f'VEN en 0 {en * vdd}', f'VBY byp 0 {byp * vdd}',
                          f'VP0 p0 0 {(code & 1) * vdd}', f'VP1 p1 0 {((code >> 1) & 1) * vdd}', f'VP2 p2 0 {(code >> 2) * vdd}',
                          *[f'VLZ{j} lz{j} 0 {((lfz >> j) & 1) * vdd}' for j in range(3)],
                          f'VIP vip 0 DC {cm} AC 0.5', f'VIN vin 0 DC {cm} AC -0.5',
                          'RSP vip inp 25', 'RSN vin inn 25',
                          'CLP outp 0 150f', 'CLN outn 0 150f', inst(sub, base)])
        ctl = '\n'.join(['op', 'print v(outp) v(outn) v(src) v(pb) i(VDD)', 'let idd=-i(VDD)', 'print idd',
                         'ac dec 40 1e4 2e10', 'let g=db(v(outp)-v(outn))',
                         'meas ac gdc find g at=1e6', 'meas ac gpk max g', 'meas ac glf find g at=1e4',
                         'meas ac g100m find g at=1e8', 'let gz=glf+3', 'meas ac fz when g=gz rise=1',
                         'meas ac g625 find g at=625e6', 'meas ac g1g25 find g at=1.25e9', 'meas ac g2g5 find g at=2.5e9',
                         'let gt=gdc-3', 'meas ac bw3db when g=gt fall=last',
                         'set wr_singlescale', 'wrdata ac.txt g'])

        def analyse(log, data, en=en, byp=byp, lfz=lfz, code=code):
            r = parse_meas(log)
            m = __import__('re').search(r'idd = ([-+0-9.eE]+)', log)
            r['idd_a'] = float(m.group(1)) if m else None
            if en and lfz:
                # IX-13: zero (gain 3 dB above the 10 kHz level) 4.4-35 MHz for codes 1-7 at peak code 7; the LF->100 MHz
                # boost stays >= 12 dB; monotonicity is judged across codes in the evidence summary
                r['boost_lf_db'] = r.get('g100m', 0) - r.get('glf', 0)
                r['boost_db'] = r.get('gpk', 0) - r.get('glf', 0)
                r['pass'] = bool((code == 0) or (3e6 < r.get('fz', 0) < 40e6 and r['boost_db'] > 12))
            elif en:
                r['peaking_db'] = r.get('gpk', 0) - r.get('gdc', 0)
                r['pass'] = bool(-12 < r.get('gdc', -99) < 4 and r.get('g1g25', -99) > -3 and (r['idd_a'] or 0) < 12e-3)
            elif byp:
                r['pass'] = bool(r.get('gdc', -99) > -2 and r.get('bw3db', 0) > 1.5e9)
            else:
                r['pass'] = bool(r.get('gdc', 0) < -30 and abs(r['idd_a'] or 1) < 1e-6)
            return r
        name = (f'ac_code{code}' + (f'_lfz{lfz}' if lfz else '')) if en else ('ac_bypass' if byp else 'ac_off')
        cases.append((name, deck(sub, netfile, body, ctl, corner, temp, f'ctle {name}'), analyse))
    return cases


# ------------------------------------------------------------------ slicer
def _slicer_body(sub, per, vd, cm, trims, vdd, n_bits=24, seed=1, ramp=None, tstop=None, delay=0., rep=1, aux=None, vt=None):
    # r6 (IX-10): aux = {edge sampler: select (0 off, 1 VTH_A, 2/3 VTH_B)}; vt = {VTAP/VTAN/VTBP/VTBN: volts}
    # (default every line at the DAC mid-scale CM 0.8 V); pre-r6 netlists have no such ports
    # per = 2 quarter-rate UI; the eight ring clocks CKPk (period 2*per) are k*per/4 apart.
    # rep: line bit length in quarter-rate UI (1 quarter, 2 half, 4 full rate at the same ring frequency)
    m = dict(VDD_WIRE_SW='vdd', VSS='0', slicer_en='en', SL_P='inp', SL_N='inn', QCK='qck',
             D0='d0', E0='e0', D1='d1', E1='e1', D2='d2', E2='e2', D3='d3', E3='e3')
    m.update({f'CKP{k}': ('ck0' if k == 0 else f'ckp{k}') for k in range(8)})
    for port in sub.ports:          # trim_<sampler>_<bit> (r3: per sampler, p0..p2 / n0..n2)
        if port.startswith('trim_'):
            _, s, b = port.split('_')
            m[port] = 'tvdd' if trims.get(s, {}).get(b) else '0'
        elif port.startswith('vsel_'):
            _, s, b = port.split('_')
            m[port] = 'tvdd' if ((aux or {}).get(s, 0) >> int(b)) & 1 else '0'
        elif port in ('VTAP', 'VTAN', 'VTBP', 'VTBN'):
            m[port] = port.lower()
    P = 2 * per
    tr = P / 40
    lines = [f'VDD vdd 0 {vdd}', f'VT tvdd 0 {vdd}', f'VEN en 0 PWL(0 0 0.5n {vdd})']
    lines += [f'V{q} {q.lower()} 0 {(vt or {}).get(q, 0.8)}' for q in ('VTAP', 'VTAN', 'VTBP', 'VTBN') if q in sub.ports]
    for k in range(8):
        name = 'ck0' if k == 0 else f'ckp{k}'
        lines.append(f'V{name} {name} 0 PULSE(0 {vdd} {1e-9 + k * P / 8:.4g} {tr:.3g} {tr:.3g} {P / 2 - tr:.4g} {P:.4g})')
    ui = per / 2
    if ramp is None:
        rng = np.random.default_rng(seed)
        bits = np.repeat(rng.integers(0, 2, -(-n_bits // rep)), rep)[:n_bits]
        # data bit k is centred on its data clock edge: bit k sampled at 1n + k*ui
        pts_p, pts_n = [], []
        for k, b in enumerate(bits):
            t0 = 1e-9 + delay + (k - .5) * ui
            v = vd / 2 if b else -vd / 2
            pts_p += [(max(t0, 0), cm + v), (t0 + ui - 20e-12, cm + v)]
            pts_n += [(max(t0, 0), cm - v), (t0 + ui - 20e-12, cm - v)]
        lines += [f'VIP inp 0 {pwl(pts_p)}', f'VIN inn 0 {pwl(pts_n)}']
    else:
        lo, hi, t_end = ramp
        lines += [f'VIP inp 0 PWL(0 {cm + lo / 2} {t_end} {cm + hi / 2})',
                  f'VIN inn 0 PWL(0 {cm - lo / 2} {t_end} {cm - hi / 2})']
        bits = None
    lines.append(inst(sub, m))
    return '\n'.join(lines), bits


# trim code used for the 'trimmed' data points: p0 on every sampler (extracted layout has a
# systematic positive offset of ~+17 mV; per-die codes come from the offset calibration in bring-up)
SAMPLERS = ('d0', 'e0', 'd1', 'e1', 'd2', 'e2', 'd3', 'e3')
TRIM_NOMINAL = {k: {'p0': 1} for k in SAMPLERS}


def tb_slicer(sub, netfile, corner='typical', temp=27, vdd=3.3, rates=(1e9,), vd=.2, offsets=True, usb=True,
              delays=None):
    """delays: {rate: s} sampling-instant delay of the quarter-rate divider (QCK rising after the CK0
    edge, measured by slicer_delay()); the open-loop data is centred on the real sampling instants,
    which is what the CDR loop does in closed loop."""
    delays = delays or {}
    cases = []
    points = [(r, 1.0, vd, {}) for r in rates] + ([(480e6, .2, .4, {})] if usb else []) + \
             [(r, 1.0, .06, TRIM_NOMINAL) for r in rates]
    for rate, cm, vd, trims in points:
        if True:
            per = 2 / rate
            nb = 40
            dq, ds = delays.get(rate, (0., 0.))
            dly = ds % (per / 2)
            body, bits = _slicer_body(sub, per, vd, cm, trims, vdd, nb, delay=dly)
            tstop = 1e-9 + (nb / 2 + 1) * per
            ctl = '\n'.join([f'tran {per / 200:.3g} {tstop:.4g}', 'set wr_singlescale',
                             'wrdata tran.txt v(d0) v(d1) v(d2) v(d3) v(qck) i(VDD) v(inp) v(inn)',
                             f'meas tran iavg avg i(VDD) from=1n to={tstop:.4g}'])

            def analyse(log, data, bits=bits, per=per, nb=nb, rate=rate, trims=trims, dly=dly, dq=dq, ds=ds):
                r = parse_meas(log)
                d = load(data)
                # quarter-rate: QCK rising -> D0 decision; D1..D3 follow by 1..3 UI.  Each output is
                # compared with the input at its true decision instant and read just before the same
                # sampler decides again (2 half-rate periods later).
                errs, checked = 0, 0
                t = d[:, 0]
                ui = per / 2
                q_up = [x for x in crossings(t, d[:, 5], vdd / 2) if x > 1e-9 + 2 * per]
                vd_ = lambda tt: at(d, 7, tt) - at(d, 8, tt)
                for tq in q_up:
                    for j in range(4):
                        ts = tq - dq + ds + j * ui
                        t_read = tq + j * ui + 2 * per - .03 * per
                        if t_read > t[-1]:
                            continue
                        v0 = vd_(ts)
                        if any(abs(vd_(ts + x) - v0) > 1e-3 for x in (-.1 * ui, .1 * ui)):
                            continue           # within 0.1 UI of an input transition
                        got = at(d, 1 + j, t_read) > vdd / 2
                        checked += 1
                        errs += int(got != (v0 > 0))
                r.update(bits_checked=checked, bit_errors=errs, line_rate_bps=rate, sampling_delay_ps=ds * 1e12,
                         power_w=abs(r.get('iavg', 0)) * vdd)
                r['pass'] = errs == 0 and checked > 10
                if trims:   # fixed trim code: per-die calibration chooses the code, so not a corner gate
                    r['gating'] = False
                return r
            label = f'data_{rate / 1e9:g}G_cm{cm:g}_{vd * 1e3:g}mVpp' + ('_trimmed' if trims else '')
            cases.append((label, deck(sub, netfile, body, ctl, corner, temp, 'slicer data'), analyse))
    # offset / trim: slow ramp -250mV..+250mV over 200 CK0 cycles (2.5 mV per decision)
    per = 2e-9
    full = lambda bits: {k: {b: 1 for b in bits} for k in SAMPLERS}
    for label, trims in () if not offsets else (('trim0', {}), ('trim_p0', TRIM_NOMINAL), ('trim_n1', full(('n1',))),
                                                 ('trim_p3', full(('p0', 'p1'))), ('trim_n3', full(('n0', 'n1'))),
                                                 # r3 third bit: full range each way (MT-01 target >= +/-50 mV)
                                                 ('trim_p7', full(('p0', 'p1', 'p2'))), ('trim_n7', full(('n0', 'n1', 'n2')))):
        t_end = 400e-9
        body, _ = _slicer_body(sub, per, 0, 1.0, trims, vdd, ramp=(-.25, .25, t_end))
        ctl = '\n'.join([f'tran 20p {t_end:.4g}', 'set wr_singlescale',
                         'wrdata tran.txt v(d0) v(e0) v(d1) v(e1) v(d2) v(e2) v(d3) v(e3)'])

        def analyse(log, data, t_end=t_end):
            d = load(data)
            t = d[:, 0]
            r = {}
            for col, name in enumerate(('d0', 'e0', 'd1', 'e1', 'd2', 'e2', 'd3', 'e3'), 1):
                ups = [u for u in crossings(t, d[:, col], vdd / 2, True) if u > 5e-9]
                r[f'offset_mV_{name}'] = 1e3 * (-.25 + .5 * ups[0] / t_end) if ups else None
            offs = [v for k, v in r.items() if v is not None]
            r['input_referred_offset_mV'] = r['offset_mV_d0']
            r['offset_mV_worst'] = max(offs, key=abs) if offs else None
            r['pass'] = len(offs) == 8
            return r
        cases.append((f'offset_{label}', deck(sub, netfile, body, ctl, corner, temp, f'slicer offset {label}'), analyse))
    return cases


def tb_slicer_trim(sub, netfile, corner='typical', temp=27, vdd=3.3, codes=None, window=(-0.09, 0.09)):
    """r4 (MT01-W2) fine offset-trim characterisation: slow differential ramp over `window` in 400 decisions per
    sampler (0.45 mV/decision for +/-90 mV), 500 MHz CK0, every sampler on the same code.  codes: {label: {bit: 1}}
    with bits p0..p2 (coarse, negative), n0..n2 (coarse, positive), f0..f2 (fine unequal pairs, positive).
    The step/range judgement is made over the set of codes (slicer_trim_summary)."""
    full = lambda bits: {k: {b: 1 for b in bits} for k in SAMPLERS}
    codes = codes or {'t0': ()}
    cases = []
    per = 1e-9
    lo, hi = window
    t_end = 800e-9
    for label, bits_ in codes.items():
        body, _ = _slicer_body(sub, per, 0, 1.0, full(bits_), vdd, ramp=(lo, hi, t_end))
        ctl = '\n'.join([f'tran 20p {t_end:.4g}', 'set wr_singlescale',
                         'wrdata tran.txt v(d0) v(e0) v(d1) v(e1) v(d2) v(e2) v(d3) v(e3)'])

        def analyse(log, data, t_end=t_end, lo=lo, hi=hi):
            d = load(data)
            t = d[:, 0]
            r = {}
            for col, name in enumerate(SAMPLERS, 1):
                ups = [u for u in crossings(t, d[:, col], vdd / 2, True) if u > 5e-9]
                r[f'offset_mV_{name}'] = 1e3 * (lo + (hi - lo) * ups[0] / t_end) if ups else None
            r['resolution_mV'] = 1e3 * (hi - lo) / (t_end / (2 * per))
            r['pass'] = all(r[f'offset_mV_{n}'] is not None for n in SAMPLERS)
            r['gating'] = False
            return r
        cases.append((f'trim_{label}', deck(sub, netfile, body, ctl, corner, temp, f'slicer trim {label}'), analyse))
    return cases


# fine code k = f2 f1 f0 (binary, weights ~2/4/8 mV); p0 / n0 = one coarse LSB each way; p0f7 checks that the fine
# span covers the coarse LSB (contiguous codes)
TRIM_CODES_R4 = dict({f'f{k}': tuple(f'f{b}' for b in range(3) if (k >> b) & 1) for k in range(8)},
                     p0=('p0',), p0f7=('p0', 'f0', 'f1', 'f2'), n0=('n0',))
TRIM_RANGE_R4 = {'p7': ('p0', 'p1', 'p2'), 'n7f7': ('n0', 'n1', 'n2', 'f0', 'f1', 'f2')}
# r6: four fine bits (f3 = the new ~1 mV pair); fine code k = f3..f0 bits of k
TRIM_CODES_R6 = dict({f'f{k}': tuple(f'f{b}' for b in range(4) if (k >> b) & 1) for k in range(16)},
                     p0=('p0',), p0f15=('p0', 'f0', 'f1', 'f2', 'f3'), n0=('n0',))
TRIM_RANGE_R6 = {'p7': ('p0', 'p1', 'p2'), 'n7f15': ('n0', 'n1', 'n2', 'f0', 'f1', 'f2', 'f3')}


RING_PLAN = (480e6, 625e6, 810e6)          # pt_pll_ring range used by the wired RX
MODES = ((1, 'quarter'), (2, 'half'), (4, 'full'))


def tb_slicer_plan(sub, netfile, corner='typical', temp=27, vdd=3.3, rings=RING_PLAN, delays=None, skews=(0.,),
                   trimmed=True, usb=True):
    """Ring-plan qualification (r2): every ring frequency x bits per ring cycle (quarter/half/full, the
    samplers always run at the ring rate; half/full only lengthen the line bit), 200 mVppd at CM 1.0 V;
    60 mVppd trimmed at quarter rate; USB HS = full rate at ring 480 MHz (480 Mb/s), CM 0.2 V, 400 mVppd.
    skews: data shifted by skew x quarter-UI against the assumed sampling instant (clock edge + APERTURE)
    while the check still uses that instant, i.e. a horizontal window test of the real aperture."""
    delays = delays or {}
    cases = []
    points = []
    for f_ring in rings:
        for rep, mode in MODES:
            points.append((f_ring, rep, mode, 1.0, .2, {}))
        if trimmed:
            points.append((f_ring, 1, 'quarter', 1.0, .06, TRIM_NOMINAL))
    if usb:
        points.append((480e6, 4, 'usbhs', .2, .4, {}))
    for f_ring, rep, mode, cm, vd, trims in points:
        for skew in skews:
            rate = 4 * f_ring                 # quarter-rate equivalent (sampling grid)
            per = 2 / rate
            nb = 40
            dq, ds = delays.get(rate, (0., APERTURE))
            ui = per / 2
            dly = (ds % ui) + skew * ui
            body, bits = _slicer_body(sub, per, vd, cm, trims, vdd, nb, delay=dly, rep=rep)
            tstop = 1e-9 + (nb / 2 + 1) * per
            ctl = '\n'.join([f'tran {per / 200:.3g} {tstop:.4g}', 'set wr_singlescale',
                             'wrdata tran.txt v(d0) v(d1) v(d2) v(d3) v(qck) i(VDD) v(inp) v(inn) v(e0) v(e1) v(e2) v(e3)',
                             f'meas tran iavg avg i(VDD) from=1n to={tstop:.4g}'])

            def analyse(log, data, per=per, rate=rate, trims=trims, dq=dq, ds=ds, rep=rep, skew=skew, f_ring=f_ring):
                r = parse_meas(log)
                d = load(data)
                errs, checked = 0, 0
                t = d[:, 0]
                ui = per / 2
                q_up = [x for x in crossings(t, d[:, 5], vdd / 2) if x > 1e-9 + 2 * per]
                vd_ = lambda tt: at(d, 7, tt) - at(d, 8, tt)
                # all eight samplers: D_j at j UI, E_j at j UI + UI/2 after the D0 instant (columns d0..d3, e0..e3)
                outs = [(1 + j, j * ui) for j in range(4)] + [(9 + j, j * ui + ui / 2) for j in range(4)]
                for tq in q_up:
                    for col, off in outs:
                        ts = tq - dq + ds + off
                        t_read = tq + off + 2 * per - .03 * per
                        if t_read > t[-1]:
                            continue
                        v0 = vd_(ts)
                        if any(abs(vd_(ts + x) - v0) > 1e-3 for x in (-.1 * ui, .1 * ui)):
                            continue           # within 0.1 quarter-UI of an input transition
                        got = at(d, col, t_read) > vdd / 2
                        checked += 1
                        errs += int(got != (v0 > 0))
                r.update(bits_checked=checked, bit_errors=errs, ring_hz=f_ring, line_rate_bps=rate / rep,
                         bits_per_ring_cycle=4 // rep, skew_ui=skew, sampling_delay_ps=ds * 1e12,
                         power_w=abs(r.get('iavg', 0)) * vdd)
                r['pass'] = errs == 0 and checked > 20
                if trims or skew:   # fixed trim code (per-die calibration) / window probes: not corner gates
                    r['gating'] = False
                return r
            label = f'ring{f_ring / 1e6:g}M_{mode}_{rate / rep / 1e9:g}G_cm{cm:g}_{vd * 1e3:g}mVpp' + \
                    ('_trimmed' if trims else '') + (f'_skew{skew:+g}' if skew else '')
            cases.append((label, deck(sub, netfile, body, ctl, corner, temp, 'slicer ring plan'), analyse))
    return cases


# ------------------------------------------------------------------ detect
def tb_detect(sub, netfile, corner='typical', temp=27, vdd=3.3):
    cases = []
    base = dict(VDD_WIRE_SW='vdd', VSS='0', IBIAS='ib', det_en='en', det_clk='clk', RX_P='lp', RX_N='ln',
                TX_P='txp', TX_N='txn', det_thr0='t0', det_thr1='t1', det_se0='s0', det_se1='s1',
                det_src_tx='src', det_inject='inj', DIFF_POS='dpos', DIFF_NEG='dneg', SE_P='sep', SE_N='sen',
                atb_det_vref='vref')
    per = 4e-9

    def common(thr, se, src=0, inj=0):
        return [f'VDD vdd 0 {vdd}', 'RIB vdd ib 260k', f'VEN en 0 PWL(0 0 2n {vdd})',
                f'VCK clk 0 PULSE(0 {vdd} 5n 0.1n 0.1n {per / 2 - .1e-9} {per})',
                f'VT0 t0 0 {vdd * (thr & 1)}', f'VT1 t1 0 {vdd * (thr >> 1)}',
                f'VS0 s0 0 {vdd * (se & 1)}', f'VS1 s1 0 {vdd * (se >> 1)}',
                f'VSRC src 0 {vdd * src}', f'VINJ inj 0 {vdd * inj}']
    # 1) USB HS squelch: thr=125 mV (code 2). lines CM 0.2 V. 200 mV diff alternating for 40n, then 60 mV diff.
    def diffwave(amp1, amp2, cm, t_sw, half=8e-9):
        pts_p, pts_n = [], []
        t = 0.
        sign = 1
        while t < 2 * t_sw:
            a = amp1 if t < t_sw else amp2
            pts_p += [(t, cm + sign * a / 2), (t + half - 50e-12, cm + sign * a / 2)]
            pts_n += [(t, cm - sign * a / 2), (t + half - 50e-12, cm - sign * a / 2)]
            sign = -sign
            t += half
        return pwl(pts_p), pwl(pts_n)
    # USB settings (from tb_detect_thresholds on the extraction): squelch det_thr=2 (effective ~150-176 mV,
    # above the 100-150 mV USB window), disconnect det_thr=3 (~556-566 mV)
    for cm, a1, a2, thr, label in ((.2, .3, .06, 2, 'usb_hs_squelch'), (.2, .8, .4, 3, 'usb_hs_disconnect')):
        pp, pn = diffwave(a1, a2, cm, 64e-9)
        body = '\n'.join(common(thr, 2) + [f'VLP lp 0 {pp}', f'VLN ln 0 {pn}', 'VTXP txp 0 0', 'VTXN txn 0 0',
                                            inst(sub, base)])
        ctl = '\n'.join(['tran 20p 128n', 'set wr_singlescale', 'wrdata tran.txt v(dpos) v(dneg) v(lp) v(ln) v(clk) i(VDD)',
                         'meas tran iavg avg i(VDD) from=10n to=128n', 'meas tran vref_v find v(vref) at=60n'])

        def analyse(log, data, a1=a1, a2=a2):
            r = parse_meas(log)
            d = load(data)
            t = d[:, 0]
            hit = np.maximum(d[:, 1], d[:, 2]) > vdd / 2
            r['hits_above_threshold_window'] = int(np.sum(hit[(t > 12e-9) & (t < 64e-9)]) > 0)
            r['fraction_hit_above'] = float(np.mean(hit[(t > 12e-9) & (t < 64e-9)]))
            r['fraction_hit_below'] = float(np.mean(hit[(t > 70e-9) & (t < 128e-9)]))
            r['pass'] = bool(r['fraction_hit_above'] > .5 and r['fraction_hit_below'] < .02)
            return r
        cases.append((label, deck(sub, netfile, body, ctl, corner, temp, f'detect {label}'), analyse))
    # 2) USB FS single-ended receivers: Vse=1.4 V (code 2); J/K/SE0 states 0..3.3 V
    seq = [(0, (3.3, 0)), (20e-9, (0, 3.3)), (40e-9, (0, 0)), (60e-9, (3.3, 0))]
    pp = pwl(sum([[(t, a), (t + 19.5e-9, a)] for t, (a, b) in seq], []))
    pn = pwl(sum([[(t, b), (t + 19.5e-9, b)] for t, (a, b) in seq], []))
    body = '\n'.join(common(0, 2) + [f'VLP lp 0 {pp}', f'VLN ln 0 {pn}', 'VTXP txp 0 0', 'VTXN txn 0 0', inst(sub, base)])
    ctl = '\n'.join(['tran 20p 80n', 'set wr_singlescale', 'wrdata tran.txt v(sep) v(sen)',
                     'meas tran sep_j find v(sep) at=18n', 'meas tran sen_j find v(sen) at=18n',
                     'meas tran sep_k find v(sep) at=38n', 'meas tran sen_k find v(sen) at=38n',
                     'meas tran sep_se0 find v(sep) at=58n', 'meas tran sen_se0 find v(sen) at=58n'])

    def se(log, data):
        r = parse_meas(log)
        h = vdd / 2
        r['pass'] = bool(r.get('sep_j', 0) > h and r.get('sen_j', 9) < h and r.get('sep_k', 9) < h
                         and r.get('sen_k', 0) > h and r.get('sep_se0', 9) < h and r.get('sen_se0', 9) < h)
        return r
    cases.append(('usb_fs_line_state', deck(sub, netfile, body, ctl, corner, temp, 'detect SE'), se))
    # 3) receiver detection: inject into TX pads loaded by 10k (absent) vs 10k||100nF-ish (present: big C), sense SE
    body = '\n'.join(common(0, 0, src=1, inj=1) + ['VLP lp 0 0', 'VLN ln 0 0',
                     'RTP txp 0 10k', 'CTP txp 0 1p', 'RTN txn 0 10k', 'CTN txn 0 50p', inst(sub, base)])
    ctl = '\n'.join(['tran 0.1n 400n', 'set wr_singlescale', 'wrdata tran.txt v(txp) v(txn) v(sep) v(sen)',
                     'meas tran v_txp find v(txp) at=390n', 'meas tran v_txn_100n find v(txn) at=100n',
                     # r6: from 10 ns (after the first det_clk sample): the SR output latch powers up in an
                     # undefined state at det_en and is only valid after a clocked decision
                     'meas tran t_sep when v(sep)=1.65 rise=1 td=10n', 'meas tran t_sen when v(sen)=1.65 rise=1 td=10n',
                     'meas tran iavg avg i(VDD) from=300n to=400n'])

    def rxdet(log, data):
        r = parse_meas(log)
        r['inject_current_uA_est'] = r['v_txp'] / 10e3 * 1e6 if 'v_txp' in r else None
        r['present_leg_slower'] = bool('t_sep' in r and r.get('t_sen', 1.0) > r['t_sep'] + 50e-9)
        r['pass'] = bool(r['present_leg_slower'] and 60 < (r['inject_current_uA_est'] or 0) < 160)
        return r
    cases.append(('rx_detect', deck(sub, netfile, body, ctl, corner, temp, 'detect rxdet'), rxdet))
    # 4) disabled: no current
    body = '\n'.join([f'VDD vdd 0 {vdd}', 'RIB vdd ib 260k', 'VEN en 0 0', f'VCK clk 0 PULSE(0 {vdd} 5n 0.1n 0.1n 1.9n 4n)',
                      'VT0 t0 0 0', 'VT1 t1 0 0', 'VS0 s0 0 0', 'VS1 s1 0 0', 'VSRC src 0 0', f'VINJ inj 0 {vdd}',
                      'VLP lp 0 1', 'VLN ln 0 0.5', 'VTXP txp 0 1', 'VTXN txn 0 1', inst(sub, base)])
    ctl = '\n'.join(['tran 0.1n 60n', 'meas tran iavg avg i(VDD) from=20n to=60n', 'meas tran itxp avg i(VTXP) from=20n to=60n',
                     'meas tran dpos_max max v(dpos) from=10n to=60n', 'meas tran sep_max max v(sep) from=10n to=60n'])

    def off(log, data):
        r = parse_meas(log)
        r['pass'] = bool(abs(r.get('iavg', 1)) < 2e-6 and abs(r.get('itxp', 1)) < 1e-6 and r.get('dpos_max', 9) < .1
                         and r.get('sep_max', 9) < .1)
        return r
    cases.append(('off', deck(sub, netfile, body, ctl, corner, temp, 'detect off'), off))
    return cases


# ------------------------------------------------------------------ cdr
def tb_cdr(sub, netfile, corner='typical', temp=27, vdd=3.3):
    """AC-3 pt_cdr (r-ac3): pump current into VCTRL held at 1.1 V (static votes and ring-rate vote
    patterns), IB_PLL into the PLL's 4/2 NMOS diode, HOLD_PLL / REF_PLL logic.  Each case can fail.
    Dynamic cases toggle the votes at 625 MHz (1.6 ns, one ring cycle per vote) and compare the average
    current with the static expectation, so switch charge injection shows up as an error current;
    alt625 alternates UP and DN of all four legs every ring cycle (ideal: 0) and must stay below 25 %
    of one leg's current (the bang-bang loop absorbs a smaller offset with a vote imbalance)."""
    unit = 8.0   # nA, design unit
    T = 1.6e-9
    def code_units(code):
        return 1 + (code & 1) + 2 * ((code >> 1) & 1) + 4 * ((code >> 2) & 1)
    # name, en, pfd, rsel, code, up legs, dn legs, fup, fdn, pattern
    states = [('off', 0, 0, 0, 7, 4, 4, 1, 1, 'static'), ('idle', 1, 0, 0, 7, 0, 0, 0, 0, 'static'),
              ('up1_c0', 1, 0, 0, 0, 1, 0, 0, 0, 'static'), ('up4_c7', 1, 0, 0, 7, 4, 0, 0, 0, 'static'),
              ('dn4_c3', 1, 0, 0, 3, 0, 4, 0, 0, 'static'), ('dn1_c7', 1, 0, 0, 7, 0, 1, 0, 0, 'static'),
              ('up4_c2', 1, 1, 1, 2, 4, 0, 0, 0, 'static'),
              ('fup_c0', 1, 0, 0, 0, 0, 0, 1, 0, 'static'), ('fdn_c7', 1, 0, 0, 7, 0, 0, 0, 1, 'static'),
              ('updn_c7', 1, 0, 0, 7, 4, 4, 0, 0, 'static'),
              ('tog625_c3', 1, 0, 0, 3, 4, 0, 0, 0, 'toggle'), ('alt625_c3', 1, 0, 0, 3, 4, 4, 0, 0, 'alt'),
              ('alt625_c0', 1, 0, 0, 0, 4, 4, 0, 0, 'alt'), ('alt625_c7', 1, 0, 0, 7, 4, 4, 0, 0, 'alt')]
    cases = []
    for name, en, pfd, rsel, code, nup, ndn, fup, fdn, pat in states:
        m = dict(VDD_PLL_SW='vdd', VSS='0', IBIAS='ib', cdr_en='en', pfd_mode='pfd', ref_sel='rsel',
                 g0='g0', g1='g1', g2='g2', FUP='fup', FDN='fdn', IB_PLL='ibp', HOLD_PLL='holdp', VCTRL='vc',
                 REF_IN='ref', WCK_IN='wck', REF_PLL='refp', atb_cdr_pbias='pb')
        L = [f'VDD vdd 0 {vdd}', 'RIB vdd ib 260k', f'VEN en 0 {en * vdd}', f'VPF pfd 0 {pfd * vdd}',
             f'VRS rsel 0 {rsel * vdd}', f'VFU fup 0 {fup * vdd}', f'VFD fdn 0 {fdn * vdd}',
             'VIBP ibp ibpd 0', 'XNBD ibpd ibpd 0 0 nfet_03v3 w=4u l=2u', 'VVC vc 0 1.1',
             # REF 39 MHz, WCK 74.25 MHz: REF_PLL frequency tells which one is selected
             f'VRF ref 0 PULSE(0 {vdd} 10n 200p 200p 12.6n 25.6n)', f'VWK wck 0 PULSE(0 {vdd} 10n 200p 200p 6.53n 13.47n)']
        L += [f'VG{b} g{b} 0 {vdd * ((code >> b) & 1)}' for b in range(3)]
        for k in range(4):
            for d, nlegs in (('UP', nup), ('DN', ndn)):
                m[f'{d}{k}'] = f'{d.lower()}{k}'
                on = k < nlegs
                if pat == 'static' or not on:
                    L.append(f'V{d}{k} {d.lower()}{k} 0 {vdd * on}')
                else:
                    # toggle: on every other ring cycle; alt: UP on even cycles, DN on odd cycles
                    dl = 0 if (pat == 'toggle' or d == 'UP') else T
                    L.append(f'V{d}{k} {d.lower()}{k} 0 PULSE(0 {vdd} {50e-9 + dl:.4g} 80p 80p {T - 80e-12:.4g} {2 * T:.4g})')
        L.append(inst(sub, m))
        body = '\n'.join(L)
        ctl = '\n'.join(['tran 0.05n 400n', 'meas tran i_ibpll avg i(VIBP) from=200n to=400n',
                         'meas tran i_bb avg i(VVC) from=200n to=400n', 'meas tran i_vdd_n avg i(VDD) from=200n to=400n',
                         'meas tran v_hold avg v(holdp) from=200n to=400n',
                         f'meas tran nref trig v(refp) val={vdd / 2} rise=2 targ v(refp) val={vdd / 2} rise=6',
                         'let i_vdd = -i_vdd_n', 'print i_vdd'])

        def analyse(log, data, name=name, en=en, pfd=pfd, rsel=rsel, code=code, nup=nup, ndn=ndn, fup=fup, fdn=fdn, pat=pat):
            import re
            def g(k):
                mm = re.search(rf'^{k}\s*=\s*([-+0-9.eE]+)', log, re.M)
                return float(mm.group(1)) if mm else None
            # i(VVC): ngspice reports current from + through the source, so sourcing into VCTRL reads positive
            ibb = g('i_bb')
            r = dict(i_ibpll_uA=g('i_ibpll') * 1e6, i_pump_nA=ibb * 1e9 if ibb is not None else None,
                     i_vdd_uA=g('i_vdd') * 1e6, v_hold=g('v_hold'), ref_4periods_s=g('nref'))
            u = unit * code_units(code)
            legs = (4 if fup else nup) - (4 if fdn else ndn)
            if pat == 'toggle':
                want = 0.5 * legs * u
            elif pat == 'alt':
                want = 0.0
            else:
                want = legs * u if en else 0.0
            r['i_pump_expected_nA'] = want
            ok_ib = abs(r['i_ibpll_uA'] - (10 if en else 0)) < 3
            if pat == 'alt':
                ok_p = abs(r['i_pump_nA']) < 0.25 * u
            elif want == 0:
                ok_p = abs(r['i_pump_nA']) < (0.25 * u if en else 1.0)
            else:
                ok_p = 0.5 < r['i_pump_nA'] / want < 2.0
            ok_hold = (r['v_hold'] < 0.3) if (en and pfd) else (r['v_hold'] > vdd - 0.3)
            per = r['ref_4periods_s']
            ok_ref = (per is None) if not en else (per is not None and abs(per / 4 - (13.47e-9 if rsel else 25.6e-9)) < 1e-9)
            r.update(ok_ib=ok_ib, ok_pump=ok_p, ok_hold=ok_hold, ok_ref=ok_ref)
            r['pass'] = bool(ok_ib and ok_p and ok_hold and ok_ref and (en or abs(r['i_vdd_uA']) < 1))
            return r
        cases.append((name, deck(sub, netfile, body, ctl, corner, temp, f'cdr {name}'), analyse))
    return cases


def tb_ptrim(sub, netfile, corner='typical', temp=27, vdd=3.3, f=810e6, codes=tuple(range(32))):
    """Per-phase delay trim: ideal 45-degree phases at f into PH0..7, all eight channels at one code per
    case; each case measures the PHk -> CKPk rise delay of every channel (CKPk loaded with 150 fF: slicer
    + capture clock pins and route).  Code sweep 0..31 -> per-channel delay curve; the judgement (step
    <= 1 deg at f, monotonic, range) is made over the whole sweep in ptrim_summary()."""
    T = 1 / f
    cases = []
    for code in codes:
        m = dict(VDD_WIRE_SW='vdd', VSS='0', ptrim_en='vdd')
        L = [f'VDD vdd 0 {vdd}']
        for k in range(8):
            m[f'PH{k}'] = f'ph{k}'
            m[f'CKP{k}'] = f'ckp{k}'
            L.append(f'VPH{k} ph{k} 0 PULSE(0 {vdd} {1e-9 + k * T / 8:.6e} 60p 60p {T / 2 - 60e-12:.6e} {T:.6e})')
            L.append(f'CL{k} ckp{k} 0 150f')
            for b in range(5):
                m[f'T{k}_{b}'] = 'vdd' if (code >> b) & 1 else '0'
        L.append(inst(sub, m))
        t1 = 1e-9 + 3 * T
        meas = [f'meas tran d{k} trig v(ph{k}) val={vdd / 2} rise=3 targ v(ckp{k}) val={vdd / 2} rise=3' for k in range(8)]
        ctl = '\n'.join([f'tran 2p {1e-9 + 5 * T:.4g}'] + meas)

        def analyse(log, data, code=code):
            import re
            r = dict(code=code)
            for k in range(8):
                mm = re.search(rf'^d{k}\s*=\s*([-+0-9.eE]+)', log, re.M)
                r[f'delay_ps_{k}'] = float(mm.group(1)) * 1e12 if mm else None
            r['pass'] = all(r[f'delay_ps_{k}'] is not None for k in range(8))
            r['gating'] = False         # judged over the sweep (ptrim_summary)
            return r
        cases.append((f'code{code:02d}', deck(sub, netfile, body='\n'.join(L), control=ctl, corner=corner, temp=temp,
                                               title=f'ptrim code {code}'), analyse))
    return cases


def ptrim_summary(res, f=810e6, spec_err_deg=5.7):
    """Over a code sweep {case: metrics}: per channel step (deg at f), monotonicity and range; pass if every
    step <= 1 deg, monotonic, and range >= 2 x the ring's measured spacing error (r7 5.7 deg), so any
    error inside +/-5.7 deg trims to within half a step (<= 0.5 deg, << 3 deg)."""
    deg = 360.0 * f * 1e-12
    out = dict(f_hz=f, channels={})
    ok = True
    for k in range(8):
        d = [res.get(f'code{c:02d}', {}).get(f'delay_ps_{k}') for c in range(32)]
        if any(x is None for x in d):
            out['channels'][k] = dict(error='missing codes'); ok = False
            continue
        steps = [(d[i + 1] - d[i]) * deg for i in range(31)]
        rng = (d[31] - d[0]) * deg
        ch = dict(delay0_ps=d[0], range_deg=rng, max_step_deg=max(steps), min_step_deg=min(steps),
                  monotonic=min(steps) > 0)
        ch['pass'] = bool(ch['monotonic'] and ch['max_step_deg'] <= 1.0 and rng >= 2 * spec_err_deg)
        ok &= ch['pass']
        out['channels'][k] = ch
    d0 = [res.get('code00', {}).get(f'delay_ps_{k}') for k in range(8)]
    if all(x is not None for x in d0):
        out['channel_spread_code0_deg'] = (max(d0) - min(d0)) * deg
    out['pass'] = bool(ok)
    return out


BENCHES = dict(termination=[tb_termination], rxlevel=[tb_rxlevel], rxselect=[tb_rxselect], wmon_sel=[tb_wmon_sel],
               ctle=[tb_ctle], slicer=[tb_slicer], detect=[tb_detect], cdr=[tb_cdr], ptrim=[tb_ptrim])


# ------------------------------------------------------------------ generic safety benches
PORTS = dict(
    termination=dict(ctrl=['term_en', 'term_mode0', 'term_mode1', 'hs_en', 'hs_term_en', 'hs_trim0', 'hs_trim1', 'hs_trim2',
                           'hs_trim3'], clk=[], ain=[], bias=[],
                     out=['TERM_ENABLE', 'DIFF_ENABLE', 'TERM_VCM', 'HS_TERM_ENABLE', 'HS_TERM_TRIM0', 'HS_TERM_TRIM1',
                          'HS_TERM_TRIM2', 'HS_TERM_TRIM3', 'HS_TERM_VCM', 'HS_VBIAS']),
    rxlevel=dict(ctrl=['rxlevel_en', 'rxlevel_half'], clk=[], ain=[], bias=[], out=['DIV_ENABLE', 'BYPASS_ENABLE']),
    rxselect=dict(ctrl=['rxselect_en', 'rxselect_direct'], clk=[], ain=['CTLE_P', 'CTLE_N', 'RX_P', 'RX_N'], bias=[],
                  out=['SL_P', 'SL_N']),
    wmon_sel=dict(ctrl=['wmon_en', 'wmon_sel0', 'wmon_sel1'], clk=[], ain=['RX_P', 'RX_N', 'CTLE_P', 'CTLE_N'], bias=[],
                  out=['WMON_IN']),
    ctle=dict(ctrl=['ctle_en', 'wire_ctle_bypass', 'ctle_peak0', 'ctle_peak1', 'ctle_peak2', 'lf_zero0', 'lf_zero1',
                    'lf_zero2'], clk=[], ain=['RX_P', 'RX_N'],
              bias=['IBIAS'], out=['CTLE_P', 'CTLE_N'], atb=['atb_ctle_pbias', 'atb_ctle_src']),
    slicer=dict(ctrl=['slicer_en'] + [f'trim_{s}_{b}' for s in ('d0', 'e0', 'd1', 'e1', 'd2', 'e2', 'd3', 'e3')
                                      for b in ('p0', 'p1', 'p2', 'n0', 'n1', 'n2', 'f0', 'f1', 'f2')],
                clk=[f'CKP{k}' for k in range(8)], ain=['SL_P', 'SL_N'], bias=[], out=['D0', 'E0', 'D1', 'E1', 'D2', 'E2', 'D3', 'E3', 'QCK']),
    detect=dict(ctrl=['det_en', 'det_thr0', 'det_thr1', 'det_se0', 'det_se1', 'det_src_tx', 'det_inject'],
                clk=['det_clk'], ain=['RX_P', 'RX_N', 'TX_P', 'TX_N'], bias=['IBIAS'],
                out=['DIFF_POS', 'DIFF_NEG', 'SE_P', 'SE_N'], atb=['atb_det_vref']),
    cdr=dict(ctrl=['cdr_en', 'pfd_mode', 'ref_sel', 'g0', 'g1', 'g2', 'UP0', 'UP1', 'UP2', 'UP3', 'DN0', 'DN1', 'DN2', 'DN3',
                   'FUP', 'FDN'], clk=['REF_IN', 'WCK_IN'], ain=['VCTRL'], bias=['IBIAS'],
             out=['IB_PLL', 'REF_PLL', 'HOLD_PLL'], atb=['atb_cdr_pbias']),
    ptrim=dict(ctrl=['ptrim_en'] + [f'T{k}_{b}' for k in range(8) for b in range(5)], clk=[f'PH{k}' for k in range(8)],
               ain=[], bias=[], out=[f'CKP{k}' for k in range(8)]),
)
ENABLE = dict(termination='term_en', rxlevel='rxlevel_en', rxselect='rxselect_en', wmon_sel='wmon_en', ctle='ctle_en',
              slicer='slicer_en', detect='det_en', cdr='cdr_en', ptrim='ptrim_en')


def tb_safe(sub, netfile, block, corner='typical', vdd=3.63):
    """Safety cases (function not required):
    off_<T>C: rail at `vdd` (3.63 V PDK limit), enable and every control low, clocks running,
      analog inputs at 3.3 V (worst high pad level): supply current and output levels at 0/27/85 C.
    stuck_on: every control high at 3.63 V, 27 C: supply current (mis-programming, no latch/short).
    unpowered: island header off (rail via 1 Mohm to VSS); controls at 0 (the register file clamps
      every control of an island that is off), clocks toggling 0-3.3 V, pad-reachable inputs
      (detect TX_P/N) at 3.63 V, internal analog nodes at 0 V: rail back-drive and input currents.
    unpowered_internal_driven (non-gating): as above but every analog input at 3.63 V and every
      control at 3.3 V -- only reachable if the pad bypass were on with the island off."""
    P = PORTS[block]
    supply = [p for p in sub.ports if p.startswith('VDD')][0]
    cases = []

    pad_reach = {'detect': ['TX_P', 'TX_N']}.get(block, [])

    def body(rail, ctrl_level, temp_note, rail_r=None, ain_level=None):
        m = {supply: 'rail', 'VSS': '0'}
        lines = [f'VDD rail_src 0 {rail}', f'RVDD rail_src rail {rail_r}' if rail_r else 'RVDD rail_src rail 0.01']
        for p in P['ctrl']:
            m[p] = 'ctl'
        lines.append(f'VCTL ctl 0 {ctrl_level}')
        for p in P['clk']:
            m[p] = 'clk'
        # clocks: running, except for an unpowered cdr whose sources (PLL, WCLK_IN receiver) share its island
        if rail_r and block == 'cdr':
            lines.append('VCLK clk 0 0')
        else:
            lines.append(f'VCLK clk 0 PULSE(0 3.3 1n 0.1n 0.1n 1.9n 4n)')
        for p in P['ain']:
            m[p] = 'ain' if (ain_level is None or p in pad_reach) else 'ain_int'
        lines.append(f'VAIN ain 0 {3.63 if rail_r else 3.3}')
        lines.append(f'VAINT ain_int 0 {ain_level if ain_level is not None else 0}')
        for p in P['bias']:
            m[p] = 'ib'
            lines.append('RIB rail_src ib 260k' if not rail_r else 'RIB ain ib 260k')
        outs = P['out'] + P.get('atb', [])
        for p in outs:
            m[p] = 'o_' + p.lower()
            lines.append(f'CO_{p} o_{p.lower()} 0 50f')
        lines.append(inst(sub, m))
        return '\n'.join(lines), outs

    for temp in (0, 27, 85):
        b, outs = body(vdd, 0, temp)
        ctl = '\n'.join(['tran 50p 60n', 'meas tran i_rail avg i(VDD) from=20n to=60n',
                         *[f'meas tran vmax_{o.lower()} max v(o_{o.lower()}) from=20n to=60n' for o in P['out']]])

        def analyse(log, data):
            r = parse_meas(log)
            r['i_rail_A'] = -r.get('i_rail', float('nan'))
            vmax = [v for k, v in r.items() if k.startswith('vmax_')]
            r['outputs_low'] = bool(vmax and max(vmax) < .1) or not P['out']
            # gate: net consumption from the rail < 5 uA.  A negative value is charge pumped *into*
            # the rail by the running clock inputs through gate capacitance (reported, not a DC path).
            r['pass'] = bool(r['i_rail_A'] < 5e-6 and r['outputs_low'])
            return r
        cases.append((f'off_{temp}C', deck(sub, netfile, b, ctl, corner, temp, f'{block} off'), analyse))
    b, outs = body(vdd, vdd, 27)
    ctl = '\n'.join(['tran 50p 60n', 'meas tran i_rail avg i(VDD) from=20n to=60n', 'meas tran i_peak min i(VDD) from=1n to=60n'])

    def stuck(log, data):
        r = parse_meas(log)
        r['i_rail_A'] = -r.get('i_rail', float('nan'))
        r['pass'] = bool(abs(r['i_rail_A']) < 30e-3)
        return r
    cases.append(('stuck_on', deck(sub, netfile, b, ctl, corner, 27, f'{block} stuck on'), stuck))
    ctl = '\n'.join(['tran 50p 60n', 'meas tran v_rail max v(rail) from=20n to=60n',
                     'meas tran i_ain avg i(VAIN) from=20n to=60n', 'meas tran i_ctl avg i(VCTL) from=20n to=60n'])
    b, outs = body(0, 0, 27, rail_r='1meg', ain_level=0)

    def unpowered(log, data):
        # i_ctl is reported, not gated: with clocks toggling into an unpowered block it is the
        # average of capacitive coupling currents, not a DC path
        r = parse_meas(log)
        r['pass'] = bool(r.get('v_rail', 9) < .5 and abs(r.get('i_ain', 1)) < 1e-6)
        return r
    cases.append(('unpowered', deck(sub, netfile, b, ctl, corner, 27, f'{block} unpowered'), unpowered))
    if P['ain']:
        b, outs = body(0, 3.3, 27, rail_r='1meg')

        def driven(log, data):
            r = parse_meas(log)
            r['pass'] = bool(r.get('v_rail', 9) < .5 and abs(r.get('i_ain', 1)) < 1e-6)
            r['gating'] = False
            return r
        cases.append(('unpowered_internal_driven', deck(sub, netfile, b, ctl, corner, 27, f'{block} unpowered driven'), driven))
    return cases


def tb_loading(sub, netfile, block, node_map, probe, ctl_levels, corner='typical', temp=27, vdd=3.3, cm=1.0):
    """Small-signal capacitance seen at `probe` (port) with the given static controls: Im(Y)/w at 1 GHz."""
    P = PORTS[block]
    supply = [p for p in sub.ports if p.startswith('VDD')][0]
    m = {supply: 'vdd', 'VSS': '0'}
    lines = [f'VDD vdd 0 {vdd}']
    for p in sub.ports:
        if p in m:
            continue
        if p == probe:
            m[p] = 'probe'
        elif p in ctl_levels:
            m[p] = 'vdd' if ctl_levels[p] else '0'
        elif p in P['ctrl'] or p in P['clk']:
            m[p] = '0'
        elif p in P['ain']:
            m[p] = 'ain'
        elif p in P['bias']:
            m[p] = 'ib'
        else:
            m[p] = 'n_' + p.lower()
    lines += [f'VPR probe 0 DC {cm} AC 1', f'VAIN ain 0 {cm}', 'RIB vdd ib 260k', inst(sub, m)]
    ctl = '\n'.join(['ac lin 1 1e9 1e9', 'let c=-imag(i(VPR))/(2*3.14159265*1e9)', 'print c'])

    def analyse(log, data):
        import re
        mm = re.search(r'^c\s*=\s*([-+0-9.eE]+)', log, re.M)
        return dict(cap_fF=float(mm.group(1)) * 1e15 if mm else None, pass_=None, **{'pass': mm is not None})
    return deck(sub, netfile, '\n'.join(lines), ctl, corner, temp, f'{block} loading at {probe}'), analyse


def tb_detect_thresholds(sub, netfile, corner='typical', temp=27, vdd=3.3, codes=(0, 1, 2, 3), cm=.2):
    """Effective differential thresholds: |P-N| ramps 0 -> 0.9 V over 360 ns (2.5 mV per det_clk sample),
    once with P>N and once with N>P; report the amplitude at which DIFF_POS / DIFF_NEG first fire."""
    base = dict(VDD_WIRE_SW='vdd', VSS='0', IBIAS='ib', det_en='en', det_clk='clk', RX_P='lp', RX_N='ln',
                TX_P='txp', TX_N='txn', det_thr0='t0', det_thr1='t1', det_se0='0', det_se1='0',
                det_src_tx='0', det_inject='0', DIFF_POS='dpos', DIFF_NEG='dneg', SE_P='sep', SE_N='sen',
                atb_det_vref='vref')
    cases = []
    t_end, amax = 360e-9, .9
    for code in codes:
        for sign in (1, -1):
            body = '\n'.join([f'VDD vdd 0 {vdd}', 'RIB vdd ib 260k', f'VEN en 0 PWL(0 0 2n {vdd})',
                              f'VCK clk 0 PULSE(0 {vdd} 5n 0.1n 0.1n 1.9n 4n)',
                              f'VT0 t0 0 {vdd * (code & 1)}', f'VT1 t1 0 {vdd * (code >> 1)}',
                              f'VLP lp 0 PWL(0 {cm} {t_end} {cm + sign * amax / 2})',
                              f'VLN ln 0 PWL(0 {cm} {t_end} {cm - sign * amax / 2})',
                              'VTXP txp 0 0', 'VTXN txn 0 0', inst(sub, base)])
            ctl = '\n'.join([f'tran 50p {t_end:.4g}', 'set wr_singlescale', 'wrdata tran.txt v(dpos) v(dneg)'])

            def analyse(log, data, sign=sign):
                d = load(data)
                col = 1 if sign > 0 else 2
                ups = [u for u in crossings(d[:, 0], d[:, col], vdd / 2, True) if u > 6e-9]
                other = d[:, 3 - col] > vdd / 2
                r = dict(threshold_mV=1e3 * amax * ups[0] / t_end if ups else None,
                         wrong_side_fired=bool(other[d[:, 0] > 6e-9].any()))
                r['pass'] = ups != [] and not r['wrong_side_fired']
                r['gating'] = False
                return r
            cases.append((f'thr_code{code}_{"pos" if sign > 0 else "neg"}',
                          deck(sub, netfile, body, ctl, corner, temp, 'detect threshold'), analyse))
    return cases


def slicer_delay_deck(sub, netfile, rate, corner='typical', temp=27, vdd=3.3):
    """Short run: QCK rising crossing minus the CK0 edge that caused it."""
    per = 2 / rate
    body, _ = _slicer_body(sub, per, 0, 1.0, {}, vdd, ramp=(.05, .05, 20e-9))
    ctl = '\n'.join([f'tran {per / 200:.3g} {1e-9 + 8 * per:.4g}', 'set wr_singlescale',
                     'wrdata tran.txt v(qck) v(ck0)'])
    return deck(sub, netfile, body, ctl, corner, temp, 'slicer divider delay')


APERTURE = 100e-12   # StrongARM decision instant after its tail clock edge (approx.)


def slicer_delay_from(data, vdd=3.3):
    """(dq, ds): QCK rising and the true sampling instant, relative to the CKP0 edge."""
    d = load(data)
    q = [x for x in crossings(d[:, 0], d[:, 1], vdd / 2) if x > 3e-9]
    c = crossings(d[:, 0], d[:, 2], vdd / 2)
    if not q or not c:
        return (0., APERTURE)
    ref = max(x for x in c if x <= q[0])
    # samplers are clocked directly by CKPk: decision instant = clock edge + aperture
    return (q[0] - ref, APERTURE)


# ------------------------------------------------------------------ closed-loop dual-loop CDR (extracted)
# gear + relaxed tolerances: the default trap/5p setup stops with 'timestep too small' near 0.48 us
OPT_CLOSED = '.option method=gear maxord=2 reltol=2e-3 vntol=1e-5 abstol=1e-10'
TMAX_CLOSED = '4p'
PLL_MAP = dict(REF='refp', EN='en', BAND='0', N4='0', N8='0', HOLD='0', IBIAS='ibp', LOCK='lock', FBCK='fbck', REFO='refo',
               ATB_VCTRL='vctrl', VDD='vdd', VSS='0', **{f'PH{k}': f'ph{k}' for k in range(8)})


def subckt_ports(path, name):
    """Port list of subckt `name` (header only; no device parsing)."""
    from types import SimpleNamespace
    text = Path(path).read_text().replace('\n+', ' ')
    for line in text.splitlines():
        tok = line.split()
        if len(tok) > 1 and tok[0].lower() == '.subckt' and tok[1] == name:
            return SimpleNamespace(name=name, ports=tok[2:])
    raise KeyError(name)


def ideal_phases(f, vdd=3.3, tr=50e-12):
    """PD sign check: ideal 8 ring phases at f (no PLL/CDR); VCTRL/FBCK/REF tied off for the analysis."""
    T = 1 / f
    out = [f'VPH{k} ph{k} 0 PULSE(0 {vdd} {1e-9 + k * T / 8:.6e} {tr} {tr} {T / 2 - tr:.6e} {T:.6e})' for k in range(8)]
    return out + ['VVCT vctrl 0 1.1', 'VFBT fbck 0 0', 'RREFT ref 0 1k']


def pll_inst(pll_sub):
    """timing's pt_pll_ring by port name (BAND is mapped for older netlists; HOLD (r6) is tied low;
    N4=N8=0 selects /16, the only modulus used here)."""
    return inst(pll_sub, PLL_MAP, 'XPLL')


def tb_cdr_closed(pll_sub, slicer_sub, cdr_sub, rate, bpc, ppm=0., T=2.4e-6, thold=0.9e-6, tpre=0.2e-6, vc0=0.98,
                  gain=0, vd=.2, seed=3, corner='typical', temp=27, vdd=3.3, bb=True, settle=0.3e-6,
                  track_only=False, data_rate=None, vz_node=None, ideal_ring_hz=None, data_phase=0.37):
    """Extracted closed loop: timing's pt_pll_ring (generated/pll_ring.ext.spice, unchanged) + pt_cdr + pt_slicer.
    0..thold: frequency loop (PFD locks the RX ring to REF = ring/16; VCTRL pre-charged to vc0 until tpre).
    thold..T: freq_hold=1; a bang-bang phase detector on the slicer samples drives pt_cdr BB_UP/BB_DN.
    The phase detector is analog-behavioural (switched sample/holds + smooth logic) standing in for
    pt_wrx_cdr_loop: it decides every half ring cycle instead of every 20-bit word.  Data: PRBS7, +/-vd/2 around CM 1.0 V, line rate rate*(1+ppm)."""
    fring = rate / bpc
    fref = fring / 16
    # track_only: freq_hold=1 from t=0 (PLL pump bias off), VCTRL pre-charged to vc0 (the hold value
    # measured on the extracted acquisition run) and data at data_rate (4 or 2 x the ring frequency
    # measured there): an extracted check of the bang-bang phase loop alone
    ui = 1 / ((data_rate or rate) * (1 + ppm * 1e-6))
    nb = int(T / ui) + 2
    lf = [0] * 7 + [1]
    bits = []
    s = [1, 0, 1, 1, 0, 1, 0]
    for _ in range(nb):
        b = s[6] ^ s[5]
        s = [b] + s[:6]
        bits.append(b)
    pts_p, pts_n = [], []
    t0 = data_phase * ui
    for k, b in enumerate(bits):
        t = t0 + k * ui
        v = vd / 2 if b else -vd / 2
        pts_p += [(t, 1.0 + v), (t + ui - 30e-12, 1.0 + v)]
        pts_n += [(t, 1.0 - v), (t + ui - 30e-12, 1.0 - v)]
    sm = dict(VDD_WIRE_SW='vdd', VSS='0', slicer_en='vdd', SL_P='inp', SL_N='inn', QCK='qck',
              D0='d0', E0='e0', D1='d1', E1='e1', D2='d2', E2='e2', D3='d3', E3='e3')
    sm.update({f'CKP{k}': f'ph{k}' for k in range(8)})
    sm.update({p: '0' for p in slicer_sub.ports if p.startswith('trim_')})
    cm = dict(VDD_PLL_SW='vdd', VSS='0', IBIAS='ib', cdr_en='vdd', freq_hold='hold', bb_gain='gain',
              BB_UP='bbup' if bb else '0', BB_DN='bbdn' if bb else '0', IB_PLL='ibp', VCTRL='vctrl',
              atb_cdr_pbias='pb', REF_IN='ref', REF_PLL='refp', FBCK_IN='fbck')
    # bang-bang PD (analog-behavioural stand-in for the RTL; XSPICE digital bridges made the transient
    # fail with 'timestep too small'): switched sample/holds capture phases 0-3 at the QCK rising edge
    # (tracking while QCK is low) and phases 4-7 at the falling edge; smooth logic forms early/late votes.
    hold_a = ('d0', 'e0', 'd1', 'e1')
    hold_b = ('d2', 'e2', 'd3', 'e3')
    dig = ['.model swa sw vt=1.65 vh=0.2 ron=500 roff=1e12', 'BQB qckb 0 V=3.3-v(qck)']
    for n in hold_a:
        dig += [f'SA{n} {n} h{n} qckb 0 swa', f'CH{n} h{n} 0 20f', f'BX{n} x{n} 0 V=1/(1+exp(-8*(v(h{n})-1.65)))']
    for n in hold_b:
        dig += [f'SB{n} {n} h{n} qck 0 swa', f'CH{n} h{n} 0 20f', f'BX{n} x{n} 0 V=1/(1+exp(-8*(v(h{n})-1.65)))']
    # All data/edge pairs (lead: bang-bang majority over the 4 pairs at quarter rate).  Hold A (phases
    # 0-3, captured at QCK rise) holds cycle n-1 throughout; hold B (phases 4-7, captured at QCK fall)
    # holds cycle n-2 while QCK is high and cycle n-1 while QCK is low.  A triple that spans A and B is
    # therefore consistent only in one half period and is weighted by that half (q = QCK high):
    #   inside A or inside B: always;  A(n-1) -> B: QCK low;  B(n-2) -> A(n-1) (next cycle's d0): QCK high
    q, nq = f'(v(qck)/{vdd})', f'(1-v(qck)/{vdd})'
    if bpc == 4:
        triples = [('d0', 'e0', 'd1', '1'), ('d1', 'e1', 'd2', nq), ('d2', 'e2', 'd3', '1'), ('d3', 'e3', 'd0', q)]
    else:   # half rate: data = phases 0,4 (D0, D2), edge = phases 2,6 (D1, D3)
        triples = [('d0', 'd1', 'd2', nq), ('d2', 'd3', 'd0', q)]
    late, early = [], []
    for a_, e_, b_, w_ in triples:
        tr = f'(v(x{a_})+v(x{b_})-2*v(x{a_})*v(x{b_}))'
        eqa = f'(1-(v(x{e_})+v(x{a_})-2*v(x{e_})*v(x{a_})))'
        eqb = f'(1-(v(x{e_})+v(x{b_})-2*v(x{e_})*v(x{b_})))'
        early.append(f'{w_}*{tr}*{eqa}'); late.append(f'{w_}*{tr}*{eqb}')
    # decision filter (~4 ns, about one RTL word at 2.5 Gb/s) so the pump is not toggled every
    # half ring cycle as no RTL decision rate would
    dig += [f'BVOTER voter 0 V={"+".join(late)}-({"+".join(early)})', 'RVOTE voter vote 80k', 'CVOTE vote 0 50f',
            # early (clock ahead of the data) -> slow the ring (DN); late -> UP
            f'BUP bupr 0 V={vdd}/(1+exp(-20*(v(vote)-0.5)))', f'BDN bdnr 0 V={vdd}/(1+exp(-20*(-v(vote)-0.5)))',
            'RUP bupr bbup 1k', 'CUP bbup 0 50f', 'RDN bdnr bbdn 1k', 'CDN bbdn 0 50f']
    body = '\n'.join([
        f'VDD vdd 0 {vdd}', 'RIB vdd ib 260k', f'VGA gain 0 {gain * vdd}',
        (f'VHO hold 0 {vdd}' if track_only else f'VHO hold 0 PWL(0 0 {thold} 0 {thold + 1e-9} {vdd})'),
        f'VREF refs 0 PULSE(0 {vdd} 5n 200p 200p {0.5 / fref - 200e-12} {1 / fref})', 'RREF refs ref 100',
        'CREF ref 0 10f',
        f'VEN ens 0 PWL(0 0 2n 0 2.1n {vdd})', 'REN ens en 100', 'CEN en 0 10f',   # EN edge starts the ring
        'RBAND band 0 100',
        # track_only: start the loop filter's integrating node (C1) at vc0 as well
        (f'.ic v(vctrl)={vc0} v(xpll.{vz_node})={vc0}' if (track_only and vz_node) else ''),
        '.option rshunt=1e10',
        f'VPRE pre 0 {vc0}', f'VPC pc 0 PWL(0 {vdd} {tpre} {vdd} {tpre + 1e-9} 0)',
        'SPRE vctrl pre pc 0 swpre', f'.model swpre sw vt={vdd / 2} vh=0.1 ron=50 roff=1e12',
        f'VIP inps 0 {pwl(pts_p)}', f'VIN inns 0 {pwl(pts_n)}', 'RSP inps inp 25', 'RSN inns inn 25',
        'CSP inp 0 50f', 'CSN inn 0 50f', OPT_CLOSED,
        *(ideal_phases(ideal_ring_hz, vdd) if ideal_ring_hz else [pll_inst(pll_sub), inst(cdr_sub, cm, 'XCDR')]),
        inst(slicer_sub, sm, 'XSL'), *(dig if bb else [])])
    body += '\n.save v(qck) v(d0) v(d1) v(d2) v(d3) v(vctrl) v(ph0) v(fbck) v(ref) i(VDD)' + (' v(bbup) v(bbdn)' if bb else '')
    ctl = '\n'.join([f'tran 5p {T:.4g} 0 {TMAX_CLOSED}', 'set wr_singlescale',
                     'wrdata tran.txt v(qck) v(d0) v(d1) v(d2) v(d3) v(vctrl) ' + ('v(bbup) v(bbdn)' if bb else 'v(vctrl) v(vctrl)') + ' v(ph0) v(fbck) v(ref)',
                     f'meas tran ivdd avg i(VDD) from={thold:.4g} to={T:.4g}'])

    def analyse(log, data, ui=ui, bpc=bpc, settle=settle):
        r = parse_meas(log)
        d = load(data)
        t = d[:, 0]
        q = crossings(t, d[:, 1], vdd / 2)
        P = np.median(np.diff(q)) if len(q) > 3 else None
        bitsr, tb = [], []
        for i in range(len(q) - 2):
            tn = q[i + 1]
            a = [at(d, 2, tn - .05 * P), at(d, 3, tn - .05 * P)]
            b = [at(d, 4, tn + .45 * P), at(d, 5, tn + .45 * P)]
            seq = [a[0], a[1], b[0], b[1]] if bpc == 4 else [a[0], b[0]]
            for v in seq:
                bitsr.append(int(v > vdd / 2)); tb.append(q[i])
        bitsr = np.array(bitsr); tb = np.array(tb)
        thold_ = thold
        ok = tb > thold_ + settle          # pump-bias ramp + phase pull-in after the hand-over
        errs = [i for i in range(7, len(bitsr)) if ok[i] and bitsr[i] != (bitsr[i - 7] ^ bitsr[i - 6])]
        ph = crossings(t, d[:, 9], vdd / 2)
        fr = lambda a, b: (sum(1 for x in ph if a <= x < b) - 1) / (b - a) if b > a else None
        def fit(a, b):
            n = [x for x in ph if a <= x < b]
            return (len(n) - 1) / (n[-1] - n[0]) if len(n) > 2 else None
        r.update(ring_hz_end_fit=fit(T - 0.4e-6, T), ring_hz_check_start_fit=fit(thold + settle - 0.2e-6, thold + settle))
        r.update(line_rate_bps=1 / ui, bits_per_cycle=bpc, ring_hz_acq=fr(thold - 0.2e-6, thold),
                 ring_hz_end=fr(T - 0.4e-6, T), ring_target_hz=1 / ui / bpc,
                 vctrl_at_hold=at(d, 6, thold), vctrl_end=at(d, 6, T),
                 bits_checked=int(np.sum(ok[7:])), bit_errors=len(errs),
                 first_err_ns=(tb[errs[0]] * 1e9 if errs else None),
                 up_fraction=float(np.mean(d[t > thold, 7] > vdd / 2)), dn_fraction=float(np.mean(d[t > thold, 8] > vdd / 2)))
        r['pass'] = bool(r['bits_checked'] > 500 and r['bit_errors'] == 0)
        return r
    return body, ctl, analyse


def tb_cdr_acq(pll_sub, cdr_sub, fring=625e6, T=1.6e-6, thold=1.0e-6, tpre=0.2e-6, vc0=1.15, vdd=3.3,
               up=(1.2e-6, 1.3e-6), dn=(1.4e-6, 1.5e-6)):
    """Extracted pt_pll_ring + pt_cdr (no slicer): frequency acquisition to fring (REF = fring/16), then
    freq_hold=1 at thold (PLL pump bias removed), then a BB_UP window and a BB_DN window to measure the
    bang-bang pump's frequency/phase action on the extracted VCO and filter.  8 x 25 fF phase loads
    (the slicer's clock-input capacitance is not included)."""
    fref = fring / 16
    cm = dict(VDD_PLL_SW='vdd', VSS='0', IBIAS='ib', cdr_en='vdd', freq_hold='hold', bb_gain='0',
              BB_UP='bbup', BB_DN='bbdn', IB_PLL='ibp', VCTRL='vctrl', atb_cdr_pbias='pb', REF_IN='ref',
              REF_PLL='refp', FBCK_IN='fbck')
    body = '\n'.join([
        f'VDD vdd 0 {vdd}', 'RIB vdd ib 260k',
        f'VHO hold 0 PWL(0 0 {thold} 0 {thold + 1e-9} {vdd})',
        f'VUP bbup 0 PWL(0 0 {up[0]} 0 {up[0] + 1e-9} {vdd} {up[1]} {vdd} {up[1] + 1e-9} 0)',
        f'VDNS bbdn 0 PWL(0 0 {dn[0]} 0 {dn[0] + 1e-9} {vdd} {dn[1]} {vdd} {dn[1] + 1e-9} 0)',
        f'VREFS refs 0 PULSE(0 {vdd} 5n 200p 200p {0.5 / fref - 200e-12} {1 / fref})', 'RREF refs ref 100',
        'CREF ref 0 10f',
        # softened sources + gear (as the closed bench): the stiff EN source stopped the run with
        # 'timestep too small' at a BB edge
        f'VEN ens 0 PWL(0 0 2n 0 2.1n {vdd})', 'REN ens en 100', 'CEN en 0 10f', OPT_CLOSED, '.option rshunt=1e10',
        f'VPRE pre 0 {vc0}', f'VPC pc 0 PWL(0 {vdd} {tpre} {vdd} {tpre + 1e-9} 0)',
        'SPRE vctrl pre pc 0 swpre', f'.model swpre sw vt={vdd / 2} vh=0.1 ron=50 roff=1e12',
        *[f'CP{k} ph{k} 0 25f' for k in range(8)],
        pll_inst(pll_sub),
        inst(cdr_sub, cm, 'XCDR'),
        '.save v(ph0) v(vctrl) v(fbck) v(ref) i(VDD)'])
    ctl = '\n'.join([f'tran 5p {T:.4g} 0 {TMAX_CLOSED}', 'set wr_singlescale', 'wrdata tran.txt v(ph0) v(vctrl) v(fbck) v(ref)'])

    def analyse(log, data):
        d = load(data)
        t = d[:, 0]
        ph = crossings(t, d[:, 1], vdd / 2)
        def f(a, b):
            n = [x for x in ph if a <= x < b]
            return (len(n) - 1) / (n[-1] - n[0]) if len(n) > 2 else None
        fb = crossings(t, d[:, 3], vdd / 2); rf = crossings(t, d[:, 4], vdd / 2)
        r = dict(f_acq_end=f(thold - 0.1e-6, thold), f_hold=f(thold + 0.05e-6, up[0]),
                 f_after_up=f(up[1] + 0.02e-6, dn[0]), f_after_dn=f(dn[1] + 0.02e-6, T),
                 vctrl_hold=at(d, 2, up[0]), vctrl_after_up=at(d, 2, dn[0]), vctrl_after_dn=at(d, 2, T),
                 f_target=fring)
        # phase of FBCK vs REF just before the hand-over (frequency AND phase locked)
        pre = [x for x in fb if thold - 0.1e-6 < x < thold]
        r['fb_minus_ref_ps'] = ((pre[-1] - max(y for y in rf if y <= pre[-1])) * 1e12) if pre else None
        tgt = fring
        r['acq_error_ppm'] = (r['f_acq_end'] / tgt - 1) * 1e6 if r['f_acq_end'] else None
        r['hold_drift_ppm'] = (r['f_hold'] / r['f_acq_end'] - 1) * 1e6 if r['f_hold'] and r['f_acq_end'] else None
        r['bb_up_step_ppm'] = (r['f_after_up'] / r['f_hold'] - 1) * 1e6 if r['f_after_up'] and r['f_hold'] else None
        r['bb_dn_step_ppm'] = (r['f_after_dn'] / r['f_after_up'] - 1) * 1e6 if r['f_after_dn'] and r['f_after_up'] else None
        r['pass'] = bool(r['acq_error_ppm'] is not None and abs(r['acq_error_ppm']) < 3000 and
                         (r['bb_up_step_ppm'] or 0) > 0 and (r['bb_dn_step_ppm'] or 0) < 0)
        return r
    return body, ctl, analyse


# ------------------------------------------------------------------ AC-3 closed loop (pt_cdr r-ac3)
def ac3_line(bits_n, rate, ppm=0.0, ppm_per_us=0.0, sj_ui=0.0, sj_hz=1e6, t0=0.0, t_ramp=0.0):
    """Bit start times of a line at rate*(1 + ppm + ramp) with sinusoidal jitter (UI peak).  The ramp
    (ppm/us) starts at t_ramp and is the SSC slope check.  Returns (edge times, nominal UI)."""
    ui0 = 1.0 / rate
    t, out = t0, []
    for _ in range(bits_n):
        r = ppm + (ppm_per_us * max(0.0, t - t_ramp) * 1e6 if ppm_per_us else 0.0)
        out.append(t)
        t += ui0 / (1 + r * 1e-6)
    if sj_ui:
        out = [x + sj_ui * ui0 * math.sin(2 * math.pi * sj_hz * x) for x in out]
    return out, ui0


def tb_cdr_ac3(pll_sub, slicer_sub, cdr_sub, rate, bpc, T=4.0e-6, tpre=0.8e-6, vc0=1.16, code=3, vd=.2,
               vdd=3.3, bb=True, settle=1.5e-6, ppm=0.0, ppm_per_us=0.0, sj_ui=0.0, sj_hz=1e6, lat_extra=3,
               vz_node=None, data_phase=0.37, fref=None, t_ramp=None):
    """AC-3 extracted closed loop: timing's pt_pll_ring (ext) with HOLD driven by pt_cdr r-ac3 (HOLD_PLL=1:
    PFD held from t=0, REF still toggling), pt_cdr r-ac3 (ext) pump legs on VCTRL, pt_slicer r2 (ext).
    VCTRL and the loop-filter integrator start at vc0 (released at tpre; stands in for the FLL result).
    Per-bit Alexander PD stand-in (behavioural): slicer outputs held at QCK edges (A: phases 0-3 on the
    rise, B: 4-7 on the fall), a cycle-consistent copy C (transparent while QCK is low), the previous
    cycle's last edge/data P, votes UPk = Dk^Ek, DNk = Ek^Dk+1 registered per ring cycle (V), then
    lat_extra more ring cycles of delay (the capture PD sits on the octet O, ~5 ring cycles after
    sampling) before driving pt_cdr UP0..3/DN0..3 (half rate: legs 0,1).  Pump code `code`.
    bb=False: no votes (free-running ring at vc0; measures f1)."""
    edges, ui0 = ac3_line(int(T * rate * 1.02) + 8, rate, ppm, ppm_per_us, sj_ui, sj_hz,
                          t0=data_phase / rate, t_ramp=(tpre if t_ramp is None else t_ramp))
    lf = []
    s = [1, 0, 1, 1, 0, 1, 0]
    for _ in edges:
        b = s[6] ^ s[5]
        s = [b] + s[:6]
        lf.append(b)
    pts_p, pts_n = [(0, 1.0 + (vd / 2 if lf[0] else -vd / 2))], [(0, 1.0 - (vd / 2 if lf[0] else -vd / 2))]
    for k in range(1, len(edges)):
        if lf[k] == lf[k - 1]:
            continue
        v = vd / 2 if lf[k] else -vd / 2
        pts_p += [(edges[k], 1.0 - v), (edges[k] + 30e-12, 1.0 + v)]
        pts_n += [(edges[k], 1.0 + v), (edges[k] + 30e-12, 1.0 - v)]
    fref = fref or rate / bpc / 16
    sm = dict(VDD_WIRE_SW='vdd', VSS='0', slicer_en='vdd', SL_P='inp', SL_N='inn', QCK='qck',
              D0='d0', E0='e0', D1='d1', E1='e1', D2='d2', E2='e2', D3='d3', E3='e3')
    sm.update({f'CKP{k}': f'ph{k}' for k in range(8)})
    sm.update({p: '0' for p in slicer_sub.ports if p.startswith('trim_')})
    cm = dict(VDD_PLL_SW='vdd', VSS='0', IBIAS='ib', cdr_en='en', pfd_mode='0', ref_sel='0',
              g0=('vdd' if code & 1 else '0'), g1=('vdd' if code & 2 else '0'), g2=('vdd' if code & 4 else '0'),
              FUP='0', FDN='0', IB_PLL='ibp', HOLD_PLL='holdp', VCTRL='vctrl', REF_IN='ref', WCK_IN='0',
              REF_PLL='refp', atb_cdr_pbias='pb')
    for k in range(4):
        cm[f'UP{k}'] = f'up{k}' if (bb and k < (4 if bpc == 4 else 2)) else '0'
        cm[f'DN{k}'] = f'dn{k}' if (bb and k < (4 if bpc == 4 else 2)) else '0'
    pm = dict(PLL_MAP, HOLD='holdp')
    names = ('d0', 'e0', 'd1', 'e1', 'd2', 'e2', 'd3', 'e3')
    dig = ['.model swa sw vt=1.65 vh=0.2 ron=500 roff=1e12', f'BQB qckb 0 V={vdd}-v(qck)']
    for i, n in enumerate(names):
        ck = 'qckb' if i < 4 else 'qck'            # A: track while QCK low, hold from the rise; B: the opposite
        dig += [f'SH{n} {n} h{n} {ck} 0 swa', f'CH{n} h{n} 0 20f',
                f'BX{n} x{n} 0 V=1/(1+exp(-8*(v(h{n})-1.65)))',
                f'SC{n} x{n} c{n} qckb 0 swa', f'CC{n} c{n} 0 20f']          # C: consistent copy
    dig += ['SPe3 ce3 pe3 qck 0 swa', 'CPe3 pe3 0 20f', 'SPd3 cd3 pd3 qck 0 swa', 'CPd3 pd3 0 20f']
    X = lambda a, b: f'(v({a})+v({b})-2*v({a})*v({b}))'
    if bpc == 4:
        votes = {'up0': X('cd0', 'ce0'), 'dn0': X('ce0', 'cd1'), 'up1': X('cd1', 'ce1'), 'dn1': X('ce1', 'cd2'),
                 'up2': X('cd2', 'ce2'), 'dn2': X('ce2', 'cd3'), 'up3': X('cd3', 'ce3'), 'dn3': X('pe3', 'cd0')}
    else:   # half: data phases 0,4 (D0, D2), edges 2,6 (D1, D3)
        votes = {'up0': X('cd0', 'cd1'), 'dn0': X('cd1', 'cd2'), 'up1': X('cd2', 'cd3'), 'dn1': X('pd3', 'cd0')}
    for v, expr in votes.items():
        dig += [f'BR{v} r{v} 0 V={expr}', f'SV{v} r{v} v{v}_0 qckb 0 swa', f'CV{v} v{v}_0 0 20f']
        prev = f'v{v}_0'
        for k in range(lat_extra):       # one ring cycle each: master (QCK high) + slave (QCK low)
            dig += [f'SM{v}_{k} {prev} m{v}_{k} qck 0 swa', f'CM{v}_{k} m{v}_{k} 0 20f',
                    f'SS{v}_{k} m{v}_{k} v{v}_{k + 1} qckb 0 swa', f'CS{v}_{k} v{v}_{k + 1} 0 20f']
            prev = f'v{v}_{k + 1}'
        dig += [f'BD{v} {v}r 0 V={vdd}/(1+exp(-20*(v({prev})-0.5)))', f'RD{v} {v}r {v} 1k', f'CD{v} {v} 0 50f']
    body = '\n'.join([
        f'VDD vdd 0 {vdd}', 'RIB vdd ib 260k',
        f'VREF refs 0 PULSE(0 {vdd} 5n 200p 200p {0.5 / fref - 200e-12} {1 / fref})', 'RREF refs ref 100', 'CREF ref 0 10f',
        f'VEN ens 0 PWL(0 0 2n 0 2.1n {vdd})', 'REN ens en 100', 'CEN en 0 10f',
        (f'.ic v(vctrl)={vc0} v(xpll.{vz_node})={vc0}' if vz_node else f'.ic v(vctrl)={vc0}'),
        '.option rshunt=1e10',
        f'VPRE pre 0 {vc0}', f'VPC pc 0 PWL(0 {vdd} {tpre} {vdd} {tpre + 1e-9} 0)',
        'SPRE vctrl pre pc 0 swpre', f'.model swpre sw vt={vdd / 2} vh=0.1 ron=50 roff=1e12',
        f'VIP inps 0 {pwl(pts_p)}', f'VIN inns 0 {pwl(pts_n)}', 'RSP inps inp 25', 'RSN inns inn 25',
        'CSP inp 0 50f', 'CSN inn 0 50f', OPT_CLOSED,
        inst(pll_sub, pm, 'XPLL'), inst(cdr_sub, cm, 'XCDR'), inst(slicer_sub, sm, 'XSL'), *(dig if bb else [])])
    vn = ['up0', 'dn0'] if bb else ['vctrl', 'vctrl']
    body += '\n.save v(qck) v(d0) v(d1) v(d2) v(d3) v(vctrl) v(ph0) v(holdp) i(VDD) ' + ' '.join(f'v({n})' for n in votes) if bb else \
        '\n.save v(qck) v(d0) v(d1) v(d2) v(d3) v(vctrl) v(ph0) v(holdp) i(VDD)'
    upn = [n for n in votes if n.startswith('up')] if bb else []
    dnn = [n for n in votes if n.startswith('dn')] if bb else []
    sig_up = '+'.join(f'v({n})' for n in upn) if bb else '0*v(vctrl)'
    sig_dn = '+'.join(f'v({n})' for n in dnn) if bb else '0*v(vctrl)'
    ctl = '\n'.join([f'tran 5p {T:.4g} 0 {TMAX_CLOSED}', 'set wr_singlescale',
                     f'let sup = {sig_up}', f'let sdn = {sig_dn}',
                     'wrdata tran.txt v(qck) v(d0) v(d1) v(d2) v(d3) v(vctrl) sup sdn v(ph0) v(holdp)',
                     f'meas tran ivdd avg i(VDD) from={tpre:.4g} to={T:.4g}'])

    def analyse(log, data, bpc=bpc, settle=settle, edges=edges, lf=lf):
        r = parse_meas(log)
        d = load(data)
        t = d[:, 0]
        q = crossings(t, d[:, 1], vdd / 2)
        P = np.median(np.diff(q)) if len(q) > 3 else None
        bitsr, tb = [], []
        for i in range(len(q) - 2):
            tn = q[i + 1]
            a = [at(d, 2, tn - .05 * P), at(d, 3, tn - .05 * P)]
            b = [at(d, 4, tn + .45 * P), at(d, 5, tn + .45 * P)]
            seq = [a[0], a[1], b[0], b[1]] if bpc == 4 else [a[0], b[0]]
            for v in seq:
                bitsr.append(int(v > vdd / 2)); tb.append(q[i])
        bitsr = np.array(bitsr); tb = np.array(tb)
        ok = tb > tpre + settle
        # PRBS7 self-check: every recovered bit must equal the XOR of the bits 6 and 7 before it (a
        # slipped or wrong bit breaks it for the following 7 checks; no alignment to the source needed)
        errs = [i for i in range(7, len(bitsr)) if ok[i] and bitsr[i] != (bitsr[i - 7] ^ bitsr[i - 6])]
        ph = crossings(t, d[:, 9], vdd / 2)
        def fit(a, b):
            n = [x for x in ph if a <= x < b]
            return (len(n) - 1) / (n[-1] - n[0]) if len(n) > 2 else None
        nchk = int(np.sum(ok[7:]))
        sel = t > tpre + settle
        r.update(line_rate_bps_nominal=rate, ppm=ppm, ppm_per_us=ppm_per_us, sj_ui=sj_ui, sj_hz=sj_hz, code=code,
                 bits_per_cycle=bpc, ring_hz_free_fit=fit(max(0, tpre - 0.3e-6), tpre),
                 ring_hz_end_fit=fit(T - 0.4e-6, T), ring_hz_target_end=None,
                 vctrl_at_release=at(d, 6, tpre), vctrl_end=at(d, 6, T),
                 vctrl_span_check=(float(np.max(d[sel, 6]) - np.min(d[sel, 6])) if np.any(sel) else None),
                 bits_checked=nchk, bit_errors=len(errs), first_err_ns=(tb[errs[0]] * 1e9 if errs else None),
                 hold_pll_min_v=float(np.min(d[t > 5e-9, 10])) if np.any(t > 5e-9) else None,
                 up_activity=float(np.mean(d[sel, 7])) / vdd if bb and np.any(sel) else None,
                 dn_activity=float(np.mean(d[sel, 8])) / vdd if bb and np.any(sel) else None)
        r['ber_95_upper'] = (3.0 / nchk) if (nchk and not errs) else None
        r['pass'] = bool(bb and nchk > 2000 and not errs and r['hold_pll_min_v'] is not None and r['hold_pll_min_v'] > vdd - 0.4)
        return r
    return body, ctl, analyse
