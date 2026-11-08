"""KLayout (pya) check: every ppolyf_u_1k body carries the HRES marker.

Run as:  klayout -b -r hres_check.py -rd gds=<file> -rd top=<cell> -rd out=<json>
Layers (gf180mcu GDS map): POLY2 30/0, RES_MK 110/5, HRES 62/0.
A high-R poly resistor body is POLY2 inside RES_MK; it must lie inside HRES.
Reports the number of RES_MK resistor bodies, how many overlap HRES, and the
number without HRES (must be 0 for any design that uses ppolyf_u_1k).
"""
import json
import pya

ly = pya.Layout()
ly.read(gds)  # noqa: F821  (-rd variables)
top_cell = ly.cell(top)  # noqa: F821
def region(l, d):
    li = ly.find_layer(l, d)
    return pya.Region() if li is None else pya.Region(top_cell.begin_shapes_rec(li))
poly2, resmk, hres = region(30, 0), region(110, 5), region(62, 0)
bodies = (poly2 & resmk).merged()
with_h = bodies.interacting(hres)
without_h = bodies - bodies.interacting(hres)
res = dict(gds=gds, top=top, resistor_bodies=bodies.count(), bodies_with_hres=with_h.count(),  # noqa: F821
           bodies_without_hres=without_h.count(), hres_shapes=hres.count(),
           bodies_not_fully_covered=(bodies - hres).merged().count())
open(out, 'w').write(json.dumps(res, indent=1))  # noqa: F821
print(json.dumps(res))
