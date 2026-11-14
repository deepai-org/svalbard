#!/usr/bin/env python3
"""Mesh convergence check: the wrx_cap->adc pair at d = 200 / 800 um on the 25 um / 12-layer mesh (CG) against the 50 um / 6-layer
mesh (direct) used for the sweeps.  Set SUBMESH_H=25 for the fine run, 50 for the coarse."""
import json, numpy as np, submesh as sm, os, time
W, HH = 5200.0, 3200.0; nz = 12 if sm.H == 25 else 6
m = sm.Mesh(W, HH, nz=nz); nx, ny = m.nx, m.ny; out = {}
for d in (200, 800):
    aw, ah, vw, vh = 660, 1450, 465, 1240; x0 = (W-(aw+d+vw))/2
    f = m.cells([x0, HH/2-ah/2, x0+aw, HH/2+ah/2]); vm = m.cells([x0+aw+d, HH/2-vh/2, x0+aw+d+vw, HH/2+vh/2])
    n = int(round(250/sm.H)); per = np.zeros((nx, ny)); per[:n, :] = per[-n:, :] = 0.3; per[:, :n] = per[:, -n:] = 0.3
    for g in ('bare', 'dense'):
        tie = per.copy()
        if g == 'dense': tie[:] = 1.0
        tie[vm] = 0
        for back in (False, True):
            t = time.time(); v = m.solve(tie, force=f, back=back)
            out[f'{d}_{g}_{"backgnd" if back else "float"}'] = dict(near_db=sm.db(np.percentile(v[vm], 90)), mean_db=sm.db(v[vm].mean()), s=round(time.time()-t, 1))
            print(d, g, back, out[f'{d}_{g}_{"backgnd" if back else "float"}'], flush=True)
json.dump(out, open(f'meshcheck_h{int(sm.H)}.json', 'w'), indent=1)
