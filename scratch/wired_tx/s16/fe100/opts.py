"""Options bench for closing the 100BASE-TX gap (wraps sweep.py, the bias-path bench, +3.4 % vs the full chain at ss-pess).
  vcas  : pad CASCODE gate from an ideal source (default VDD)
  wscale: W of the pad cascodes (nfet_06v0, gate CASCODE) and switches (nfet_03v3, gate MAIN_P/N POST_P/N) x k (ad/as/pd/ps scaled too)
  ratio : magnetics chip:line = 1:n (chip side more turns, n < 1), ideal transformer (E/F) + OCL 350 uH referred to the chip
          side (350u/n^2); back-termination Rb = 49.9/n^2 per leg (source seen from the line stays 100 ohm differential),
          filter impedance-scaled: L = 98n/n^2 per leg, C = 19.6p * n^2. Line amplitude = 25 I / n, leg drop = 37.4 I / n^2.
  vct   : B39 centre tap
  mode  : 'tran' (MLT-3 stream, as sweep.py) or 'ac' (RL at the RJ45, line side, 100 ohm reference, static -1 state)
"""
import sys, json, re, time
from pathlib import Path
import numpy as np
H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
import sweep, anchor, stream
from chain13 import tools

RES = H / 'results'; RUNS = H / 'runs'
A16 = H / 'a16_bench.spice'      # a16_wrap.spice + pads-core/esdopt/tx/sec/models/a16_rt.spice
sweep.C13.PADFILE['A16'] = A16; sweep.C13.PADLABEL['A16'] = 'pad=a16_rt (up-diodes, DVDD=VDD)'
A16MAP = {'xpad.xphysical.sum_p_d_0)': 'xpad.xphysical.sum_p_d_0__3)', 'xpad.xphysical.sum_n_d_0)': 'xpad.xphysical.sum_n_d_0__3)',
          'xpad.xphysical.pad_p__2)': 'xpad.xphysical.pad_p__37)', 'xpad.xphysical.pad_n__2)': 'xpad.xphysical.pad_n__37)',
          'v(xpad.esd_rail)': 'v(ATBPAD)'}
SW = ('MAIN_P', 'MAIN_N', 'POST_P', 'POST_N')


def scale_pad(txt, k):
    out, n06, n03 = [], 0, 0
    for l in txt.splitlines():
        p = l.split()
        if p and p[0][0] == 'X' and len(p) > 5 and ((p[5] == 'nfet_06v0' and p[2] == 'CASCODE') or (p[5] == 'nfet_03v3' and p[2] in SW)):
            def sc(m):
                key, val, unit = m.group(1), float(m.group(2)), m.group(3)
                return f'{key}={val * (k if key in ("w", "pd", "ps") else k):.6g}{unit}'
            l = re.sub(r'\b(w|ad|as|pd|ps)=([\d.eE+-]+)([a-zA-Z]*)', sc, l)
            n06 += p[5] == 'nfet_06v0'; n03 += p[5] == 'nfet_03v3'
        out.append(l)
    return '\n'.join(out) + '\n', n06, n03


def board_n(n, vct):
    return [f'VCT CT 0 {vct}', f'RBT_P CT BOARD_P {49.9 / n**2:.5g}', f'RBT_N CT BOARD_N {49.9 / n**2:.5g}',
            f'LF_P BOARD_P RJ_P {98e-9 / n**2:.5g}', f'LF_N BOARD_N RJ_N {98e-9 / n**2:.5g}', f'CF RJ_P RJ_N {19.6e-12 * n**2:.5g}',
            f'LMAG RJ_P RJ_N {350e-6 / n**2:.5g}',
            f'ELN LPX LN RJ_P RJ_N {n}', 'VSNS LPX LP 0', f'FCH RJ_P RJ_N VSNS {n}', 'VLN LN 0 0', 'RLINE LP LN 100']


