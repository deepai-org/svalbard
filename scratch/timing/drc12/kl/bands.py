import pya, json
# bands in block coordinates: (gds, top, [x0,y0,x1,y1] in chip coords, trans) -> layers present
jobs = json.load(open('/w/kl/bands.json'))
for j in jobs:
    ly = pya.Layout(); ly.read(j['gds']); top = ly.cell(j['top'])
    t = pya.DCplxTrans(1, j['rot'], False, j['dx'], j['dy']).inverted()
    for b in j['boxes']:
        bb = t * pya.DBox(*b)
        res = []
        for li in ly.layer_indexes():
            info = ly.get_info(li)
            r = pya.Region(top.begin_shapes_rec_touching(li, bb.to_itype(ly.dbu)))
            r &= pya.Region(bb.to_itype(ly.dbu))
            if not r.is_empty(): res.append(f'{info.layer}/{info.datatype}:{r.area()*ly.dbu**2/bb.area():.2f}')
        print(j['name'], [round(v,1) for v in (bb.left,bb.bottom,bb.right,bb.top)], ' '.join(res))
