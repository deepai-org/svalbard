"""three-level view of a mux/m8 run with POST on: far-end sample vs main bit b[n] and previous bit b[n-1]."""
import sys, json
sys.path.insert(0, '../s12'); sys.path.insert(0, '../s12/mux')
import numpy as np
from chain import S, tools
d = sys.argv[1]
r = json.load(open(f'{d}/result.json'))
tb = open(f'{d}/tb.sp').read()
names = [x[2:-1] for x in tb[tb.index('wrdata wave.txt') + 16:].split('\n')[0].split()]
names = [n if n.lower() != 'vdd' else 'I' for n in names]
w = tools.read_wrdata(f'{d}/wave.txt', names); t = w['time']
rate = r['rate']; ui = 1 / rate; nb = int(round((t[-1] - 1e-9) / ui)) - 4
bits = np.array(S.prbs7_bits(nb + 8))
v = w['FAR_P'] - w['FAR_N']; v = v - np.mean(v[t > 5e-9])
best = None
for lat in range(-2, 30):
    for phi in np.arange(0, 1, 1 / 16):
        n = np.arange(16, nb - 36)
        vs = np.interp(1e-9 + (n + lat + phi) * ui, t, v)
        b = 2 * bits[n] - 1; bp = 2 * bits[n - 1] - 1
        A = np.linalg.lstsq(np.stack([b, bp], 1), vs, rcond=None)
        resid = vs - np.stack([b, bp], 1) @ A[0]
        key = float(np.std(resid))
        if best is None or key < best[0]:
            best = (key, lat, phi, A[0], resid, vs, b, bp)
key, lat, phi, a, resid, vs, b, bp = best
print(d.split('/')[-1], 'pol', r['pol'], 'lat', lat, 'phi', phi, 'main tap V', round(a[0], 3), 'post tap V', round(a[1], 3), 'ratio', round(a[1] / a[0], 3),
      'resid rms', round(key, 3), 'max', round(float(np.abs(resid).max()), 3))
for lvl in (-2, 0, 2):
    m = (b + bp) == lvl
    for sgn in ((1, -1) if lvl == 0 else (0,)):
        mm = m & ((b == sgn) if lvl == 0 else True)
        print(f'   b+b-1={lvl:+d} b={sgn:+d}: n={mm.sum():3d} min {vs[mm].min():+.3f} mean {vs[mm].mean():+.3f} max {vs[mm].max():+.3f}')
