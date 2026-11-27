import klayout.db as db, json
ly=db.Layout(); ly.read('/run/pt_wiredtx8.gds'); top=ly.top_cell()
L=db.LayoutToNetlist(db.RecursiveShapeIterator(ly,top,[]))
names=[('M1',34),('V1',35),('M2',36),('V2',38),('M3',42),('V3',40),('M4',46),('V4',41),('M5',81)]
R={n:L.make_layer(ly.layer(g,0),n) for n,g in names}
seq=['M1','V1','M2','V2','M3','V3','M4','V4','M5']
for a in seq: L.connect(R[a])
for a,b in zip(seq,seq[1:]): L.connect(R[a],R[b])
L.extract_netlist()
ties=json.load(open('/run/ties.json')); dbu=ly.dbu
for tn,t in ties.items():
  if not tn.startswith('chan'): continue
  p=db.Point(int((t[0]+t[1])/2/dbu),int((t[2]+t[3])/2/dbu)); hits=[]
  for n in ('M5','M4','M3'):
    net=L.probe_net(R[n],p)
    if net: hits.append((n,net.cluster_id)); break
  print(tn,t,hits)
p=db.Point(int(400/dbu),int(251/dbu))
for n in ('M5','M4','M3','M2','M1'):
  net=L.probe_net(R[n],p); print('plate',n,net.cluster_id if net else None)
