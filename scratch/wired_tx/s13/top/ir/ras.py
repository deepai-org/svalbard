# KLayout (docker): supply nets VDD / VSS of the flattened block -> per-layer coverage rasters + via cut counts (npz-ish raw)
import klayout.db as db, sys, json, struct
gds, H = sys.argv[1], float(sys.argv[2])
ly = db.Layout(); ly.read(gds); top = ly.top_cell(); dbu = ly.dbu
l2n = db.LayoutToNetlist(db.RecursiveShapeIterator(ly, top, []))
M = {}
for n, (a, d) in dict(m1=(34,0), v1=(35,0), m2=(36,0), v2=(38,0), m3=(42,0), v3=(40,0), m4=(46,0), v4=(41,0), m5=(81,0)).items():
    M[n] = l2n.make_layer(ly.layer(a, d), n)
T = {n: l2n.make_text_layer(ly.layer(a, 10), 't' + n) for n, a in dict(m1=34, m2=36, m3=42, m4=46, m5=81).items()}
seq = ['m1', 'v1', 'm2', 'v2', 'm3', 'v3', 'm4', 'v4', 'm5']
for n in seq: l2n.connect(M[n])
for a, b in zip(seq, seq[1:]): l2n.connect(M[a], M[b])
for n in T: l2n.connect(M[n], T[n])
l2n.extract_netlist()
c = l2n.netlist().circuit_by_name(top.name)
bb = top.bbox(); x0, y0 = bb.left * dbu, bb.bottom * dbu
nx, ny = int((bb.width() * dbu) / H) + 1, int((bb.height() * dbu) / H) + 1
meta = dict(H=H, x0=x0, y0=y0, nx=nx, ny=ny, layers={})
for net in ('VDD', 'VSS'):
    nt = c.net_by_name(net)
    for n in seq:
        r = l2n.shapes_of_net(nt, M[n], True).merged()
        key = f'{net}_{n}'
        if n.startswith('m'):
            ras = r.rasterize(db.Point(int(x0 / dbu), int(y0 / dbu)), db.Vector(int(H / dbu), int(H / dbu)), nx, ny)
            with open(key + '.bin', 'wb') as f:
                for row in ras:
                    f.write(struct.pack(f'{nx}f', *[v * dbu * dbu / (H * H) for v in row]))
        else:
            cnt = {}
            for p in l2n.shapes_of_net(nt, M[n], True).each():
                ce = p.bbox().center(); k = (int((ce.x * dbu - x0) / H), int((ce.y * dbu - y0) / H))
                cnt[k] = cnt.get(k, 0) + 1
            json.dump([[k[0], k[1], v] for k, v in cnt.items()], open(key + '.json', 'w'))
        meta['layers'][key] = r.area() * dbu * dbu
json.dump(meta, open('meta.json', 'w'), indent=1)
print(json.dumps(meta))
