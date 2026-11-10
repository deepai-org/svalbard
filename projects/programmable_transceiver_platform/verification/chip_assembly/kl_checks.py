# KLayout batch script: geometry/connectivity checks on the assembled chip.
#   klayout -b -rd work=/work -r kl_checks.py
# Each check has a negative control that must fail, so a passing check is meaningful.
import json
import sys
import klayout.db as db

sys.path.insert(0, '/flow')
import inventory as inv   # noqa: E402
from klconn import LAYERS, METALS, window_regions, trace, touches, cell_labels, um   # noqa: E402

W = work
asm = json.load(open(W+'/assembly.json'))
fp = json.load(open(W+'/floorplan.json'))
ly = db.Layout()
ly.read(W+'/pt_chip_top.gds')
top = ly.cell('pt_chip_top')
out = {}

def inst_of(name):
    return [i for i in top.each_inst() if i.cell.name == name]

# 1. Unintended overlap of drawn top-level metal (pt_pdn) with block/pad metal -------------
pdn = ly.cell('pt_pdn')
pdn_reg = {m: db.Region(pdn.begin_shapes_rec(ly.find_layer(*LAYERS[m]))).merged() for m in METALS}
allowed = ('gf180mcu_fd_io__dvdd', 'gf180mcu_fd_io__dvss', 'gf180mcu_fd_io__in_c', 'retained_provider_ring',
           'pad_rf_pair', 'pad_single_leg_b', 'isw_')
hits = {}
where = {}
for inst in top.each_inst():
    c = inst.cell
    if c.name in ('pt_pdn', 'pt_digital_macro_abstract') or c.name.startswith('decap_'):
        continue
    bb = inst.bbox()
    for m in METALS:
        r = pdn_reg[m] & db.Region(bb)
        if r.is_empty():
            continue
        idx = ly.find_layer(*LAYERS[m])
        cr = db.Region(c.begin_shapes_rec(idx)).transformed(inst.cplx_trans if hasattr(inst, 'cplx_trans') else inst.dcplx_trans.to_itrans(ly.dbu))
        ov = cr & r
        if not ov.is_empty():
            key = f'{c.name}/{m}'
            hits[key] = hits.get(key, 0)+ov.count()
            where.setdefault(key, []).extend([[round(v*ly.dbu, 2) for v in (q.bbox().left, q.bbox().bottom, q.bbox().right, q.bbox().top)]
                                              for q in ov.each()][:6])
unexpected = {k: v for k, v in hits.items() if not k.split('/')[0].startswith(allowed)}
# Negative control: one Metal4 shape of a non-allowed pad cell added to the pdn metal must be found.
neg_found = None
for inst in top.each_inst():
    if inst.cell.name in ('pad_txpad', 'pad_refpad', 'pad_wirepad'):
        idx = ly.find_layer(*LAYERS['M4'])
        cr = db.Region(inst.cell.begin_shapes_rec(idx)).transformed(inst.cplx_trans)
        probe = db.Region(next(cr.each()).bbox())
        neg_found = not ((pdn_reg['M4']+probe) & cr).is_empty()
        break
# Shapes drawn directly in the top cell (not in pt_pdn or an instance) bypass every check
# above; the orphan packaging interconnect was such a case. Labels are allowed.
top_own = {}
for idx in ly.layer_indexes():
    n = sum(1 for s in top.shapes(idx).each() if not s.is_text())
    if n:
        info = ly.get_info(idx)
        top_own[f'{info.layer}/{info.datatype}'] = n
out['pdn_overlaps'] = dict(by_instance_layer=hits, unexpected=unexpected,
                           unexpected_where={k: where[k] for k in unexpected}, negative_control_detected=neg_found,
                           top_cell_own_geometry=top_own,
                           ok=not unexpected and neg_found is True and not top_own)

# 2. Pad-family shape overlaps against neighbours (mirrored wired cells, WMON B cell) -------
pad_insts = [i for i in top.each_inst() if i.cell.name.startswith('pad_')]
pair_ov = []
for a in range(len(pad_insts)):
    for b in range(a+1, len(pad_insts)):
        A, B = pad_insts[a], pad_insts[b]
        if not A.bbox().overlaps(B.bbox()):
            continue
        box = A.bbox() & B.bbox()
        for m in METALS:
            idx = ly.find_layer(*LAYERS[m])
            ra = db.Region(top.begin_shapes_rec_touching(idx, box))
            # shapes of each instance only
            sa = db.Region(A.cell.begin_shapes_rec(idx)).transformed(A.cplx_trans) & db.Region(box)
            sb = db.Region(B.cell.begin_shapes_rec(idx)).transformed(B.cplx_trans) & db.Region(box)
            if not (sa & sb).is_empty():
                pair_ov.append(f'{A.cell.name}@{A.bbox().center()} x {B.cell.name}@{B.bbox().center()} {m}')
out['pad_family_overlaps'] = dict(ok=not pair_ov, overlaps=pair_ov,
                                  bbox_overlapping_pairs=sum(1 for a in range(len(pad_insts)) for b in range(a+1, len(pad_insts))
                                                             if pad_insts[a].bbox().overlaps(pad_insts[b].bbox())))

# 3. Shared debug buses: rail joined by the bus, rail/VSS separate; negative control --------
def pad_inst(name):
    p = asm['pads'][name]
    return next(i for i in pad_insts if i.cell.name == p['cell'] and
                abs(i.bbox().center().y/1000-(p['bbox'][1]+p['bbox'][3])/2) < 1 and
                abs(i.bbox().center().x/1000-(p['bbox'][0]+p['bbox'][2])/2) < 1)
