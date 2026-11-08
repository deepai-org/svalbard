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
             TERM_ENABLE='te', DIFF_ENABLE='de', TERM_VCM='vcm')
    body = '\n'.join([
        f'VDD vdd 0 {V}', step_src('VEN', 'en', en, V), step_src('VM0', 'm0', m0, V), step_src('VM1', 'm1', m1, V),
        # pad bank model on TERM_VCM: two legs of 24 ohm + switch into a 25 ohm (100 ohm diff, AC-coupled) line;
        # common-mode load only: legs are a DC-isolated source here, plus 17.8 mA HS driver current in USB mode
        'CL1 te 0 300f', 'CL2 de 0 200f',
        'Iusb 0 vcm PWL(0 0 400n 0 400.1n 17.8m 450n 17.8m 450.1n 0)',
        inst(sub, m)])
    ctl = '\n'.join([
        'tran 0.2n 900n', 'set wr_singlescale', 'wrdata tran.txt v(vcm) v(te) v(de) i(VDD)',
        'meas tran vcm_div find v(vcm) at=290n', 'meas tran vcm_gnd_17m8 find v(vcm) at=440n',
        'meas tran vcm_gnd find v(vcm) at=390n', 'meas tran te_div find v(te) at=290n', 'meas tran de_div find v(de) at=290n',
        'meas tran te_gnd find v(te) at=440n', 'meas tran de_diff find v(de) at=690n', 'meas tran te_diff find v(te) at=690n',
        'meas tran vcm_diff find v(vcm) at=690n', 'meas tran idd_div avg i(VDD) from=250n to=290n',
        'meas tran idd_off avg i(VDD) from=800n to=890n', 'meas tran idd_reset avg i(VDD) from=10n to=45n',
        'meas tran te_off find v(te) at=890n', 'meas tran vcm_off find v(vcm) at=890n',
        'meas tran t_settle when v(vcm)=1.14 rise=1 td=50n'])

    def analyse(log, data):
        r = parse_meas(log)
        r['vcm_gnd_ron_ohm'] = (r['vcm_gnd_17m8'] - r['vcm_gnd']) / 17.8e-3 if 'vcm_gnd_17m8' in r else None
        r['vcm_settle_ns'] = (r['t_settle'] - 50e-9) * 1e9 if 't_settle' in r else None
        r['pass'] = bool(abs(r.get('vcm_div', 0) - 1.2) < .1 and r.get('te_div', 0) > .9 * V and r.get('de_div', 1) < .1
                         and r.get('vcm_gnd_ron_ohm', 99) < 3 and r.get('de_diff', 0) > .9 * V and r.get('te_diff', 1) < .1
                         and r.get('te_off', 1) < .1 and abs(r.get('idd_off', 1)) < 1e-6)
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
                ctle_peak1='p1', RX_P='inp', RX_N='inn', CTLE_P='outp', CTLE_N='outn',
                atb_ctle_pbias='pb', atb_ctle_src='src')
    for en, byp, code in ((1, 0, 0), (1, 0, 1), (1, 0, 2), (1, 0, 3), (0, 1, 0), (0, 0, 0)):
        body = '\n'.join([f'VDD vdd 0 {vdd}', 'RIB vdd ib 260k', f'VEN en 0 {en * vdd}', f'VBY byp 0 {byp * vdd}',
                          f'VP0 p0 0 {(code & 1) * vdd}', f'VP1 p1 0 {(code >> 1) * vdd}',
                          f'VIP vip 0 DC {cm} AC 0.5', f'VIN vin 0 DC {cm} AC -0.5',
                          'RSP vip inp 25', 'RSN vin inn 25',
                          'CLP outp 0 150f', 'CLN outn 0 150f', inst(sub, base)])
        ctl = '\n'.join(['op', 'print v(outp) v(outn) v(src) v(pb) i(VDD)', 'let idd=-i(VDD)', 'print idd',
                         'ac dec 40 1e6 2e10', 'let g=db(v(outp)-v(outn))',
                         'meas ac gdc find g at=1e6', 'meas ac gpk max g',
                         'meas ac g625 find g at=625e6', 'meas ac g1g25 find g at=1.25e9', 'meas ac g2g5 find g at=2.5e9',
                         'let gt=gdc-3', 'meas ac bw3db when g=gt fall=last',
                         'set wr_singlescale', 'wrdata ac.txt g'])

        def analyse(log, data, en=en, byp=byp):
            r = parse_meas(log)
            m = __import__('re').search(r'idd = ([-+0-9.eE]+)', log)
            r['idd_a'] = float(m.group(1)) if m else None
            if en:
                r['peaking_db'] = r.get('gpk', 0) - r.get('gdc', 0)
                r['pass'] = bool(-12 < r.get('gdc', -99) < 4 and r.get('g1g25', -99) > -3 and (r['idd_a'] or 0) < 12e-3)
            elif byp:
                r['pass'] = bool(r.get('gdc', -99) > -2 and r.get('bw3db', 0) > 1.5e9)
            else:
                r['pass'] = bool(r.get('gdc', 0) < -30 and abs(r['idd_a'] or 1) < 1e-6)
            return r
        name = f'ac_code{code}' if en else ('ac_bypass' if byp else 'ac_off')
        cases.append((name, deck(sub, netfile, body, ctl, corner, temp, f'ctle {name}'), analyse))
    return cases


