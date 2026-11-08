"""KLayout (pya) layer-by-layer XOR of two GDS files (same top cell).
klayout -b -r gds_xor.py -rd ga=<A> -rd gb=<B> -rd top=<cell> -rd out=<json>"""
import pya, json
a=pya.Layout(); a.read(ga); b=pya.Layout(); b.read(gb)
ta=a.cell(top); tb=b.cell(top)
res={}
layers=set((l.layer,l.datatype) for l in a.layer_infos())|set((l.layer,l.datatype) for l in b.layer_infos())
for (L,D) in sorted(layers):
    ia=a.find_layer(L,D); ib=b.find_layer(L,D)
    ra=pya.Region(ta.begin_shapes_rec(ia)) if ia is not None else pya.Region()
    rb=pya.Region(tb.begin_shapes_rec(ib)) if ib is not None else pya.Region()
    x=(ra^rb).merged()
    if x.count():
        bb=x.bbox(); res['%d/%d'%(L,D)]=dict(polys=x.count(), area_um2=round(x.area()*a.dbu*a.dbu,3), bbox=[bb.left*a.dbu,bb.bottom*a.dbu,bb.right*a.dbu,bb.top*a.dbu])
open(out, 'w').write(json.dumps(res, indent=1))  # noqa: F821
print(json.dumps(res))
