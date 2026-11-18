"""CH1: what the real COB channel costs for a given pad impedance (differential), per-chip tuned carrier parts.
Channel model: scratch/rf-lna-p/v8/bom4/chan.py (bond 2.45 nH Q 50, finger, 5.5 mm 86.6 ohm trace Q 40, via, connector, d mm carrier line).
Zpad modelled as R - j/(wC) (series RC fitted at 2.44 GHz).  Loss = transducer loss (available source power -> power into Zpad)."""
import sys, numpy as np, itertools
sys.path.insert(0, '/home/ubuntu/svalbard/scratch/rf-lna-p/v8/bom4')
import chan as CH
from scipy.optimize import minimize
F = np.linspace(2.395e9, 2.4885e9, 41); BAND = (F >= 2.4e9) & (F <= 2.4835e9)
QS = {'pess': dict(sL=40., sC=100., pC=100., pL=40.), 'opt': dict(sL=80., sC=300., pC=300., pL=80.)}
def zpad(r, x):
    c = -1 / (2 * np.pi * 2.44e9 * x); return r + 1 / (1j * 2 * np.pi * F * c)
def fit(z, topo, qn, d_mm, conn=(1.0e-9, 0.25e-12), bond=2.45e-9, seeds=6):
    ch = CH.channel(bond=bond, conn_l=conn[0], conn_c=conn[1], d_mm=d_mm)
    start = {'sL': 3e-9, 'sC': 1.0e-12, 'pC': 1.0e-12, 'pL': 4e-9}
    def ev(x):
        els = ch + [(t, v, QS[qn][t]) for t, v in zip(topo, np.exp(x))]
        s11, loss, _ = CH.s11_loss(els, F, z); return s11.max(), loss[BAND].max(), loss[BAND].mean()
    best = None
    for s in range(seeds):
        x0 = np.log([start[t] for t in topo]) + np.random.RandomState(s).normal(0, 0.7, len(topo)) * (s > 0)
        r = minimize(lambda x: ev(x)[1] + 3 * max(0, ev(x)[0] + 10.5), x0, method='Nelder-Mead', options=dict(maxiter=800, xatol=1e-3, fatol=1e-4))
        if best is None or r.fun < best[0]: best = (r.fun, r.x)
    s, lmax, lmean = ev(best[1]); return s, lmax, lmean, np.exp(best[1])
if __name__ == '__main__':
    # self-check of the model on known answers is in chan.py (__main__): T1 lossless L-match, T2 series R, T3 broken
    cases = [(float(a), float(b)) for a, b in (x.split(',') for x in sys.argv[1:])] or [(6.4, -72.5), (10., -91.), (12.7, -92.), (20., -100.), (30., -100.)]
    for r, x in cases:
        z = zpad(r, x)
        for d in (2., 10.):
            out = []
            for topo in (('sC', 'pC'), ('pC', 'sC'), ('pL', 'sC'), ('sC', 'pL'), ('sL', 'pC'), ('pC', 'sL', 'pC')):
                s, lmax, lmean, v = fit(z, topo, 'pess', d)
                out.append((lmax, s, topo, v))
            out.sort(key=lambda o: o[0] + 5 * max(0, o[1] + 10))
            lmax, s, topo, v = out[0]
            so, lo, _, _ = fit(z, topo, 'opt', d)
            print('Zpad %.1f%+.1fj d %2.0f mm: best %s vals %s S11 %.1f dB loss(pess Q) %.2f dB (opt Q %.2f) | others: %s' % (r, x, d, '+'.join(topo), ['%.3g' % q for q in v], s, lmax, lo, ' '.join('%s %.2f/%.0f' % ('+'.join(o[2]), o[0], o[1]) for o in out[1:4])), flush=True)