# ------------------------------------------------------------------ slicer
def _slicer_body(sub, per, vd, cm, trims, vdd, n_bits=24, seed=1, ramp=None, tstop=None, delay=0.):
    # per = 2 UI; the eight quarter-rate clocks CKPk (period 2*per) are k*per/4 apart
    m = dict(VDD_WIRE_SW='vdd', VSS='0', slicer_en='en', SL_P='inp', SL_N='inn', QCK='qck',
             D0='d0', E0='e0', D1='d1', E1='e1', D2='d2', E2='e2', D3='d3', E3='e3')
    m.update({f'CKP{k}': ('ck0' if k == 0 else f'ckp{k}') for k in range(8)})
    for s in ('d0', 'e0', 'd1', 'e1'):
        for b in ('p0', 'p1', 'n0', 'n1'):
            m[f'trim_{s}_{b}'] = 'tvdd' if trims.get(s, {}).get(b) else '0'
    P = 2 * per
    tr = P / 40
    lines = [f'VDD vdd 0 {vdd}', f'VT tvdd 0 {vdd}', f'VEN en 0 PWL(0 0 0.5n {vdd})']
    for k in range(8):
        name = 'ck0' if k == 0 else f'ckp{k}'
        lines.append(f'V{name} {name} 0 PULSE(0 {vdd} {1e-9 + k * P / 8:.4g} {tr:.3g} {tr:.3g} {P / 2 - tr:.4g} {P:.4g})')
    ui = per / 2
    if ramp is None:
        rng = np.random.default_rng(seed)
        bits = rng.integers(0, 2, n_bits)
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
TRIM_NOMINAL = {k: {'p0': 1} for k in ('d0', 'e0', 'd1', 'e1')}


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
    for label, trims in () if not offsets else (('trim0', {}), ('trim_p0', TRIM_NOMINAL), ('trim_n1', {k: {'n1': 1} for k in ('d0', 'e0', 'd1', 'e1')}), ('trim_p3', {k: {'p0': 1, 'p1': 1} for k in ('d0', 'e0', 'd1', 'e1')}),
                         ('trim_n3', {k: {'n0': 1, 'n1': 1} for k in ('d0', 'e0', 'd1', 'e1')})):
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
                     'meas tran t_sep when v(sep)=1.65 rise=1', 'meas tran t_sen when v(sen)=1.65 rise=1',
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
    """Static currents of the dual-loop CDR cell: IB_PLL into a 0.8 V diode-like load (PLL IBIAS pin)
    and the bang-bang pump current into VCTRL held at 1.1 V, for every control state."""
    states = [  # name, en, hold, gain, up, dn
        ('acq', 1, 0, 0, 0, 0), ('hold_idle', 1, 1, 0, 0, 0), ('hold_up', 1, 1, 0, 1, 0), ('hold_dn', 1, 1, 0, 0, 1),
        ('hold_up_g', 1, 1, 1, 1, 0), ('hold_dn_g', 1, 1, 1, 0, 1), ('acq_up', 1, 0, 0, 1, 0), ('off', 0, 0, 0, 1, 1)]
    cases = []
    for name, en, hold, gain, up, dn in states:
        m = dict(VDD_PLL_SW='vdd', VSS='0', IBIAS='ib', cdr_en='en', freq_hold='hold', bb_gain='gain',
                 BB_UP='up', BB_DN='dn', IB_PLL='ibp', VCTRL='vc', atb_cdr_pbias='pb', REF_IN='0', REF_PLL='refp', FBCK_IN='fbk')
        body = '\n'.join([f'VDD vdd 0 {vdd}', 'RIB vdd ib 260k', f'VEN en 0 {en * vdd}', f'VHO hold 0 {hold * vdd}',
                          f'VGA gain 0 {gain * vdd}', f'VUP up 0 {up * vdd}', f'VDN dn 0 {dn * vdd}',
                          # PLL IBIAS pin load = its NMOS diode (4/2), sensed by a 0 V source
                          'VIBP ibp ibpd 0', 'XNBD ibpd ibpd 0 0 nfet_03v3 w=4u l=2u', 'VVC vc 0 1.1',
                          # pt_pll_ring FBCK (39 MHz) clocks the hand-over flops; static when the PLL is off
                          (f'VFB fbk 0 PULSE(0 {vdd} 10n 200p 200p 12.6n 25.6n)' if en else 'VFB fbk 0 0'),
                          inst(sub, m)])
        ctl = '\n'.join(['tran 0.2n 400n', 'meas tran i_ibpll avg i(VIBP) from=300n to=400n',
                         'meas tran i_bb avg i(VVC) from=300n to=400n', 'meas tran i_vdd_n avg i(VDD) from=300n to=400n',
                         'let i_vdd = -i_vdd_n', 'print i_vdd'])

        def analyse(log, data, name=name, en=en, hold=hold, gain=gain, up=up, dn=dn):
            import re
            g = lambda k: float(re.search(rf'^{k}\s*=\s*([-+0-9.eE]+)', log, re.M).group(1))
            r = dict(i_ibpll_uA=g('i_ibpll') * 1e6, i_bb_nA=g('i_bb') * 1e9, i_vdd_uA=g('i_vdd') * 1e6)
            want_ib = 10 if (en and not hold) else 0
            want_bb = 0 if not (en and hold) or up == dn else (1 if up else -1) * (2 if gain else 1) * 60
            r['pass'] = bool(abs(r['i_ibpll_uA'] - want_ib) < 3 and
                             (abs(r['i_bb_nA']) < 5 if want_bb == 0 else 0.4 < r['i_bb_nA'] / want_bb < 2.5)
                             and (en or abs(r['i_vdd_uA']) < 1))
            return r
        cases.append((name, deck(sub, netfile, body, ctl, corner, temp, f'cdr {name}'), analyse))
    return cases


