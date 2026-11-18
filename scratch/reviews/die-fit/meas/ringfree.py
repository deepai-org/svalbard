# Die-fit: free area inside the provider pad ring band (outside the core), e.g. for probe frames or decap.
# Reads the v5 assembly padring source (provider reference ring). Read-only.
import klayout.db as db, json
f='/repo/projects/programmable_transceiver_platform/analog/pads/generated/provider-assembly-inputs/provider-reference-ring.gds'
ly=db.Layout(); ly.read(f); t=max(ly.top_cells(), key=lambda c:c.bbox().area()); bx=t.bbox(); dbu=ly.dbu
out=dict(top=t.name, bbox=[bx.left*dbu,bx.bottom*dbu,bx.right*dbu,bx.top*dbu])
PH=[(21,0),(22,0),(30,0),(34,0),(36,0),(42,0),(46,0),(81,0),(75,0)]
def reg(lts, clip):
    r=db.Region()
    for lt in lts:
        i=ly.find_layer(*lt)
        if i is not None: r+=db.Region(t.begin_shapes_rec_touching(i, clip))&db.Region(clip)
    return r.merged()
U=lambda v:int(v/dbu)
W,H=bx.width(),bx.height()
for name,(x0,y0) in dict(sw=(bx.left,bx.bottom), se=(bx.right-U(452),bx.bottom), nw=(bx.left,bx.top-U(452)), ne=(bx.right-U(452),bx.top-U(452))).items():
    clip=db.Box(x0,y0,x0+U(452),y0+U(452)); B=db.Region(clip)
    rec={}
    for tag,lts in (('all',PH),('m5',[(81,0)]),('m4',[(46,0)]),('m3',[(42,0)]),('m12',[(34,0),(36,0)]),('dev',[(21,0),(22,0),(30,0)])):
        occ=reg(lts,clip); free=B-occ.sized(U(3)); big=free.sized(-U(30)).sized(U(30))&free     # pieces >= 60 um wide
        rec[tag]=dict(occupied_mm2=round(occ.area()*dbu*dbu/1e6,4), free60_mm2=round(big.area()*dbu*dbu/1e6,4),
                      boxes=sorted([[round(p.bbox().width()*dbu),round(p.bbox().height()*dbu)] for p in big.each()], key=lambda b:-b[0]*b[1])[:3])
    out[name]=rec; print(name, json.dumps(rec), flush=True)
json.dump(out, open('/work/ringfree.json','w'), indent=1)
