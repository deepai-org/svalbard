"""nview.py <nets.gds> x1 y1 x2 y2 out.png LAYER[+LAYER],...  : PNG per layer panel, coloured by net."""
import sys, klayout.db as k
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
L = k.Layout(); L.read(sys.argv[1]); t = L.top_cell(); d = L.dbu
x1, y1, x2, y2 = map(float, sys.argv[2:6]); out = sys.argv[6]; panels = sys.argv[7].split(',')
LY = {'M1': 34, 'M2': 36, 'M3': 42, 'M4': 46, 'M5': 81, 'V1': 35, 'V2': 38, 'V3': 40, 'V4': 41}
C = {1: 'red', 2: 'blue', 3: 'green', 4: 'orange', 9: 'gray'}
w = k.Region(k.Box(round(x1 / d), round(y1 / d), round(x2 / d), round(y2 / d)))
fig, axs = plt.subplots(1, len(panels), figsize=(8 * len(panels), 8 * (y2 - y1) / (x2 - x1) + 1))
if len(panels) == 1: axs = [axs]
for ax, ps in zip(axs, panels):
    for ln in ps.split('+'):
        for dt, c in C.items():
            li = L.find_layer(LY[ln], dt)
            if li is None: continue
            r = (k.Region(t.begin_shapes_rec(li)) & w).merged()
            for p in r.each():
                pts = [(q.x * d, q.y * d) for q in p.each_point_hull()]
                ax.add_patch(Polygon(pts, closed=True, fc=c if not ln.startswith('V') else 'k', ec=c, lw=.4, alpha=.4 if not ln.startswith('V') else 1))
    ax.set_xlim(x1, x2); ax.set_ylim(y1, y2); ax.set_aspect('equal'); ax.set_title(ps + '  red P, blue N, green VSS, orange RAIL, gray other'); ax.grid(True, lw=.2)
plt.tight_layout(); plt.savefig(out, dpi=int(sys.argv[8]) if len(sys.argv) > 8 else 60)
