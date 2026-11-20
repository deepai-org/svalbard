import klayout.db as db, json
ly = db.Layout(); ly.read('/h/out/qvco9h.fill.gds')
top = max(ly.top_cells(), key=lambda c: c.bbox().area()); dbu = ly.dbu
mk = db.Region(top.begin_shapes_rec(ly.layer(151, 5))).merged()
# spiral metal polygons (all metal layers of the spiral cell instances) and all tank-net metal is not separable here: spiral metal only
sp = db.Region()
def walk(c, tr):
    for i in c.each_inst():
        t = tr * i.trans
        if i.cell.name == 'pt_spiral_ind':
            for l in (34, 36, 42, 46, 81):
                li = ly.find_layer(l, 0)
                if li is not None:
                    sp.insert(db.Region(i.cell.begin_shapes_rec(li)).transformed(t))
        else: walk(i.cell, t)
walk(top, db.Trans()); sp.merge()
near = sp.sized(int(25 / dbu))
out = dict(marker_mm2=mk.area() * dbu * dbu / 1e6, frame_bbox_um=[top.bbox().left * dbu, top.bbox().bottom * dbu, top.bbox().right * dbu, top.bbox().top * dbu], layers={})
for name, l in (('COMP', 22), ('Poly2', 30), ('Metal1', 34), ('Metal2', 36), ('Metal3', 42), ('Metal4', 46), ('Metal5', 81)):
    i = ly.find_layer(l, 4)
    r = db.Region(top.begin_shapes_rec(i)) if i is not None else db.Region()
    out['layers'][name] = dict(dummies_total=r.count(), in_marker=(r & mk).count(), within_25um_of_spiral_metal=(r & near).count())
print(json.dumps(out)); open('/h/out/qvco9h.fillcheck.json', 'w').write(json.dumps(out, indent=1))
