"""Read-back GDS checks for a published converter cell (runs inside the analog image with KLayout's Python module).

  python3 gds_check.py <cell.gds> <top> <ports (space separated)> <out.json>

Reports, from the GDS on disk:
  * bbox (um) and the boundary layer used for it (0/0 PR boundary if present, else the cell bbox);
  * every port label (Metal1..5 label layers x/10): layer, position, the metal shape under it on the drawing layer and
    whether that shape touches the cell edge (pins on the cell edge, ASM-8 / MANDATE 4a);
  * ports in the list with no label, and labels at top level that are not ports;
  * Metal5 (81/0) area and bbox (ASM-8: Metal5 belongs to the grid; any use is a declared exception);
  * marker / device-recognition layer shape counts (MIM 75/0 + CAP_MK 117/5, Dualgate 55/0, NAT 5/0, HRES 62/0,
    RES_MK 110/5, PMNDMY 152/5) so the caller can compare them with the device list (Magic export can drop markers).
"""
import json
import sys

import klayout.db as db

gds, top_name, ports, out = sys.argv[1], sys.argv[2], sys.argv[3].split(), sys.argv[4]
ly = db.Layout()
ly.read(gds)
top = ly.cell(top_name)
assert top is not None, f'no cell {top_name}'
dbu = ly.dbu
bb = top.dbbox()
METALS = {34: 'Metal1', 36: 'Metal2', 42: 'Metal3', 46: 'Metal4', 81: 'Metal5'}
EDGE_TOL = 0.01


def li(l, d):
    return ly.find_layer(l, d)


labels = []
for lnum, name in METALS.items():
    lt = li(lnum, 10)
    ld = li(lnum, 0)
    if lt is None:
        continue
    region = db.Region(top.begin_shapes_rec(ld)) if ld is not None else db.Region()
    region.merge()
    for s in top.shapes(lt).each():          # top-level labels only (ports)
        if not s.is_text():
            continue
        t = s.dtext
        p = db.Point(round(t.x / dbu), round(t.y / dbu))
        under = [poly for poly in region.each() if poly.inside(p) or poly.bbox().contains(p)]
        touch = None
        if under:
            b = under[0].bbox()
            x1, y1, x2, y2 = b.left * dbu, b.bottom * dbu, b.right * dbu, b.top * dbu
            sides = [k for k, ok in (('W', abs(x1 - bb.left) < EDGE_TOL), ('E', abs(x2 - bb.right) < EDGE_TOL),
                                     ('S', abs(y1 - bb.bottom) < EDGE_TOL), ('N', abs(y2 - bb.top) < EDGE_TOL)) if ok]
            touch = sides
        labels.append(dict(text=t.string, layer=name, x=round(t.x, 3), y=round(t.y, 3), shape=bool(under),
                           edge=touch))
by = {}
for lab in labels:
    by.setdefault(lab['text'], []).append(lab)
port_rows = {}
for p in ports:
    rows = by.get(p, [])
    good = [r for r in rows if r['layer'] in ('Metal3', 'Metal4') and r['shape'] and r['edge']]
    port_rows[p] = dict(labels=rows, on_edge_m34=bool(good))
m5 = li(81, 0)
m5r = db.Region(top.begin_shapes_rec(m5)) if m5 is not None else db.Region()
m5r.merge()
m5bb = m5r.bbox()
markers = {}
for k, (l, d) in {'MIM_75/0': (75, 0), 'CAP_MK_117/5': (117, 5), 'Dualgate_55/0': (55, 0), 'NAT_5/0': (5, 0),
                  'HRES_62/0': (62, 0), 'RES_MK_110/5': (110, 5), 'PMNDMY_152/5': (152, 5), 'Poly2_30/0': (30, 0)}.items():
    i = li(l, d)
    markers[k] = sum(1 for _ in top.begin_shapes_rec(i)) if i is not None else 0
res = dict(gds=gds, top=top_name, bbox_um=[bb.left, bb.bottom, bb.right, bb.top],
           size_um=[round(bb.width(), 3), round(bb.height(), 3)], area_mm2=round(bb.width() * bb.height() * 1e-6, 5),
           ports=port_rows,
           missing_ports=[p for p in ports if not by.get(p)],
           extra_labels=sorted(set(by) - set(ports)),
           ports_not_on_edge_m34=[p for p, r in port_rows.items() if not r['on_edge_m34']],
           metal5=dict(area_um2=round(m5r.area() * dbu * dbu, 1), polygons=m5r.count(),
                       bbox_um=[m5bb.left * dbu, m5bb.bottom * dbu, m5bb.right * dbu, m5bb.top * dbu] if m5r.count() else None),
           markers=markers)
json.dump(res, open(out, 'w'), indent=1)
print(json.dumps({k: res[k] for k in ('size_um', 'missing_ports', 'extra_labels', 'ports_not_on_edge_m34', 'metal5',
                                      'markers')}))