def deck(w, *, vcas=None, wscale=1.0, ratio=1.0, mode='tran', **kw):
    if mode == 'ac':
        kw['sy'] = np.array([-1, -1])
    info = {}
    if wscale != 1.0:     # scale BEFORE the pess pass (pess_all inserts gate resistors and renames the gate nodes)
        pt, n06, n03 = scale_pad(sweep.B.clean(sweep.C13.PADFILE[kw['pad_model']].read_text()), wscale)
        f = w / 'pad_scaled_src.spice'; f.write_text(pt)
        sweep.C13.PADFILE['W'] = f; sweep.C13.PADLABEL['W'] = f'pad={kw["pad_model"]} W x{wscale}'
        kw['pad_model'] = 'W'
        info['scaled'] = dict(nfet_06v0_cascodes=n06, nfet_03v3_switches=n03)
    names, t0 = sweep.deck(w, **kw)
    vdd = kw['vdd']
    L = (w / 'tb.sp').read_text().split('\n')
    out = []
    for l in L:
        if l.startswith('VCAS ') and vcas is not None:
            l = f'VCAS CAS_SRC 0 {vcas}'
        if ratio != 1.0 and l.startswith(('RBT_', 'LF_', 'CF ', 'LMAG', 'RLINE')):
            continue
        if ratio != 1.0 and l.startswith('VCT '):
            out += board_n(ratio, float(l.split()[3])); continue
        out.append(l)
    rj = ('LP', 'LN') if ratio != 1.0 else ('RJ_P', 'RJ_N')
    extra = ' v(cascode) v(xpad.xphysical.pad_p__2) v(xpad.xphysical.pad_n__2) v(xpad.esd_rail) i(VCT)'
    for i, l in enumerate(out):
        if l.startswith(('save ', 'wrdata ')):
            out[i] = l.replace('v(RJ_P) v(RJ_N)', f'v({rj[0]}) v({rj[1]})') + extra
    names = names + ['CAS', 'DP', 'DN', 'ESDR', 'ICT']
    if kw.get('pad_model') == 'A16':
        out = ['VDVD VDD ATBPAD 0' if l.startswith('RATB ') else l for l in out]
        for i, l in enumerate(out):
            if l.startswith(('save ', 'wrdata ')):
                for a_, b_ in A16MAP.items():
                    l = l.replace(a_, b_)
                out[i] = l + ' i(VDVD)'
        names = names + ['IDVD']
    if mode == 'ac':
        out = [l for l in out if not l.startswith(('save ', 'wrdata ', 'set wr_', 'run'))]
        out = [l for l in out if not (l.startswith('RLINE'))]
        i = next(k for k, l in enumerate(out) if l.startswith('.tran'))
        out[i] = '.ac dec 40 1meg 100meg'
        out.insert(i, f'RPORT {rj[0]} XA 100'); out.insert(i, f'VAC XA {rj[1]} DC 0 AC 1')
        j = out.index('.control')
        out[j + 1:j + 1] = ['run', f'let z = v({rj[0]},{rj[1]}) / (-i(VAC))', 'let gam = (z - 100) / (z + 100)', 'let rl = -db(gam)',
                            'let zp = v(PAD_P,PAD_N) / (-i(VAC))', 'wrdata rl.txt rl']
    (w / 'tb.sp').write_text('\n'.join(out))
    return names, t0, info


def rl_limit(f):
    m = f / 1e6
    return np.where(m <= 30, 16.0, np.where(m <= 60, 16 - 20 * np.log10(m / 30), 10.0))


