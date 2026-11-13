# klayout -b -r kl_gds_census.py -rd root=/work -rd out=/out/gds-census.json
# Read-only census of every block GDS: dbu, layers, forbidden layers, off-grid (5 nm) vertices,
# per-layer density over the top-cell bbox, metal wider than 30 um (outside Pad), DNWELL / LU marker presence.
import klayout.db as kdb, json, os, glob, sys
L = dict(COMP=(22,0), POLY2=(30,0), M1=(34,0), M2=(36,0), M3=(42,0), M4=(46,0), M5=(81,0), MTOP=(53,0), VIA5=(82,0),
         PAD=(37,0), DNWELL=(12,0), NWELL=(21,0), LVPWELL=(204,0), DUALGATE=(55,0), FUSETOP=(75,0), NAT=(5,0),
         GUARD_RING_MK=(167,5), LATCHUP_MK=(137,5), ESD_MK=(136,5), PMNDMY=(152,5), SAB=(49,0), RES_MK=(110,5), HRES=(62,0))
files = sorted(set(glob.glob(root + '/**/*.gds', recursive=True) + glob.glob(root + '/**/*.gds.gz', recursive=True)))
res = []
for f in files:
    rel = os.path.relpath(f, root)
    if 'precompact' in rel or 'prelu' in rel: continue
    rec = dict(gds=rel, bytes=os.path.getsize(f))
    try:
        ly = kdb.Layout(); ly.read(f)
        tops = ly.top_cells(); top = max(tops, key=lambda c: c.bbox().area())
        bb = top.bbox(); dbu = ly.dbu
        rec.update(dbu=dbu, top=top.name, n_top=len(tops), cells=ly.cells(), bbox_um=[bb.width()*dbu, bb.height()*dbu])
        area = bb.area() or 1
        present = {(li.layer, li.datatype) for li in ly.layer_infos()}
        rec['unknown_layers'] = sorted(f'{a}/{b}' for a, b in present)[:0]
        rec['layers'] = sorted(f'{a}/{b}' for a, b in present)
        big = area * dbu * dbu > 1.0e6   # > 1 mm2: skip the expensive checks
        dens = {}; flags = {}
        grid = int(round(0.005 / dbu)); offgrid = 0
        for name, (a, b) in L.items():
            idx = ly.find_layer(a, b)
            if idx is None: continue
            it = top.begin_shapes_rec(idx)
            if it.at_end(): continue
            flags[name] = True
            if big and name not in ('MTOP','VIA5','DNWELL'): continue
            r = kdb.Region(it)
            if name in ('COMP','POLY2','M1','M2','M3','M4','M5'):
                r.merge(); dens[name] = round(r.area() / area, 4)
                if name.startswith('M'):
                    w = r.sized(-int(15.0/dbu))
                    if not w.is_empty(): rec.setdefault('wide_gt30um', {})[name] = w.count()
            if grid > 1 and name in ('COMP','POLY2','M1','M2','M3','M4','M5'):
                for p in r.each():
                    for pt in p.each_point_hull():
                        if pt.x % grid or pt.y % grid: offgrid += 1
        rec.update(density=dens, present=sorted(flags), offgrid_vertices=offgrid, big_skipped=big)
    except Exception as e:
        rec['error'] = str(e)
    res.append(rec)
json.dump(res, open(out, 'w'), indent=1)
