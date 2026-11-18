import klayout.db as k, glob, sys
for f in sorted(glob.glob('/foss/pdks/gf180mcuD/libs.ref/gf180mcu_fd_io/gds/*.gds')):
    L = k.Layout(); L.read(f)
    for c in L.each_cell():
        if 'RAIL' in c.name.upper() or c.name in sys.argv[1:]:
            b = c.dbbox(); s = []
            for li in L.layer_indexes():
                i = L.get_info(li)
                if i.layer in (34, 35, 36, 38, 42, 46, 81) and i.datatype == 0:
                    r = k.Region(c.begin_shapes_rec(li)); r.merge()
                    if not r.is_empty(): bb = r.bbox(); s.append('%d: n%d area %.0f bbox y %.1f-%.1f x %.1f-%.1f' % (i.layer, r.count(), r.area() * L.dbu ** 2, bb.bottom * L.dbu, bb.top * L.dbu, bb.left * L.dbu, bb.right * L.dbu))
            print(f.split('/')[-1], c.name, '%.1f %.1f %.1f %.1f' % (b.left, b.bottom, b.right, b.top)); [print('   ', x) for x in s]
