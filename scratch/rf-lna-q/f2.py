"""F2 (round 2, item 2): degeneration spirals full / half / none on the extracted LNA (bench-level source network), corners + views.
usage: f2.py full|half|none"""
import sys, json; sys.path.insert(0, '/home/ubuntu/svalbard/scratch/rf-lna-q')
from var import *
import lna_close as L, numpy as np
mode = sys.argv[1]
if mode == 'half': LS.G_DEG = dict(LS.G_DEG, dout_um=100.0, turns=2, width_um=15.0)
def src(variant):
    if mode == 'none': return 'Rdsp srcp_b scm_b 0.02\nRdsn srcn_b scm_b 0.02\n'
    n = LS.DEG_NAMES[variant]; return f'Xdegp srcp_b scm_b {{gnd}} {n}\nXdegn srcn_b scm_b {{gnd}} {n}\n' + LS.subckt_deg(variant)
if mode != 'none': m = LS.model_deg('nom'); print(mode, 'deg L %.2f nH Rs %.2f area %.1fk' % (m['L_nH'], m['Rs_ohm'], m['footprint_um2'] / 1e3), flush=True)
L.OUT = flow.SCRATCH / f'close_deg_{mode}'
out = dict(band=[], stab=[])
for v, c in [('extpr', (p, t, vv)) for p in L.PROCS for t, vv in ((32, 3.15), (22, 3.35))] + [('extpp', SS), ('extlo', ('ff', 22, 3.35))]:
    tb.SRC_BOND = src(tb.LNA_DEG_VIEW.get(v, 'nom'))
    best = None
    for ct in (3, 6, 9, 12):
        L.TANK_CT[(v, c[0])] = ct; r = L.band.__globals__['tb'] and None
    # tank code: pick by ideal-match gain
    w = L.OUT / 'band'; u = tb.lna_ac(w, v, c, f=2.44e9, ct=9); mi = tb.board_match(complex(u['zin_re_ohm'], u['zin_im_ohm']), f=2.44e9)
    ct = max(((k, tb.lna_ac(w, v, c, f=2.44e9, ct=k, match=mi)['gain_db']) for k in (3, 6, 9, 12, 15)), key=lambda x: x[1])[0]
    z = complex(u['zin_re_ohm'], u['zin_im_ohm']); m, s11f, lossf = LM.channel_fit(z, d_mm=2.); m['ct'] = ct
    b = tb.lna_band(w, v, c, m, ct=ct); inb = [r for r in b['rows'] if 2.3999e9 <= r['f'] <= 2.48351e9]
    row = dict(view=v, corner=c, ct=ct, zpad=[z.real, z.imag], idd_ma=u['idd_a'] * 1e3, s11=max(r['s11_db'] for r in b['rows']), gain=[min(r['gain_db'] for r in inb), max(r['gain_db'] for r in inb)], nf=[min(r['nf_db'] for r in inb), max(r['nf_db'] for r in inb)], match=m)
    out['band'].append(row)
    print(mode, 'BAND', v, c, 'ct%d Zpad %.1f%+.1fj S11 %.1f gain %.2f..%.2f NF %.2f..%.2f' % (ct, z.real, z.imag, row['s11'], *row['gain'], *row['nf']), flush=True)
for v, c, dg, lob, pk in [('extpr', FF, 'lowr', False, 'B_nom'), ('extpr', FF, 'lowr', True, 'B_nom'), ('extpr', FF, 'lowr', False, 'B_min'), ('extpr', FF, 'lowr', True, 'B_max'), ('extlo', ('ff', 22, 3.35), 'lowr', False, 'B_nom'),
                          ('extpr', TT, None, True, 'B_nom'), ('extpr', SS, None, True, 'B_nom'), ('extpr', ('fs', 22, 3.35), 'lowr', False, 'B_nom')]:
    tb.SRC_BOND = src(dg or tb.LNA_DEG_VIEW.get(v, 'nom')); tb.set_lobias(lob)
    r = LM.stability(L.OUT / 'stab', v, c, deg=dg, pkg=pk, cdie=3e-9, rdie=0.03, rsw=0.2); tb.set_lobias(False)
    cm = []; dm = []
    for kind, acc in (('cm', cm), ('mx', dm)):
        for f in sorted((L.OUT / 'stab').glob(f'*_{kind}?_zr.txt'), key=lambda p: p.stat().st_mtime)[-2:]:
            d = np.array(S.read_table(f)); acc.append(float(d[d[:, 0] <= 8e9, 1].min()))
    r.update(view=v, corner=c, lobias=lob, pkg=pk, cm_min_below_8ghz=min(cm), dm_min_below_8ghz=min(dm)); out['stab'].append(r)
    print(mode, 'STAB', v, c[0], 'lob' if lob else 'rx', pk, 'mu %.4f K %.2f Re_diff %.2f (<8G %.2f) | Re_cm %.2f (<8G %.2f)' % (r['min_mu'], r['min_k'], r['min_re_zin_real_mixer_ohm'], r['dm_min_below_8ghz'], r['min_re_zcm_real_mixer_ohm'], r['cm_min_below_8ghz']), flush=True)
json.dump(out, open(Q / f'f2_{mode}.json', 'w'), indent=1, default=str)
