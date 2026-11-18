"""E14: input-stage exploration for the REAL channel.  Schematic + emulated extraction wiring (0.2 pF at each gate node g,
0.08 pF at each pad, 0.2 pF on each tank node).  Metric: LNA own NF (ideal match, noiseless mixer) + channel/match loss on the
real COB channel (ch1.fit, pessimistic part Q, connector + 2 mm), tt and pessimistic end; plus stability screen (ff, lowr).
usage: e14.py tag ccm_side rcm_w deg_dout deg_turns rdeg_w rgs_w [wcs]"""
import sys; sys.path.insert(0, '/home/ubuntu/svalbard/scratch/rf-lna-q')
from var import *
import ch1, numpy as np, lna_spiral
tag = sys.argv[1]; ccm, rcmw, dd, dt, rdw, rgw = [float(x) for x in sys.argv[2:8]]; wcs = float(sys.argv[8]) if len(sys.argv) > 8 else 450.
LS.G_DEG = dict(LS.G_DEG, dout_um=dd, turns=int(dt))
mods = dict(LNA_CCM=ccm, LNA_RCM_W=rcmw, LNA_RDEG_W=rdw, LNA_RGS_W=rgw, LNA_WCS=wcs, LNA_WREP=4.8 * wcs / 450.)
def wires(t):
    i = t.index('.subckt pt_lna '); e = t.index('.ends', i)
    return t[:e] + 'Cw1 g_p VSS 0.2p\nCw2 g_n VSS 0.2p\nCw3 rf_in_p VSS 0.08p\nCw4 rf_in_n VSS 0.08p\nCw5 tank_p VSS 0.2p\nCw6 tank_n VSS 0.2p\n' + t[e:]
m = LS.model_deg('nom'); print(tag, 'deg L %.2f nH Rs %.2f area %.1fk' % (m['L_nH'], m['Rs_ohm'], m['footprint_um2'] / 1e3), mods, flush=True)
tot = {}
for v, c in (('extpr', TT), ('extpp', SS)):
    W = variant(f'e14_{tag}_{v}', mods=mods, like=v, patch=wires)
    u = tb.lna_ac(W, 'selftest', c, f=2.44e9, ct=7); z = complex(u['zin_re_ohm'], u['zin_im_ohm']); mi = tb.board_match(z, f=2.44e9)
    gs = [(ct, tb.lna_ac(W, 'selftest', c, f=2.44e9, ct=ct, match=mi)['gain_db']) for ct in (0, 4, 8, 12)]
    ct, g = max(gs, key=lambda x: x[1]); n = tb.lna_ac(W, 'selftest', c, f=2.44e9, ct=ct, match=mi, noiseless_load=True)
    best = min((ch1.fit(ch1.zpad(z.real, z.imag), tp, 'pess', 2.)[:2] + (tp,) for tp in (('pL', 'sC'), ('sC', 'pC'), ('sL', 'pC'))), key=lambda o: o[1] + 5 * max(0, o[0] + 10))
    tot[v] = n['nf_db'] + best[1]
    print(tag, v, 'Zin %.1f%+.1fj idd %.1f gain %.2f (ct %d) NF_own %.2f | channel+match loss %.2f dB (S11 %.1f, %s) | NF_own+loss %.2f, gain-loss %.2f' % (z.real, z.imag, u['idd_a'] * 1e3, g, ct, n['nf_db'], best[1], best[0], '+'.join(best[2]), tot[v], g - best[1]), flush=True)
W = variant(f'e14_{tag}_st', mods=mods, like='extpr', patch=wires)
r = LM.stability(W, 'selftest', FF, deg='lowr'); print(tag, fmt(r).replace('mu 1.0000 ', ''))
for kind in ('mx0', 'cm0'):
    f = sorted(W.glob(f'stab_selftest_*_{kind}_zr.txt'))[-1]; d = np.array(S.read_table(f)); F = d[:, 0] / 1e9
    print(tag, kind, ' '.join('%g:%.2f' % (x, np.interp(x, F, d[:, 1])) for x in (0.2, 0.5, 1, 1.5, 2, 2.4, 3, 4, 6, 8, 10, 13, 16, 20, 30)))
