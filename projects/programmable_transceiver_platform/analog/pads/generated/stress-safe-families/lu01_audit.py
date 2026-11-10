"""LU-01 audit (port of scratch/reviews/physical-limits/analyses/lu01/lu.py, same metric) for arbitrary GDS/top."""
import klayout.db as pya, json, sys
def audit(path, top=None):
    ly=pya.Layout(); ly.read(path); t=ly.cell(top) if top else ly.top_cells()[0]; dbu=ly.dbu
    def R(n):
        li=ly.find_layer(n,0)
        return pya.Region(t.begin_shapes_rec(li)).merged() if li is not None else pya.Region()
    comp,nw,pp,np_,poly,dnw=R(22),R(21),R(31),R(32),R(30),R(12)
    sd=comp-poly; ndiff=(sd&np_)-nw; pdiff=(sd&pp)&nw; ptap=(comp&pp)-nw; ntap=(comp&np_)&nw
    um=lambda x:int(x/dbu); res=dict(cell=t.name, ndiff_um2=round(ndiff.area()*dbu*dbu,1), pdiff_um2=round(pdiff.area()*dbu*dbu,1))
    for name,diff,tap in (('nmos_to_ptap',ndiff,ptap),('pmos_to_ntap',pdiff,ntap)):
        for lim in (5,10,15,20):
            res[f'{name}_uncovered_at_{lim}um_um2']=round((diff-tap.sized(um(lim))).area()*dbu*dbu,2)
        rings=[p for p in tap.each() if p.holes()>0]; enc=pya.Region()
        for p in rings:
            for h in range(p.holes()): enc.insert(pya.Polygon([q for q in p.each_point_hole(h)]))
        res[f'{name}_diff_in_ring_frac']=round(((diff&enc).area()/diff.area()) if diff.area() else 1,3)
        unc=diff-tap.sized(um(15)); res[f'{name}_uncovered15_bboxes']=[[round(c*dbu,1) for c in (b.left,b.bottom,b.right,b.top)] for b in [p.bbox() for p in unc.each()]][:10]
    return res
if __name__=='__main__':
    out={a:audit(*a.split(':')) for a in sys.argv[2:]}
    json.dump(out,open(sys.argv[1],'w'),indent=1); print(json.dumps(out,indent=1))
