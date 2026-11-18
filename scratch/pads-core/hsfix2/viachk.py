"""viachk.py <gds> [top]: via cuts not covered by both metals, cut shapes that are not 0.26 x 0.26, off-grid (5 nm) cut corners."""
import sys, klayout.db as k
L = k.Layout(); L.read(sys.argv[1]); t = L.cell(sys.argv[2]) if len(sys.argv) > 2 else L.top_cell(); d = L.dbu
R = lambda l: k.Region(t.begin_shapes_rec(L.find_layer(l, 0))).merged()
mim = R(75) if L.find_layer(75, 0) is not None else k.Region()
for v, lo, hi in ((35, 34, 36), (38, 36, 42), (40, 42, 46), (41, 46, 81)):
    c = R(v); a = c.not_inside(R(lo)); b = c.not_inside(R(hi))
    if v == 41: a = a.not_interacting(mim)
    bad = [p for p in c.each() if not p.is_box() or p.bbox().width() != round(.26 / d) or p.bbox().height() != round(.26 / d)]
    off = [p for p in c.each() if any(q % 5 for q in (p.bbox().left, p.bbox().bottom))]
    print(v, 'cuts', c.count(), 'not in lower metal', a.count(), 'not in upper metal', b.count(), 'bad shape', len(bad), 'off grid', len(off),
          [str(p.bbox()) for p in list(a.each())[:3] + list(b.each())[:3] + bad[:3] + off[:3]])
