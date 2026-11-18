import sys, klayout.db as k
L = k.Layout(); L.read(sys.argv[1]); t = L.top_cell(); d = L.dbu
x1, y1, x2, y2 = map(float, sys.argv[2:6])
w = k.Box(round(x1 / d), round(y1 / d), round(x2 / d), round(y2 / d))
for spec in sys.argv[6:]:
    l, dt = map(int, spec.split('/')); li = L.find_layer(l, dt)
    if li is None: continue
    r = k.Region(t.begin_shapes_rec_overlapping(li, w)); r.merge()
    for p in r.each():
        if not p.bbox().inside(w): continue
        print(spec, 'hull', [(q.x * d, q.y * d) for q in p.each_point_hull()], 'holes', [[(q.x * d, q.y * d) for q in p.each_point_hole(h)] for h in range(p.holes())])
