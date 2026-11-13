# klayout -b -r dens.py -rd gds=... -rd out=... [-rd tile=250]
# Per-layer density (drawn, drawn+dummy) over the top-cell bbox, PDK density-deck definition, plus where fill landed:
# dummy squares under inductor metal (thick M5 spiral shapes / IND_MK), over MIM (FuseTop), and a tile map of min density.
import klayout.db as db, json
ly = db.Layout(); ly.read(gds)
top = max(ly.top_cells(), key=lambda c: c.bbox().area())
if top.name.startswith('FRAME_'):
    blk = ly.cell(top.name[6:]); bb = blk.bbox()
else:
    bb = top.bbox()
area = float(bb.area()); dbu = ly.dbu; WIN = db.Region(bb)
L = dict(COMP=22, Poly2=30, Metal1=34, Metal2=36, Metal3=42, Metal4=46, Metal5=81)
LIM = dict(COMP=25, Poly2=14, Metal1=30, Metal2=30, Metal3=30, Metal4=30, Metal5=30)
def reg(l, d):
    i = ly.find_layer(l, d)
    if i is None: return db.Region()
    r = db.Region(top.begin_shapes_rec(i)); r.merge(); return r & WIN
res = dict(gds=gds, top=top.name, bbox_um=[bb.width()*dbu, bb.height()*dbu], layers={})
dr, du = {}, {}
for n, l in L.items():
    dr[n], du[n] = reg(l, 0), reg(l, 4)
    a0, a1 = dr[n].area()/area*100, (dr[n]+du[n]).merged().area()/area*100
    res['layers'][n] = dict(drawn_pct=round(a0, 2), with_dummy_pct=round(a1, 2), limit_pct=LIM[n], passes=a1 >= LIM[n], dummy_shapes=du[n].count())
# keep-out markers present?
res['markers'] = {k: reg(*v).count() for k, v in dict(PMNDMY=(152, 5), NDMY=(111, 5), IND_MK=(151, 5), FuseTop=(75, 0), RES_MK=(110, 5)).items()}
# fill under/over sensitive structures
def under(dummy, shield):
    return dict(shapes=(dummy & shield).count(), area_um2=round((dummy & shield).area()*dbu*dbu, 1), struct_area_um2=round(shield.area()*dbu*dbu, 1))
mim = reg(75, 0)
if not mim.is_empty():
    res['fill_vs_mim'] = {n: under(du[n], mim) for n in L}
ind_cells = [c for c in ly.each_cell() if any(k in c.name.lower() for k in ('spiral', 'lna_ind', 'inductor', '_ind_', 'balun'))]
if ind_cells:
    names = set(c.name for c in ind_cells)
    ind = db.Region()
    def walk(cell, tr, depth=0):
        for inst in cell.each_inst():
            t = tr * inst.cplx_trans
            if inst.cell.name in names:
                ind.insert(inst.cell.bbox().transformed(t))
            elif depth < 6:
                walk(inst.cell, t, depth + 1)
    walk(top, db.ICplxTrans())
    ind.merge(); ind = ind & WIN
    coil = ((dr['Metal3'] + dr['Metal4'] + dr['Metal5']) & ind).merged()
    res['inductor_cells'] = sorted(names)
    res['inductor_bbox_um2'] = round(ind.area()*dbu*dbu, 1)
    res['fill_in_inductor_bbox'] = {n: under(du[n], ind) for n in L}
    res['fill_directly_under_over_coil_metal'] = {n: under(du[n], coil) for n in L}
t = float(globals().get('tile', 0) or 0)
if t > 0:
    nx, ny = max(1, int(bb.width()*dbu/t)), max(1, int(bb.height()*dbu/t))
    tm = {}
    for n in ('Metal1', 'Metal2', 'COMP'):
        r = (dr[n]+du[n]).merged(); vals = []
        for ix in range(nx):
            for iy in range(ny):
                box = db.Box(bb.left+int(ix*t/dbu), bb.bottom+int(iy*t/dbu), bb.left+int((ix+1)*t/dbu), bb.bottom+int((iy+1)*t/dbu))
                vals.append(round((r & db.Region(box)).area()/float(box.area())*100, 1))
        vals.sort(); tm[n] = dict(tiles=len(vals), min=vals[0], p10=vals[len(vals)//10], median=vals[len(vals)//2], max=vals[-1])
    res['tile_density_pct'] = tm
json.dump(res, open(out, 'w'), indent=1)
print(json.dumps(res['layers']))