BENCHES = dict(termination=[tb_termination], rxlevel=[tb_rxlevel], rxselect=[tb_rxselect], wmon_sel=[tb_wmon_sel],
               ctle=[tb_ctle], slicer=[tb_slicer], detect=[tb_detect], cdr=[tb_cdr])


# ------------------------------------------------------------------ generic safety benches
PORTS = dict(
    termination=dict(ctrl=['term_en', 'term_mode0', 'term_mode1'], clk=[], ain=[], bias=[],
                     out=['TERM_ENABLE', 'DIFF_ENABLE', 'TERM_VCM']),
    rxlevel=dict(ctrl=['rxlevel_en', 'rxlevel_half'], clk=[], ain=[], bias=[], out=['DIV_ENABLE', 'BYPASS_ENABLE']),
    rxselect=dict(ctrl=['rxselect_en', 'rxselect_direct'], clk=[], ain=['CTLE_P', 'CTLE_N', 'RX_P', 'RX_N'], bias=[],
                  out=['SL_P', 'SL_N']),
    wmon_sel=dict(ctrl=['wmon_en', 'wmon_sel0', 'wmon_sel1'], clk=[], ain=['RX_P', 'RX_N', 'CTLE_P', 'CTLE_N'], bias=[],
                  out=['WMON_IN']),
    ctle=dict(ctrl=['ctle_en', 'wire_ctle_bypass', 'ctle_peak0', 'ctle_peak1'], clk=[], ain=['RX_P', 'RX_N'],
              bias=['IBIAS'], out=['CTLE_P', 'CTLE_N'], atb=['atb_ctle_pbias', 'atb_ctle_src']),
    slicer=dict(ctrl=['slicer_en'] + [f'trim_{s}_{b}' for s in ('d0', 'e0', 'd1', 'e1') for b in ('p0', 'p1', 'n0', 'n1')],
                clk=[f'CKP{k}' for k in range(8)], ain=['SL_P', 'SL_N'], bias=[], out=['D0', 'E0', 'D1', 'E1', 'D2', 'E2', 'D3', 'E3', 'QCK']),
    detect=dict(ctrl=['det_en', 'det_thr0', 'det_thr1', 'det_se0', 'det_se1', 'det_src_tx', 'det_inject'],
                clk=['det_clk'], ain=['RX_P', 'RX_N', 'TX_P', 'TX_N'], bias=['IBIAS'],
                out=['DIFF_POS', 'DIFF_NEG', 'SE_P', 'SE_N'], atb=['atb_det_vref']),
    cdr=dict(ctrl=['cdr_en', 'freq_hold', 'bb_gain', 'BB_UP', 'BB_DN'], clk=['REF_IN', 'FBCK_IN'], ain=['VCTRL'], bias=['IBIAS'],
             out=['IB_PLL', 'REF_PLL'], atb=['atb_cdr_pbias']),
)
ENABLE = dict(termination='term_en', rxlevel='rxlevel_en', rxselect='rxselect_en', wmon_sel='wmon_en', ctle='ctle_en',
              slicer='slicer_en', detect='det_en', cdr='cdr_en')


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
