"""Choose the r12 fixed offsets FIX[k] (bit-4-type units per node, ~2 LSB each) from the l8 real-ring code curves (res/l8_*.json):
predicted r12 code-0 position of channel k = l8 position at code 2*FIX[k] (linear extrapolation past 31 with the last slope);
predicted range = l8 position(2F+31) - position(2F).  Objective: maximise min over tags of range / (need_meas + 14) (G1 ratio).
Integer coordinate search from the rounded mean-pattern start.  -> pickfix.json"""
import json, glob, itertools
import numpy as np
from pathlib import Path
H = Path(__file__).resolve().parent
R = {Path(f).stem[3:]: json.loads(Path(f).read_text()) for f in sorted(glob.glob(str(H / 'res/l8_*.json')))}
def pos(r, k, c):
    x = r['code_points']; y = r['pos_vs_code_ps'][k]
    return float(np.interp(c, x, y)) if c <= x[-1] else y[-1] + (c - x[-1]) * (y[-1] - y[-2]) / (x[-1] - x[-2])
def score(F):
    out = {}
    for t, r in R.items():
        p0 = [pos(r, k, 2 * F[k]) for k in range(8)]; rg = min(pos(r, k, 2 * F[k] + 31) - p0[k] for k in range(8))
        need = max(p0) - min(p0); out[t] = (rg / (need + 14), need, rg)
    return min(v[0] for v in out.values()), out
m = np.mean([r['code0_pos_ps'] for r in R.values()], axis=0); lsb = np.mean([min(r['range_ps']) / 31 for r in R.values()])
F = [int(round(x)) for x in (m.max() - m) / (2 * lsb)]
best = score(F)[0]
improved = True
while improved:
    improved = False
    for k, d in itertools.product(range(8), (-1, 1)):
        G = list(F); G[k] += d
        if min(G) < 0: continue
        s = score(G)[0]
        if s > best + 1e-6: F, best, improved = G, s, True
s, det = score(F)
res = dict(FIX=F, worst_ratio=round(s, 3), mean_pattern_ps=[round(x, 1) for x in m], lsb_ps=round(lsb, 2),
           per_tag={t: dict(ratio=round(v[0], 3), need_meas_pred=round(v[1], 1), range_pred=round(v[2], 1)) for t, v in det.items()})
(H / 'pickfix.json').write_text(json.dumps(res, indent=1)); print(json.dumps(res, indent=0))
