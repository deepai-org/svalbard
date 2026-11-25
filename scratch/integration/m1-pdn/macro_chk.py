import klayout.db as db, json
ly=db.Layout(); ly.read('/run/chip/pt_chip_top.gds'); top=ly.cell('pt_chip_top')
man=json.load(open('/run/chip/manifest.json')); b=[i for i in man['instances'] if i['name']=='digital'][0]
box=db.DBox(*b['bbox']).to_itype(ly.dbu); print('macro bbox',b['bbox'], b['trans'])
for nm,L in (('M4',(46,0)),('V4',(41,0)),('M5',(81,0))):
    li=ly.find_layer(*L); per={}
    it=db.RecursiveShapeIterator(ly,top,li,box,False)
    while not it.at_end():
        p=[e.inst().cell.name for e in it.path()]; k=p[0] if p else 'top'
        a=per.setdefault(k,[0,0]); a[0]+=1; a[1]+=it.shape().bbox().area()*ly.dbu**2; it.next()
    print(nm,{k:(v[0],round(v[1])) for k,v in per.items()})
mc=ly.cell(b['cell']); print('macro cell',mc.name, mc.dbbox())
for nm,L in (('M4',(46,0)),('V4',(41,0)),('M5',(81,0))):
    print(nm,'in macro cell', db.Region(mc.begin_shapes_rec(ly.find_layer(*L))).count())
# macro supply labels
for L in ((46,10),(81,10),(46,0),(81,0)):
    li=ly.find_layer(*L)
    if li is None: continue
    it=mc.begin_shapes_rec(li); labs=collections=set() if False else set()
    while not it.at_end():
        if it.shape().is_text(): labs.add(it.shape().text.string)
        it.next()
    print(L,[x for x in labs if x.upper() in ('VDD','VSS','VPWR','VGND')])
