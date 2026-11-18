"""E13: extracted LNA quick look: stability base rows + K/mu curve summary + RF numbers.  usage: e13.py tag"""
import sys; sys.path.insert(0, '/home/ubuntu/svalbard/scratch/rf-lna-q')
from var import *
import numpy as np, kmu
tag = sys.argv[1]; W = Q / 'w' / f'e13_{tag}'
for v, c, dg in (('extpr', FF, 'lowr'), ('extlo', ('ff', 22, 3.35), 'lowr'), ('extpr', TT, None)):
    r = LM.stability(W, v, c, deg=dg); print(tag, v, c[0], dg, fmt(r), flush=True)
    pre = sorted(W.glob(f'stab_{v}_{tb._tag(c)}_ct7_a0_active_*_a.txt'))[-1]
    f, k, mu, *_ = kmu.kmu(str(pre)[:-6]); bad = (k < 1) | (mu < 1)
    print('   K<1/mu<1 at GHz:', ('%.2f..%.2f' % (f[bad].min() / 1e9, f[bad].max() / 1e9)) if bad.any() else 'none', '| min K %.2f at %.2f GHz' % (k.min(), f[k.argmin()] / 1e9))
    for kind in ('mx0', 'cm0'):
        d = np.array(S.read_table(str(pre)[:-6] + f'_{kind}_zr.txt')); F = d[:, 0] / 1e9
        print('   ', kind, ' '.join('%g:%.2f' % (x, np.interp(x, F, d[:, 1])) for x in (0.1, 0.5, 1, 2, 2.4, 4, 6, 8, 10, 13, 16, 20, 25, 30)))
for v, c in (('extpr', TT), ('extpp', SS), ('extpr', SS)):
    u = tb.lna_ac(W, v, c, f=2.44e9, ct=7); mi = tb.board_match(complex(u['zin_re_ohm'], u['zin_im_ohm']), f=2.44e9)
    gs = [(ct, tb.lna_ac(W, v, c, f=2.44e9, ct=ct, match=mi)['gain_db']) for ct in (0, 3, 6, 9, 12, 15)]
    ct = max(gs, key=lambda x: x[1])[0]; n = tb.lna_ac(W, v, c, f=2.44e9, ct=ct, match=mi, noiseless_load=True)
    print(tag, v, c[0], 'Zin %.1f%+.1fj idd %.2f mA | gain vs ct %s | best ct %d NF_own %.2f dB' % (u['zin_re_ohm'], u['zin_im_ohm'], u['idd_a'] * 1e3, ' '.join('%d:%.2f' % g for g in gs), ct, n['nf_db']), flush=True)
