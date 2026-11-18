"""POST tap from settled levels: far-end level at bits whose 3 predecessors are equal (settled, s) and at first bits
after a transition (peak, k).  De-emphasis ratio r = p/m from s = m - p, k ~ m + p (pol 0);  same sign: three levels."""
import sys, json
sys.path.insert(0, '../s12'); sys.path.insert(0, '../s12/mux')
import numpy as np
from chain import S, tools


def load(d):
    r = json.load(open(f'{d}/result.json'))
    tb = open(f'{d}/tb.sp').read()
    names = [x[2:-1] for x in tb[tb.index('wrdata wave.txt') + 16:].split('\n')[0].split()]
    names = [n if n.lower() != 'vdd' else 'I' for n in names]
    w = tools.read_wrdata(f'{d}/wave.txt', names); t = w['time']
    ui = 1 / r['rate']; nb = int(round((t[-1] - 1e-9) / ui)) - 4
    bits = np.array(S.prbs7_bits(nb + 8))
    v = w['FAR_P'] - w['FAR_N']; v = v - np.mean(v[t > 5e-9])
    return r, t, v, ui, nb, bits


def levels(d, pol=None):
    r, t, v, ui, nb, bits = load(d)
    pol = r['pol'] if pol is None else pol
    n = np.arange(16, nb - 36); b = 2 * bits[n] - 1
    hist = [2 * bits[n - i] - 1 for i in range(1, 4)]
    settled = (hist[0] == b) & (hist[1] == b) & (hist[2] == b)
    first = (hist[0] != b)
    best = None
    for lat in range(-2, 30):
        for phi in np.arange(0, 1, 1 / 16):
            vs = np.interp(1e-9 + (n + lat + phi) * ui, t, v)
            if pol == 0 or not r.get('post_bias'):
                key = abs(float(np.mean(vs * b)))                       # binary: correlation with the bit
            else:
                key = abs(float(np.mean(vs * (b + hist[0]))))           # three-level: correlation with b[n] + b[n-1]
            if best is None or key > best[0]:
                best = (key, lat, phi, vs)
    key, lat, phi, vs = best
    sg = np.sign(np.mean(vs * b)) or 1.0
    vs = vs * sg
    out = dict(tag=d.split('/')[-1], pol=pol, lat=lat, phi=phi, i_ma=r['i_ma'], post_bias=r.get('post_bias'), mbias=r.get('mbias', 1.9))
    if pol == 0 or not r.get('post_bias'):
        s = float(np.mean(vs[settled] * b[settled])); k = float(np.mean(vs[first] * b[first]))
        out.update(settled_v=round(s, 4), first_v=round(k, 4), inner_eye_v=round(float(2 * np.min(vs * b)), 4),
                   errors=int(np.sum(vs * b <= 0)), bits=int(len(n)))
    else:
        three = b + hist[0]
        outer = np.abs(vs[three != 0]); zero = np.abs(vs[three == 0])
        wrong = int(np.sum(np.sign(vs[three != 0]) != np.sign(three[three != 0])))
        out.update(outer_min_v=round(float(outer.min()), 4), outer_mean_v=round(float(outer.mean()), 4), zero_max_v=round(float(zero.max()), 4),
                   margin_v=round(float(outer.min() - zero.max()), 4), wrong_sign=wrong, bits=int(len(n)),
                   pos_mean=round(float(vs[three == 2].mean()), 4), neg_mean=round(float(vs[three == -2].mean()), 4))
    return out


if __name__ == '__main__':
    ref = levels(sys.argv[1]) if len(sys.argv) > 2 else None
    for d in sys.argv[2:] or sys.argv[1:]:
        o = levels(d)
        if ref and 'settled_v' in o:
            o['r_p_over_m'] = round((1 - o['settled_v'] / ref['settled_v']) , 3)
        print(json.dumps(o))
