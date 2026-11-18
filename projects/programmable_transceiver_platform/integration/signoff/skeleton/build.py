# KLayout batch script: skeleton chip assembly.   kl.sh skeleton/build.py [-rd out=skel/pt_chip_skel.gds]
# Input /run/skel/plan.json (skeleton/plan.py). Output /run/skel/pt_chip_skel.gds and /run/skel/manifest.json.
# Real ring (provider pad ring, seal ring, ID cells and marker of the 1x1 slot) + custom pad families + every block that
# has a GDS matching its floorplan rectangle + pin-only placeholders for the rest. No top-level wiring.
import json
import klayout.db as db

R = '/repo'
OUT = globals().get('out', 'skel/pt_chip_skel.gds')
plan = json.load(open('/run/skel/plan.json'))
BASE = R+'/projects/programmable_transceiver_platform/analog/pads/generated/packaging-assembly.gds'
TOP = 'pt_chip_top'
um = lambda v: int(round(v*1000))
man = dict(top=TOP, base_ring=BASE[len(R)+1:], instances=[], notes=[], ring_sites_replaced=[], pad_over_provider_cell=[], pad_snap=[], ring_sites_restored=[])

ly = db.Layout(); ly.dbu = 0.001
ly.read(BASE)
top = ly.cell('custom_assembly_candidate'); top.name = TOP
# Wiring drawn in the base top cell belongs to the packaging candidate's own custom cells, which are removed here.
orphan = 0
for li in ly.layer_indexes():
    orphan += top.shapes(li).size(); top.shapes(li).clear()
gone = []
for inst in list(top.each_inst()):
    n = inst.cell.name
    if n.startswith('custom_') or n.startswith('attached_tx_'):
        gone.append(n); inst.delete()
man['notes'].append(f'base top: {orphan} orphan shapes cleared, removed instances {sorted(set(gone))}')
keep_src = {}   # cells of the base file that are re-used as masters (looked up before pruning)
for n in sorted(set(gone)):
    c = ly.cell(n)
    if c is not None and c.is_top() and n != 'attached_tx_interlock':
        ly.prune_cell(c.cell_index(), -1)
ring = ly.cell('retained_provider_ring')
rail = next(ly.cell(i) for i in ring.each_child_cell() if ly.cell(i).name.startswith('5LM_METAL_RAIL'))

L_BND = ly.layer(0, 0)          # PR boundary
L_M4, L_M4L = ly.layer(46, 0), ly.layer(46, 10)
L_PAD = ly.layer(37, 0)
_m = db.Layout(); _m.read(R+'/'+globals().get('mask', 'scratch/integration/signoff-gap/dl/precheck-live/assets/golden_masks/mask_1x1.gds'))
MASKR = db.Region(_m.top_cell().begin_shapes_rec(_m.layer(37, 0))).merged()
MASK = [q.bbox() for q in MASKR.each() if q.bbox().width() < 100000 and q.bbox().height() < 100000]     # bond openings (not the seal-ring frame)

imported = {}
def import_cell(key, path, cell_name):
    """Copy a cell tree from another file under the name `key` (children are renamed automatically on clashes)."""
    if key in imported: return imported[key]
    if path == BASE:
        c = ly.cell(cell_name); c.name = key; imported[key] = c; return c
    src = db.Layout(); src.read(path)
    c = src.cell(cell_name) if cell_name else None
    if c is None:
        tops = sorted(src.top_cells(), key=lambda t: -t.bbox().area())
        c = tops[0]
        if cell_name: man['notes'].append(f'{key}: cell {cell_name} not in {path[len(R)+1:]}, used {c.name}')
    tgt = ly.create_cell(key); tgt.copy_tree(c)
    imported[key] = tgt
    return tgt

def placeholder(master, w, h, pins):
    key = master          # the cell IS the black box of that master: same name as in the reference netlist
    if key in imported: return imported[key]
    c = ly.create_cell(key)
    c.shapes(L_BND).insert(db.Box(0, 0, um(w), um(h)))
    c.shapes(L_BND).insert(db.Text('PLACEHOLDER '+master, db.Trans(db.Vector(um(1), um(1)))))
    # pins: 2 x 2 um Metal4 squares on a 6 um pitch, rings 3 um inside the outline, as many rings as needed
    slots, inset = [], 3.0
    while len(slots) < len(pins) and inset*2+2 < min(w, h):
        x = inset
        while x+2 <= w-inset: slots.append((x, inset)); slots.append((x, h-inset-2)); x += 6
        y = inset+6
        while y+2 <= h-inset-6: slots.append((inset, y)); slots.append((w-inset-2, y)); y += 6
        inset += 6
    for p, (x, y) in zip(pins, slots):
        c.shapes(L_M4).insert(db.Box(um(x), um(y), um(x+2), um(y+2)))
        c.shapes(L_M4L).insert(db.Text(p, db.Trans(db.Vector(um(x+1), um(y+1)))))
    if len(slots) < len(pins): man['notes'].append(f'{key}: only {len(slots)} of {len(pins)} pins drawn')
    imported[key] = c
    return c

