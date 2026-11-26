#!/usr/bin/env python3
"""CHIP=rf|wired evalp.py cfg.py <chip>_place.json <tag> [G]: legality / rule check, small cells + decap placed next to partners,
macro pins assigned facing their nets, gcell global route (M2 V, M3 H), utilisation report, SVG + ASCII drawing."""
import json, sys, importlib.util, collections, math
import numpy as np
import plan_lib as P
spec = importlib.util.spec_from_file_location('cfg', sys.argv[1]); cfg = importlib.util.module_from_spec(spec); spec.loader.exec_module(cfg)
pl = json.load(open(sys.argv[2])); pl = pl.get('hand', pl); tag = sys.argv[3]; P.G = float(sys.argv[4]) if len(sys.argv) > 4 else 20.0
place = {i: tuple(v) for i, v in pl.items()}
p = P.Plan(cfg.JSON, cfg.RUN, place, cfg.KEEPOUTS, cfg.CHANNELS)
C = p.C
dec = sorted(i for i in p.movable() if C[i]['master'] == 'decap')
sm = [i for i in p.movable() if C[i]['master'] != 'decap']
sm.sort(key=lambda i: -C[i]['w'] * C[i]['h'])
un = p.autoplace(sm, halo=4.0)
# decap: macro-edge bank first (next to the macro), then tiles anywhere
near = {i: cfg.MACRO for i in dec if 'bank' in i}
und = p.autoplace(dec, near=near, step=20.0, halo=2.0)
bad, ka, ad = p.check(cfg.RULES, [(a, b, d) for a, b, d, w in cfg.ADJ if not b.startswith('g4_')])
# switch to supply-bond distance (G4)
g4 = []
for s, (e, c) in cfg.G4.items():
    r = p.rect[s]; d = (r[0] - 452 if e == 'W' else 3480 - r[2]) + max(0, r[1] - c, c - r[3]); g4.append((s, e, c, round(d)))
# virtual rules
for a, v, d in cfg.RULES:
    if a in cfg.VIRTUAL and v in p.rect:
        g = P.egap(cfg.VIRTUAL[a], p.rect[v]); ka.append((a, v, d, round(g), g >= d))
mp = p.assign_macro(cfg.MACRO, pitch=getattr(cfg, 'MPITCH', 2.24), forbid=getattr(cfg, 'MFORBID', None))
import os
SIGM1 = os.environ.get('SIG_M1') == '1'
p.grid(sig_m1=SIGM1)
uH, uV = p.route(lambda n, v: 3.0 if v['cls'] in ('supply', 'lo') else 1.0, iters=5)
capH = np.maximum(p.capH, 1e-3); capV = np.maximum(p.capV, 1e-3)
rH = uH / capH; rV = uV / capV
res = dict(tag=tag, unplaced_small=un, unplaced_decap=und, decap_placed=len(dec) - len(und), decap_total=len(dec),
           overlaps=[b for b in bad], keepaway=[k for k in ka], adjacency=[a for a in ad], g4=g4,
           macro_sides=dict(collections.Counter(v[0] for v in mp.values())), msgs=p.msgs)
okH = p.capH > 0.5; okV = p.capV > 0.5
res['route'] = dict(G=P.G, H_cells_over70=int(((rH > 0.7) & okH).sum()), H_cells_over100=int(((rH > 1.0) & okH).sum()),
                    V_cells_over70=int(((rV > 0.7) & okV).sum()), V_cells_over100=int(((rV > 1.0) & okV).sum()),
                    forced_through_blocks=round(float(uH[~okH].sum() + uV[~okV].sum())), total=round(float(uH.sum() + uV.sum())),
                    wl_mm=round(float(uH.sum() + uV.sum()) * P.G / 1000, 1))
json.dump(dict(res=res, channels=cfg.CHANNELS, keepouts=[('k', k) for k in cfg.KEEPOUTS], rect=p.rect, orient=p.orient, mpins=p.mpins), open(f'eval_{tag}.json', 'w'), indent=0, default=list)
np.save(f'use_{tag}.npy', np.stack([uH, uV, p.capH, p.capV]))
print(json.dumps(res['route']))
print('unplaced', un, 'decap', res['decap_placed'], '/', res['decap_total'])
print('overlaps', bad[:10])
print('keepaway fails', [k for k in ka if not k[4]])
print('adjacency fails', [a for a in ad if not a[4]])
print('g4', g4)
print('macro pin sides', res['macro_sides'], p.msgs)
