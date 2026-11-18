"""q.py <nets.gds> x1 y1 x2 y2 LAYERS [minw] [max]: shapes per net in a window (clipped bboxes)."""
import sys, klayout.db as k
L = k.Layout(); L.read(sys.argv[1]); t = L.top_cell(); d = L.dbu
x1, y1, x2, y2 = map(float, sys.argv[2:6]); minw = float(sys.argv[7]) if len(sys.argv) > 7 else 0; mx = int(sys.argv[8]) if len(sys.argv) > 8 else 40
LY = {'M1': 34, 'M2': 36, 'M3': 42, 'M4': 46, 'M5': 81, 'V1': 35, 'V2': 38, 'V3': 40, 'V4': 41}
N = {1: 'P', 2: 'N', 3: 'VSS', 4: 'RAIL', 9: 'other'}
w = k.Region(k.Box(round(x1 / d), round(y1 / d), round(x2 / d), round(y2 / d)))
for ln in sys.argv[6].split(','):
    for dt, nm in N.items():
        li = L.find_layer(LY[ln], dt)
        if li is None: continue
        r = (k.Region(t.begin_shapes_rec(li)) & w).merged()
        out = []
        for p in r.each():
            b = p.bbox()
            if min(b.width(), b.height()) * d < minw: continue
            out.append((b.left * d, b.bottom * d, b.right * d, b.top * d, 'r' if p.is_box() else 'p%d' % p.num_points()))
        if out:
            print(ln, nm, len(out))
            for q in sorted(out)[:mx]: print('   %.3f %.3f %.3f %.3f %s' % q)
