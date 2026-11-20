"""EM on cut lines: current through a straight cut across a band (per layer), divided by the drawn width of that layer on
the cut -> mA/um, the quantity the DRM limit applies to.  python3 emlines.py cfg.json map_prefix"""
import json, sys, numpy as np
cfg = json.load(open(sys.argv[1])); pre = sys.argv[2]; d = cfg['dir']
meta = json.load(open(f'{d}/meta.json')); H, x0, y0, nx, ny = meta['H'], meta['x0'], meta['y0'], meta['nx'], meta['ny']
RS = dict(nom=[0.09] * 4 + [0.04], high=[0.104] * 4 + [0.049])[cfg.get('corner', 'nom')]; LIM = [2.09] * 4 + [4.5]
ML = ['m1', 'm2', 'm3', 'm4', 'm5']
bands = json.loads(sys.argv[3])        # [{net, name, axis: 'x' (cuts at constant x, band in y) | 'y', lo, hi, from, to}]
out = {}
for b in bands:
    V = np.load(f'{pre}_{b["net"]}_layers.npy')
    cov = [np.minimum(np.fromfile(f'{d}/{b["net"]}_{l}.bin', dtype=np.float32).reshape(ny, nx), 1) for l in ML]
    worst = {}
    for k in range(5):
        best = (0, None, 0, 0)
        for c in np.arange(b['from'], b['to'], H):
            if b['axis'] == 'x':
                i = int((c - x0) / H); j0, j1 = int((b['lo'] - y0) / H), int((b['hi'] - y0) / H)
                cv = np.minimum(cov[k][j0:j1, i], cov[k][j0:j1, i + 1]); dv = (V[k][j0:j1, i] - V[k][j0:j1, i + 1]) * 1e-3
            else:
                j = int((c - y0) / H); i0, i1 = int((b['lo'] - x0) / H), int((b['hi'] - x0) / H)
                cv = np.minimum(cov[k][j, i0:i1], cov[k][j + 1, i0:i1]); dv = (V[k][j, i0:i1] - V[k][j + 1, i0:i1]) * 1e-3
            m = cv > 0.2
            w = float(cv[m].sum()) * H
            if w < 0.3: continue
            I = abs(float((dv[m] * cv[m]).sum())) / RS[k] * 1e3      # mA through this layer on the cut
            if I / w > best[0]: best = (I / w, round(float(c), 1), round(I, 2), round(w, 2))
        if best[1] is not None:
            worst[ML[k]] = dict(mA_per_um=round(best[0], 3), at=best[1], mA=best[2], width_um=best[3], margin_pct=round(100 * (1 - best[0] / LIM[k]), 1))
    out[b['name']] = worst
print(json.dumps(out, indent=1))
