"""Assembly-ready spiral cells (baseline, 2026-11-22): generated/lna_{ind,deg}.gds from lna_spiral.layout get
  - the fill keep-out markers of integration/signoff/fill/keepouts.json inside the cell: PMNDMY (152/5) and IND_MK (151/5) over the
    spiral bounding box grown by 25 um (the cell boundary);
  - pins at the cell edge: a straight Metal5 stub, strap width, from terminal A and from terminal B to the nearest boundary edge, with
    the pin label (A / B, Metal5 label 81/10) at the edge.
Runs inside the analog image (klayout python):  python3 spiral_finish.py <in.gds> <out.gds> <width_um>"""
import sys
import klayout.db as k
src, dst, w = sys.argv[1], sys.argv[2], float(sys.argv[3])
ly = k.Layout(); ly.read(src); top = ly.top_cell(); dbu = ly.dbu
M5, M5L = ly.layer(81, 0), ly.layer(81, 10)
bb = top.dbbox(); E = bb.enlarged(25.0, 25.0)
labels = {}
for li in ly.layer_indexes():
    it = top.begin_shapes_rec(li); it.shape_flags = k.Shapes.STexts
    while not it.at_end():
        t = it.shape().text
        if t.string in ('A', 'B'): labels[t.string] = it.trans() * k.Point(t.x, t.y)
        it.next()
assert set(labels) == {'A', 'B'}, labels
hw = w / 2
for name, p in labels.items():
    x, y = p.x * dbu, p.y * dbu
    d = {'W': x - E.left, 'E': E.right - x, 'S': y - E.bottom, 'N': E.top - y}
    side = min(d, key=d.get)
    if side == 'W': r, lp = k.DBox(E.left, y - hw, x, y + hw), (E.left + 0.5, y)
    elif side == 'E': r, lp = k.DBox(x, y - hw, E.right, y + hw), (E.right - 0.5, y)
    elif side == 'S': r, lp = k.DBox(x - hw, E.bottom, x + hw, y), (x, E.bottom + 0.5)
    else: r, lp = k.DBox(x - hw, y, x + hw, E.top), (x, E.top - 0.5)
    top.shapes(M5).insert(r)
    top.shapes(M5L).insert(k.DText(name, lp[0], lp[1]))
    print(name, 'pin on', side, 'edge at', round(lp[0], 2), round(lp[1], 2))
for l in ((152, 5), (151, 5)):
    top.shapes(ly.layer(*l)).insert(E)
ly.write(dst)
print('cell', top.name, 'boundary', round(E.width(), 2), 'x', round(E.height(), 2), 'um', round(E.width() * E.height()), 'um2')
