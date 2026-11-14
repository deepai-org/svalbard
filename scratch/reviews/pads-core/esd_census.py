"""Layer census (ESD 24/0, SAB 49/0, DNWELL 12/0, NAT 5/0, ...) over published GDS. KLayout python, hierarchy based.
usage (in the image): python3 /work/ws/esd_census.py  -> /work/ws/layer-census.json
Per file and top cell: drawn shape count and drawn area (um2, overlaps not merged) with instance multiplicity; owner cells
(cells that draw the layer themselves). For ESD and SAB also the context: merged area of the layer AND other layers."""
import klayout.db as kdb, json, glob, os, sys, time
LAY = dict(ESD=(24, 0), ESD_MK=(24, 5), SAB=(49, 0), DNWELL=(12, 0), NAT=(5, 0), HRES=(62, 0), RES_MK=(110, 5), FuseTop=(75, 0), CAP_MK=(117, 5),
           MIM_L_MK=(117, 10), Via5=(82, 0), MetalTop=(53, 0), FuseWindow_D=(96, 1), PLFUSE=(125, 5), GUARD_RING_MK=(167, 5), LDMOS_XTOR=(226, 0), MVSD=(210, 0), MVPSD=(11, 39))
CTX = dict(COMP=(22, 0), Poly2=(30, 0), Nplus=(32, 0), Pplus=(31, 0), Nwell=(21, 0), Dualgate=(55, 0), SAB=(49, 0), ESD=(24, 0), DNWELL=(12, 0), LVPWELL=(204, 0))
files = []
for pat in ('/proj/analog/**/*.gds', '/proj/analog/**/*.gds.gz', '/proj/verification/digital_hardening/**/*.gds'):
    files += glob.glob(pat, recursive=True)
files += ['/work/agnd/pad_agnd_flat.gds', '/work/hspad/b2/pad_hspad.gds', '/foss/pdks/gf180mcuD/libs.ref/gf180mcu_fd_io/gds/gf180mcu_fd_io.gds']
files += glob.glob('/scratch/island-support-20261108-075605/layout/*.gds') + ['/scratch/core-bias-routing-20261110-compact/pt_core_bias_routed.gds']
files += glob.glob('/scratch/pad-compact/rf-pair/pad.gds') + glob.glob('/scratch/pad-compact/reference_clock/pad/combined.gds')
if len(sys.argv) > 1: files = sys.argv[1:]
files = sorted(set(files)); out = {}; t0 = time.time()
def mult(ly, top):
    m = {top.cell_index(): 1}
    order = []
    def topo(ci, seen):
        if ci in seen: return
        seen.add(ci)
        for cc in ly.cell(ci).each_child_cell(): topo(cc, seen)
        order.append(ci)
    topo(top.cell_index(), set())
    for ci in reversed(order):
        k = m.get(ci, 0)
        if not k: continue
        for inst in ly.cell(ci).each_inst():
            m[inst.cell_index] = m.get(inst.cell_index, 0)+k*inst.size()
    return m
for f in files:
    try:
        ly = kdb.Layout(); ly.read(f)
    except Exception as e:
        out[f] = dict(error=str(e)); continue
    dbu = ly.dbu; rec = {}
    li = {n: ly.find_layer(*lp) for n, lp in LAY.items()}
    own = {}
    for n, i in li.items():
        if i is None: continue
        for c in ly.each_cell():
            sh = c.shapes(i)
            if sh.size():
                a = sum(s.area() for s in sh.each())*dbu*dbu
                own.setdefault(n, {})[c.cell_index()] = (sh.size(), a)
    if not own:
        out[f] = dict(tops=[t.name for t in ly.top_cells()], none=True); continue
    for top in ly.top_cells():
        m = None; tr = {}
        for n, d in own.items():
            if m is None: m = mult(ly, top)
            cnt = sum(v[0]*m.get(ci, 0) for ci, v in d.items()); ar = sum(v[1]*m.get(ci, 0) for ci, v in d.items())
            if not cnt: continue
            owners = sorted(((ly.cell(ci).name, m.get(ci, 0), v[0], round(v[1], 2)) for ci, v in d.items() if m.get(ci, 0)), key=lambda x: -x[1]*x[3])
            tr[n] = dict(shapes=cnt, drawn_area_um2=round(ar, 2), n_owner_cells=len(owners), owners=owners[:12])
        # context for ESD and SAB (merged, flat) -- only when present and the file is not huge
        for n in ('ESD', 'SAB', 'DNWELL', 'NAT'):
            if n in tr and os.path.getsize(f) < 120e6:
                R = lambda lp: kdb.Region(top.begin_shapes_rec(ly.find_layer(*lp))) if ly.find_layer(*lp) is not None else kdb.Region()
                base = R(LAY[n]).merged(); c = dict(merged_area_um2=round(base.area()*dbu*dbu, 2), polygons=base.count())
                comp = R(CTX['COMP']); poly = R(CTX['Poly2']); gate = (comp & poly)
                g_in = gate & base
                c['gate_area_um2'] = round(g_in.area()*dbu*dbu, 2); c['gates'] = g_in.merged().count()
                c['gates_Nplus'] = (g_in & R(CTX['Nplus'])).merged().count(); c['gates_Pplus'] = (g_in & R(CTX['Pplus'])).merged().count()
                c['gates_in_Dualgate'] = (g_in & R(CTX['Dualgate'])).merged().count()
                c['comp_no_poly_um2'] = round(((comp-poly) & base).area()*dbu*dbu, 2); c['poly_no_comp_um2'] = round(((poly-comp) & base).area()*dbu*dbu, 2)
                if n != 'SAB': c['and_SAB_um2'] = round((base & R(CTX['SAB'])).area()*dbu*dbu, 2)
                if n != 'ESD': c['and_ESD_um2'] = round((base & R(CTX['ESD'])).area()*dbu*dbu, 2)
                c['and_Nwell_um2'] = round((base & R(CTX['Nwell'])).area()*dbu*dbu, 2)
                tr[n]['context'] = c
        if tr: rec[top.name] = tr
    out[f] = rec if rec else dict(tops=[t.name for t in ly.top_cells()], none=True)
    print('%6.0fs %s %s' % (time.time()-t0, f, {t: {n: (v['shapes'], v['drawn_area_um2']) for n, v in tr.items()} for t, tr in rec.items()} if rec else 'none'), flush=True)
    json.dump(out, open('/work/ws/layer-census.json', 'w'), indent=0)
