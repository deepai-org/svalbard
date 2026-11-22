import pya
ly=pya.Layout(); ly.read(g); c=max(ly.top_cells(), key=lambda q:q.dbbox().area()); b=c.dbbox()
m5=pya.Region(c.begin_shapes_rec(ly.layer(81,0))).merged()
ch=pya.Region()
for k in range(-1,25):
    for ax in (12.25,47.25):
        x=b.left+ax+70*k
        ch.insert(pya.DBox(x-13.5,b.bottom,x+13.5,b.top).to_itype(ly.dbu))
print('bbox',b,'M5 total',round(m5.area()*ly.dbu**2),'um2', 'M5 in channels', round((m5&ch).area()*ly.dbu**2,1),'um2')