def run(tag, corner='ss', pess=False, vdd=3.15, code=255, post_code=None, pol=1, pad_model='RT', gate=None, nsym=26, vct=3.3,
        vcas=None, wscale=1.0, ratio=1.0, mode='tran'):
    post_code = code if post_code is None else post_code
    gate = gate or (round(0.330 * vdd, 3), round(0.848 * vdd, 3))
    temp = anchor.TEMP[corner]; rate = anchor.RATE
    sy = stream.mlt3(anchor.START + nsym)[anchor.START:]
    w = RUNS / tag; w.mkdir(parents=True, exist_ok=True)
    names, t0, info = deck(w, vcas=vcas, wscale=wscale, ratio=ratio, mode=mode, corner=corner, temp=temp, vdd=vdd, pess=pess, code=code,
                           post_code=post_code, pol=pol, pad_model=pad_model, gate=gate, sy=sy, rate=rate, vct=vct)
    ts0 = time.time(); tools.ngspice_host(w, 'tb.sp', timeout=20000)
    out = dict(tag=tag, mode=mode, corner=corner, pess=pess, vdd=vdd, vct=vct, vcas=vcas if vcas is not None else vdd, wscale=wscale, ratio=ratio,
               main_code=code, post_code=post_code, pad=pad_model, gate_v=list(gate), sec=round(time.time() - ts0), **info)
    if mode == 'ac':
        if (w / 'rl.txt').exists():
            d = np.loadtxt(w / 'rl.txt'); f, rl = d[:, 0], d[:, 1]
            s = (f >= 2e6) & (f <= 80e6); mg = rl[s] - rl_limit(f[s])
            out.update(rl_min_db=round(float(rl[s].min()), 2), rl_margin_min_db=round(float(mg.min()), 2),
                       at_mhz=round(float(f[s][np.argmin(mg)] / 1e6), 1), rl_pass=bool(mg.min() >= 0),
                       rl_db={f'{m}MHz': round(float(np.interp(m * 1e6, f, rl)), 1) for m in (2, 10, 30, 60, 80)})
    elif (w / 'wave.txt').exists():
        a = tools.read_wrdata(w / 'wave.txt', names)
        a['t_score'] = t0 + 6 * anchor.N / rate
        m = anchor.measure(a['time'], a, sy, anchor.N / rate, t0, vdd)
        s = a['time'] > a['t_score']
        vds = np.maximum(a['DP'] - a['SUMP0'], a['DN'] - a['SUMN0'])
        vgs = np.maximum(a['CAS'] - a['SUMP0'], a['CAS'] - a['SUMN0'])
        vgd = np.maximum(np.abs(a['CAS'] - a['DP']), np.abs(a['CAS'] - a['DN']))
        ileg = -(a['ILP'] + a['ILN'])
        if 'IDVD' in a:
            m['updiode_ma_max'] = round(float(np.max(-a['IDVD'][s])) * 1e3, 3)
        m.update(pad_max_v=round(float(max(a['PAD_P'][s].max(), a['PAD_N'][s].max())), 3), sum_max_v=round(float(max(a['SUMP0'][s].max(), a['SUMN0'][s].max())), 3), sum_min_v=round(float(min(a['SUMP0'][s].min(), a['SUMN0'][s].min())), 3),
                 cascode_max_v=dict(vgs=round(float(vgs[s].max()), 2), vgd=round(float(vgd[s].max()), 2), vds=round(float(vds[s].max()), 2),
                                    vg=round(float(a['CAS'][s].max()), 2), vd=round(float(max(a['DP'][s].max(), a['DN'][s].max())), 2)),
                 esd_rail_v=round(float(a['ESDR'][s].mean()), 3),
                 ct_minus_legs_ua=round(float(np.mean(-a['ICT'][s] - ileg[s]) * 1e6), 1))
        out['meas'] = m
    for f_ in w.glob('*'):
        if f_.name not in ('tb.sp', 'tb.sp.log'):
            f_.unlink()
    RES.mkdir(exist_ok=True); (RES / f'{tag}.json').write_text(json.dumps(out, indent=1, default=str))
    return out


if __name__ == '__main__':
    o = run(**json.loads(sys.argv[1])); m = o.get('meas', {})
    print(o['tag'], o['sec'], 'amp', m.get('amp_mv'), 'sym', m.get('symmetry'), 'on', (m.get('ILN') or {}).get('held_p1_ma'),
          'pad', m.get('pad_min_v'), 'sum', m.get('sum_min_v'), m.get('sum_max_v'), 'cas', m.get('cascode_max_v'), 'esd', m.get('esd_rail_v'),
          'leak_ua', m.get('ct_minus_legs_ua'), 'rl', o.get('rl_min_db'), o.get('rl_margin_min_db'), o.get('at_mhz'), o.get('rl_db'), flush=True)


def padc(tag, wscale=1.0, corner='typical', vdd=3.3):
    """single-ended capacitance of PAD_P (both legs held at 3.3 V, tails at code 0, cascode at VDD), 50 MHz."""
    w = RUNS / tag; w.mkdir(parents=True, exist_ok=True)
    deck(w, wscale=wscale, mode='ac', corner=corner, temp=anchor.TEMP[corner], vdd=vdd, pess=False, code=0, post_code=0, pol=1,
         pad_model='RT', gate=(0.330 * vdd, 0.848 * vdd), sy=None, rate=anchor.RATE, vct=3.3)
    L = (w / 'tb.sp').read_text().split('\n')
    i = next(k for k, l in enumerate(L) if l.startswith('RATB'))
    L = L[:i + 1] + ['VACP PAD_P 0 DC 3.3 AC 1', 'VACN PAD_N 0 DC 3.3', '.ac lin 1 50meg 50meg', '.control', 'run',
                     'print imag(-i(VACP))', '.endc', '.end']
    (w / 'tb.sp').write_text('\n'.join(L)); tools.ngspice_host(w, 'tb.sp')
    y = float(re.search(r'imag\(-i\(vacp\)\)\s*=\s*([-\d.eE+]+)', (w / 'tb.sp.log').read_text()).group(1))
    c = y / (2 * np.pi * 50e6)
    for f_ in w.glob('*'):
        if f_.name not in ('tb.sp', 'tb.sp.log'):
            f_.unlink()
    o = dict(tag=tag, wscale=wscale, pad_p_c_pf=round(c * 1e12, 3)); (RES / f'{tag}.json').write_text(json.dumps(o)); print(o, flush=True)
    return o
