# Die-fit: is the attachment column of pad_wirepad / pad_txpad narrower than the cell bbox (an L-shaped footprint)?
# For 50 um depth bands, report the lateral extent of ALL drawn shapes (any layer). Read-only.
import klayout.db as db, json
P='/proj/analog/pads/generated/stress-safe-families/'
out={}
for name,f in {'pad_wirepad':P+'wired-receive-usb/combined.gds','pad_txpad':P+'wired-transmit/combined.gds','pad_refpad':P+'reference/combined.gds'}.items():
    ly=db.Layout(); ly.read(f); t=max(ly.top_cells(),key=lambda c:c.bbox().area()); bx=t.bbox(); dbu=ly.dbu
    allr=db.Region()
    for li in ly.layer_indexes():
        allr+=db.Region(t.begin_shapes_rec(li))
    allr=allr.merged()
    long_is_y = bx.height()>bx.width()
    bands=[]
    L=bx.height() if long_is_y else bx.width()
    step=int(50/dbu); pos=0
    while pos<L:
        if long_is_y: clipb=db.Box(bx.left,bx.bottom+pos,bx.right,min(bx.top,bx.bottom+pos+step))
        else: clipb=db.Box(bx.left+pos,bx.bottom,min(bx.right,bx.left+pos+step),bx.top)
        r=allr&db.Region(clipb); b=r.bbox()
        if r.is_empty(): bands.append([pos*dbu,None,None,0])
        else:
            lo,hi=((b.left-bx.left)*dbu,(b.right-bx.left)*dbu) if long_is_y else ((b.bottom-bx.bottom)*dbu,(b.top-bx.bottom)*dbu)
            bands.append([pos*dbu,round(lo,1),round(hi,1),round(r.area()*dbu*dbu/ (clipb.area()*dbu*dbu),3)])
        pos+=step
    out[name]=dict(w=bx.width()*dbu,h=bx.height()*dbu,bands=bands)
    print(name,out[name]['w'],out[name]['h']); [print('  ',b) for b in bands]
json.dump(out,open('/work/padnotch.json','w'),indent=0)
