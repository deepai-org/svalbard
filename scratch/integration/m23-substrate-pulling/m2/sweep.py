#!/usr/bin/env python3
"""M2 generic distance / guarding sweep (floorplan-independent: for the re-pack).
Aggressor rectangle (forced 1 V) and a victim rectangle (floating probe) at edge gap d on a 5.2 x 3.2 mm slab whose perimeter
(pad ring, 250 um) is tied 0.3 g.  Guarding variants:
  bare   : nothing else tied (pessimistic upper bound)
  vring  : one-cell p+ guard ring round the victim, narrow (~1 um line: 1 g per cell)
  both   : narrow rings round victim and aggressor
  bothw  : wide, well-strapped rings (full cell width p+: 10 g per cell) round both
  dense  : every other surface cell tied 1 g (A1 assumption: continuous tie sea; optimistic bound)
each with the backside floating / grounded.  Output dB (near = worst 10 % of victim cells; mean)."""
import json, sys, numpy as np, submesh as sm
W, HH = 5200.0, 3200.0
PAIRS = {  # name: (aggressor w,h ; victim w,h)   long sides facing where it matters
    'wrx_cap->adc': ((660, 1450), (465, 1240)),
    'ring->qvco': ((210, 800), (630, 850)),
    'digital->qvco': ((1640, 1700), (630, 850)),
    'pa->qvco_or_lna': ((200, 480), (630, 850)),
    'qvco->lna': ((630, 850), (125, 200)),
}
DS = (50, 100, 200, 300, 500, 800, 1200, 2000)
out = {}
sel = sys.argv[1:] or list(PAIRS)
import os
NZ = int(os.environ.get('SUBMESH_NZ', '12')); TAG = os.environ.get('SUBMESH_TAG', '')
m = sm.Mesh(W, HH, nz=NZ); nx, ny = m.nx, m.ny
def ring(rect, gap=sm.H, w=sm.H):
    o = m.cells([rect[0]-gap-w, rect[1]-gap-w, rect[2]+gap+w, rect[3]+gap+w]); i = m.cells([rect[0]-gap, rect[1]-gap, rect[2]+gap, rect[3]+gap]); return o & ~i
for pn in sel:
    (aw, ah), (vw, vh) = PAIRS[pn]; out[pn] = {}
    for d in DS:
        tot = aw+d+vw; x0 = max(300.0, (W-tot)/2)
        if x0+tot > W-300: continue
        ar = [x0, HH/2-ah/2, x0+aw, HH/2+ah/2]; vr = [x0+aw+d, HH/2-vh/2, x0+aw+d+vw, HH/2+vh/2]
        f = m.cells(ar); vm = m.cells(vr)
        per = np.zeros((nx, ny)); n = 10; per[:n, :] = per[-n:, :] = 0.3; per[:, :n] = per[:, -n:] = 0.3
        row = {}
        for g in ('bare', 'vring', 'both', 'bothw', 'dense'):
            if g in ('vring', 'both', 'bothw') and d < 4*sm.H: continue
            tie = per.copy()
            gr = 10.0 if g == 'bothw' else 1.0          # narrow (~1 um) p+ line ~ 1 g per cell; wide (full-cell, strapped) ring ~ 10 g
            if g in ('vring', 'both', 'bothw'): tie[ring(vr) & ~f] = gr
            if g in ('both', 'bothw'): tie[ring(ar) & ~vm] = gr
            if g == 'dense': tie[:] = 1.0
            tie[vm] = 0.0
            for back in (False, True):
                v = m.solve(tie, force=f, back=back)
                t2 = tie.copy(); t2[vm] = 0.3      # victim keeps its own taps (ideal quiet ground): residual local potential
                v2 = m.solve(t2, force=f, back=back)
                row[f"{g}_{'backgnd' if back else 'float'}"] = dict(near_db=sm.db(np.percentile(v[vm], 90)), mean_db=sm.db(v[vm].mean()),
                                                                 tied_near_db=sm.db(np.percentile(v2[vm], 90)), tied_mean_db=sm.db(v2[vm].mean()))
        out[pn][d] = row; print(pn, d, {k: (w['near_db'], w['tied_near_db']) for k, w in row.items()}, flush=True)
    json.dump(out, open(f"sweep{TAG}_{pn.replace('->', '_to_')}.json", 'w'), indent=1)
