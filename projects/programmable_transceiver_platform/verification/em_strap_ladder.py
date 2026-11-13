"""Round-2 reviewer: 1-D resistive ladder of one strap bar (M2/M3/M4 in parallel, via2/via3 along the whole strap,
via4 to an ideal M5 trunk, bar current injected into M2 uniformly over the array via via1). Reports peak per-layer
current fraction of the bar, peak via4 / via2 / via3 per-cut current vs the uniform assumption in em_check.py.
Pessimistic cases: M4 sheet 0.8x nominal with M2/M3 1.2x (M4 hogs), and via R halved (sharper crowding)."""
import numpy as np, sys
import scipy.sparse as sp, scipy.sparse.linalg as sl
def run(tl, tw, xa, xb, h, I, rs=(0.09,0.09,0.09), rv=4.5, dx=0.05):
    x = np.arange(tl, xb + 1e-9, dx); n = len(x); L = 3
    rows = max(1, int((h - .6 - .26) // .52) + 1)
    gv = rows * (dx / .52) / rv                       # via2 / via3 conductance per segment
    gv4 = np.where(x <= tl + tw, gv, 0.)               # via4 only over the trunk
    gv23 = np.where(x >= tl + .3, gv, 0.)
    N = L * n; G = sp.lil_matrix((N, N)); b = np.zeros(N); idx = lambda l, k: l * n + k
    for l in range(L):
        gm = h / (rs[l] * dx)
        for k in range(n - 1):
            a, c = idx(l, k), idx(l, k + 1); G[a,a]+=gm; G[c,c]+=gm; G[a,c]-=gm; G[c,a]-=gm
    for l in range(L - 1):
        for k in range(n):
            a, c = idx(l, k), idx(l + 1, k); g = gv23[k]; G[a,a]+=g; G[c,c]+=g; G[a,c]-=g; G[c,a]-=g
    for k in range(n): G[idx(2, k), idx(2, k)] += gv4[k]
    inj = (x >= xa) & (x <= xb); b[[idx(0, k) for k in range(n) if inj[k]]] = I / inj.sum()
    v = sl.spsolve(G.tocsr(), b).reshape(L, n)
    cur = [np.abs(np.diff(v[l]) * h / (rs[l] * dx)) for l in range(L)]
    i4 = v[2] * gv4; i23 = [np.abs(v[l] - v[l + 1]) * gv23 for l in range(2)]
    per_cut = lambda arr: arr / (rows * dx / .52)      # mA per cut
    v4cuts = max(1, int((tw - .6 - .26) // .52) + 1) * rows
    return dict(peak_layer_frac=[round(c.max() / I, 3) for c in cur], gap_frac=[round(c[np.searchsorted(x, (tl + tw + xa) / 2)] / I, 3) for c in cur],
                via4_peak_over_uniform=round(per_cut(i4).max() / (I / v4cuts), 2),
                via23_peak_mA_per_cut=[round(per_cut(a).max(), 3) for a in i23], check=round(i4.sum() / I, 4))

def worst(tl, tw, xb, h, I):
    """PD46 r2: crowding per strap bar; current injected over the far half of the strap (pessimistic vs injection near
    the trunk); worst of nominal and M4 0.8x / M2,M3 1.2x and via R halved."""
    xa = (tl + tw + xb) / 2
    cs = [run(tl, tw, xa, xb, h, I), run(tl, tw, xa, xb, h, I, rs=(.108, .108, .072)), run(tl, tw, xa, xb, h, I, rs=(.108, .108, .072), rv=2.25)]
    return max(c['peak_layer_frac'][2] for c in cs), max(c['via4_peak_over_uniform'] for c in cs), max(max(c['via23_peak_mA_per_cut']) for c in cs)