def fit_trans(c, rect, others):
    """Transformation that puts cell c into rect. Returns (trans, how) or (None, why).
    exact / smaller: lower-left aligned inside the rectangle. larger: the cell is bigger than its rectangle (the floorplan
    booked a size the published cell does not have); it is placed on one of the rectangle's corners if it then touches
    no other rectangle and stays in the core."""
    b = c.bbox(); w, h = b.width()/1000, b.height()/1000
    W, H = rect[2]-rect[0], rect[3]-rect[1]
    def tr_at(rot, x, y):
        X, Y = um(x), um(y)
        return db.Trans(db.Trans.R90, db.Vector(X+b.top, Y-b.left)) if rot else db.Trans(db.Trans.R0, db.Vector(X-b.left, Y-b.bottom))
    for rot, (cw, ch) in ((False, (w, h)), (True, (h, w))):
        exact = abs(cw-W) <= 1.5 and abs(ch-H) <= 1.5
        if exact or (cw <= W+1.5 and ch <= H+1.5):
            return tr_at(rot, rect[0], rect[1]), ('exact' if exact else 'smaller')+(' R90' if rot else '')
    core = plan['core']
    for rot, (cw, ch) in ((False, (w, h)), (True, (h, w))):
        for x, y in ((rect[0], rect[1]), (rect[2]-cw, rect[1]), (rect[0], rect[3]-ch), (rect[2]-cw, rect[3]-ch)):
            r = (x-2, y-2, x+cw+2, y+ch+2)
            if x < core[0] or y < core[1] or x+cw > core[2] or y+ch > core[3]: continue
            if any(r[0] < o[2] and o[0] < r[2] and r[1] < o[3] and o[1] < r[3] for o in others): continue
            return tr_at(rot, x, y), f'larger than its rectangle ({w:.1f} x {h:.1f} vs {W:.1f} x {H:.1f})'+(' R90' if rot else '')
    return None, f'cell {w:.1f} x {h:.1f} vs rect {W:.1f} x {H:.1f}'

def record(name, master, cell, tr, kind, src, how, in_conn):
    bb = tr*cell.bbox()
    man['instances'].append(dict(name=name, master=master, cell=cell.name, trans=str(tr), kind=kind, how=how, in_conn=in_conn,
                                 gds=src.get('gds') if src else None, sha256=src.get('sha256') if src else None,
                                 bbox=[bb.left/1000, bb.bottom/1000, bb.right/1000, bb.top/1000]))

