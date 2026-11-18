import sys, klayout.db as k
gds, top, x1,y1,x2,y2 = sys.argv[1], sys.argv[2], *map(float, sys.argv[3:7]); layers=sys.argv[7].split(','); minw=float(sys.argv[8]) if len(sys.argv)>8 else 0
L=k.Layout(); L.read(gds); t=L.cell(top); dbu=L.dbu
LY={'M1':34,'M2':36,'M3':42,'M4':46,'M5':81,'V1':35,'V2':38,'V3':40,'V4':41,'COMP':22,'PAD':37,'NW':21,'CONT':33,'POLY':30}
box=k.Box(int(x1/dbu),int(y1/dbu),int(x2/dbu),int(y2/dbu))
for ln in layers:
    li=L.find_layer(LY[ln],0)
    r=k.Region(t.begin_shapes_rec_overlapping(li,box)); r.merge()
    out=[]
    for p in r.each():
        b=p.bbox()
        if min(b.width(),b.height())*dbu<minw: continue
        out.append((round(b.left*dbu,3),round(b.bottom*dbu,3),round(b.right*dbu,3),round(b.top*dbu,3),'rect' if p.is_box() else f'poly{p.num_points()}'))
    print(ln,len(out))
    for o in sorted(out)[:int(sys.argv[9]) if len(sys.argv)>9 else 60]: print('  ',o)