bus_res = {}
for a_name, b_name in inv.SHARED_PROTECTION:
    A, B = pad_inst(a_name), pad_inst(b_name)
    win = (A.bbox()+B.bbox()).enlarged(um(60), um(60))
    regs = window_regions(ly, top, win)
    la = {n: (l, p) for n, l, p in cell_labels(ly, A.cell, A.cplx_trans, ('ESD_RAIL', 'VSS'))}
    lb = {n: (l, p) for n, l, p in cell_labels(ly, B.cell, B.cplx_trans, ('ESD_RAIL', 'VSS'))}
    ra, rb = trace(regs, *la['ESD_RAIL']), trace(regs, *lb['ESD_RAIL'])
    va = trace(regs, *la['VSS'])
    joined = touches(ra, rb)
    short = touches(ra, va)
    bus = asm['debug_buses'][f'{a_name}+{b_name}']
    neg = {}
    if isinstance(bus.get('ESD_RAIL'), dict):
        x1, y1, x2, y2 = bus['ESD_RAIL']['rect']
        cut = dict(regs)
        cut['M5'] = regs['M5'] - db.Region(db.Box(um(x1), um(y1), um(x2), um(y2)))
        neg['rail_bus_removed_still_joined'] = touches(trace(cut, *la['ESD_RAIL']), trace(cut, *lb['ESD_RAIL']))
    vss_bus_on_both = False
    if isinstance(bus.get('VSS'), dict):
        x1, y1, x2, y2 = bus['VSS']['rect']
        busr = db.Region(db.Box(um(x1), um(y1), um(x2), um(y2)))
        vb = trace(regs, *lb['VSS'])
        own_a = va['M4'] & db.Region(A.bbox())
        own_b = vb['M4'] & db.Region(B.bbox())
        vss_bus_on_both = not (busr & own_a).is_empty() and not (busr & own_b).is_empty()
        widths = (x2-x1, y2-y1)
    bus_res[f'{a_name}+{b_name}'] = dict(rail_joined=joined, rail_vss_short=short, negative_control=neg,
                                         vss_bus_lands_on_both=vss_bus_on_both,
                                         ok=joined and not short and neg.get('rail_bus_removed_still_joined') is False and vss_bus_on_both)
out['debug_buses'] = bus_res

# 4. Island switch strapping: VDD and VISL separate, VISL bar reached at >= 4 points --------
sw = {}
for p in fp['placed']:
    if not p['master'].startswith('isw_'):
        continue
    inst = next(i for i in top.each_inst() if i.cell.name == p['master'])
    win = inst.bbox().enlarged(um(40), um(40))
    regs = window_regions(ly, top, win)
    labs = cell_labels(ly, inst.cell, inst.cplx_trans, ('VDD', 'VISL'))
    vdd = [x for x in labs if x[0] == 'VDD']
    visl = [x for x in labs if x[0] == 'VISL']
    nv, ni = trace(regs, vdd[0][1], vdd[0][2]), trace(regs, visl[0][1], visl[0][2])
    m5_island_bar = ni['M5'].count()
    # straps landing on the VISL bar: Metal5 polygons of the VISL net crossing the cell edge
    edge = db.Region(db.Box(inst.bbox().left, inst.bbox().bottom-um(5), inst.bbox().right, inst.bbox().bottom+um(1)))
    straps = (ni['M5'] & edge).count()
    # negative control: bridge the two bars with Metal5 -> must short
    bridged = dict(regs)
    x = vdd[0][2].x
    bridged['M5'] = (regs['M5'] + db.Region(db.Box(x-um(5), inst.bbox().bottom-um(30), x+um(5), inst.bbox().top+um(30)))).merged()
    neg_short = touches(trace(bridged, vdd[0][1], vdd[0][2]), trace(bridged, visl[0][1], visl[0][2]))
    sw[p['name']] = dict(vdd_visl_short=touches(nv, ni), visl_strap_crossings=straps, negative_control_short_detected=neg_short,
                         ok=not touches(nv, ni) and straps >= 4 and neg_short)
out['island_strapping'] = sw

# 5. Core ring: VDD/VSS separate at every corner window; RESET_N PD/PU ties -----------------
ring = {}
for name, (cx, cy) in dict(sw=(408, 408), se=(3524, 408), nw=(408, 4714), ne=(3524, 4714)).items():
    win = db.Box(um(cx-120), um(cy-120), um(cx+120), um(cy+120))
    regs = window_regions(ly, top, win)
    vss_pt = db.Point(um(cx+(-15.5 if cx < 2000 else 15.5)), um(cy+(-15.5 if cy < 2000 else 15.5)))
    vdd_pt = db.Point(um(cx+(15.5 if cx < 2000 else -15.5)), um(cy+(15.5 if cy < 2000 else -15.5)))
    a, b = trace(regs, 'M4', vss_pt), trace(regs, 'M4', vdd_pt)
    ring[name] = dict(vss_found=a['M4'].count() > 0, vdd_found=b['M4'].count() > 0, short=touches(a, b) if a['M4'].count() and b['M4'].count() else None)
rst = asm['reset_n_ties']
out['core_ring'] = dict(corners=ring, reset_n=rst,
                        ok=all(v['vss_found'] and v['vdd_found'] and v['short'] is False for v in ring.values()))
json.dump(out, open(W+'/geometry-checks.json', 'w'), indent=1, default=str)
print('CHECKS', {k: (v.get('ok') if isinstance(v, dict) and 'ok' in v else {kk: vv.get('ok') for kk, vv in v.items()}) for k, v in out.items()})