# ---------------------------------------------------------------- custom pad families
for p in plan['pads']:
    x1 = min(r[0] for r in p['rects']); y1 = min(r[1] for r in p['rects']); x2 = max(r[2] for r in p['rects']); y2 = max(r[3] for r in p['rects'])
    if not p['cands']:
        man['notes'].append(f"{p['name']}: no pad GDS for {p['master']}"); continue
    src = p['cands'][0]
    c = import_cell(p['master'], R+'/'+src['gds'], src['cell'])
    b = c.bbox()
    # packaging convention: west M45 (x,y)->(y,x), east R90 (x,y)->(-y,x); local x along the edge, local y into the core
    if p['edge'] == 'west': tr = db.Trans(db.Trans.M45, db.Vector(um(x1)-b.bottom, um(y1)-b.left))
    else: tr = db.Trans(db.Trans.R90, db.Vector(um(x2)+b.bottom, um(y1)-b.left))
    # snap along the edge so that the family's bond openings sit on the template openings (golden mask of the slot)
    op = [q.bbox() for q in db.Region(c.begin_shapes_rec(L_PAD)).merged().transformed(tr).each()]
    d = sorted(min((m.bottom-o.bottom for m in MASK if abs(m.left-o.left) < 5000), key=abs) for o in op) if op else [0]
    shift = d[len(d)//2]
    if shift:
        tr = db.Trans(db.Vector(0, shift))*tr
        man['pad_snap'].append(dict(pad=p['name'], shift_um=shift/1000, spread_um=(d[-1]-d[0])/1000))
    got = tr*b
    how = 'exact' if max(abs(got.left/1000-x1), abs(got.right/1000-x2), abs(got.bottom/1000-y1), abs(got.top/1000-y2)) <= 2.0 else \
        f'bbox {got.width()/1000:.1f} x {got.height()/1000:.1f} vs floorplan {x2-x1:.1f} x {y2-y1:.1f}'
    top.insert(db.CellInstArray(c.cell_index(), tr))
    record(p['name'], p['master'], c, tr, src['kind'], src, how, p['in_conn'])
    # provider IO cells whose bond opening the pad family replaces (its own Pad opening lies on the site) give way to the rail cell
    opening = db.Region(c.begin_shapes_rec(L_PAD)).transformed(tr)
    for inst in list(ring.each_inst()):
        n = inst.cell.name
        if 'fill' in n or n.startswith('5LM') or '__cor' in n: continue
        ib = inst.bbox()
        if not (opening & db.Region(ib)).is_empty():
            t = inst.trans; inst.delete(); ring.insert(db.CellInstArray(rail.cell_index(), t))
            man['ring_sites_replaced'].append(dict(pad=p['name'], was=n, at=[ib.left/1000, ib.bottom/1000]))
        elif got.overlaps(ib):
            man['pad_over_provider_cell'].append(dict(pad=p['name'], cell=n, at=[ib.left/1000, ib.bottom/1000]))

# rail-only sites left without any bond opening (customised for an older pad plan in the base ring) get a provider analog pad back
allop = db.Region(top.begin_shapes_rec(L_PAD)).merged()
asig = next(ly.cell(i) for i in ring.each_child_cell() if 'asig_5p0' in ly.cell(i).name)
for inst in list(ring.each_inst()):
    ib = inst.bbox()      # the rail cell covers the rail band only: look from the die edge inwards
    site = db.Box(26000 if ib.left < 500000 else ib.left, 26000 if ib.bottom < 500000 else ib.bottom,     # 26 um: inside the seal ring
                  3906000 if ib.right > 3432000 else ib.right, 5096000 if ib.top > 4622000 else ib.top)
    if inst.cell.name.startswith('5LM') and (allop & db.Region(site)).is_empty():
        t = inst.trans; inst.delete(); ring.insert(db.CellInstArray(asig.cell_index(), t))
        man['ring_sites_restored'].append(dict(cell=asig.name, at=[ib.left/1000, ib.bottom/1000]))
allop = db.Region(top.begin_shapes_rec(L_PAD)).merged(); mreg = MASKR
man['pad_mask'] = dict(template_openings=len(MASK), not_fully_open=[str(q.bbox()) for q in (mreg-allop).merged().each()], extra_openings=(allop-mreg).merged().count())
man['rail_only_sites'] = [str(i.bbox()) for i in ring.each_inst() if i.cell.name.startswith('5LM')]

# ---------------------------------------------------------------- blocks
for bl in plan['blocks']:
    rect = bl['rect']; W, H = rect[2]-rect[0], rect[3]-rect[1]
    placed = False
    if bl.get('reserve'):
        man['instances'].append(dict(name=bl['name'], master=bl['master'], cell=None, kind='reserve', bbox=rect, in_conn=False)); continue
    for src in bl['cands']:
        c = import_cell(bl['master'], R+'/'+src['gds'], src['cell'])
        others = [o['rect'] for o in plan['blocks'] if o is not bl]+[r for q in plan['pads'] for r in q['rects']]
        tr, how = fit_trans(c, rect, others)
        if tr is None:
            man['notes'].append(f"{bl['name']}: {src['kind']} GDS {src['gds']} does not match its rectangle ({how})")
            imported.pop(bl['master'])     # another candidate (staged) may fit; unused cells are pruned at the end
            c.name = c.name+'__unused'
            continue
        top.insert(db.CellInstArray(c.cell_index(), tr)); record(bl['name'], bl['master'], c, tr, src['kind'], src, how, bl['in_conn'])
        bb = tr*c.bbox(); bl['rect'] = [bb.left/1000, bb.bottom/1000, bb.right/1000, bb.top/1000]
        placed = True; break
    if not placed:
        c = placeholder(bl['master'], W, H, bl['pins'])
        b = c.bbox()         # one placeholder cell per master: later instances with the rectangle turned are rotated
        tr = db.Trans(db.Vector(um(rect[0]), um(rect[1]))) if abs(b.width()/1000-W) < 0.01 else db.Trans(db.Trans.R90, db.Vector(um(rect[0])+b.top, um(rect[1])))
        top.insert(db.CellInstArray(c.cell_index(), tr)); record(bl['name'], bl['master'], c, tr, 'placeholder', None, 'placeholder', bl['in_conn'])
for c in [c for c in ly.top_cells() if c.name != TOP]:
    ly.prune_cell(c.cell_index(), -1)
man['left_out'] = plan['left_out']
man['counts'] = {}
for i in man['instances']: man['counts'][i['kind']] = man['counts'].get(i['kind'], 0)+1
assert [c.name for c in ly.top_cells()] == [TOP], [c.name for c in ly.top_cells()]
ly.write('/run/'+OUT)
json.dump(man, open('/run/skel/manifest.json', 'w'), indent=0)
print('pad mask:', man['pad_mask'], '| snaps:', [(q['pad'], q['shift_um']) for q in man['pad_snap']], '| restored:', man['ring_sites_restored'])
print('instances by kind:', man['counts'], '| ring sites replaced:', len(man['ring_sites_replaced']), '| cells:', ly.cells())
for n in man['notes']: print(' note:', n)
