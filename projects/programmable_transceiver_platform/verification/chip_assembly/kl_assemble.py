# KLayout batch script: full-chip GDS assembly.
#   klayout -b -rd work=/work -rd repo=/repo -r kl_assemble.py
# Inputs: /work/floorplan.json, /work/abstracts.json, /work/mim/decap_mim_unit_raw.gds
# Outputs: /work/pt_chip_top.gds, /work/assembly.json, /work/pdn-shapes.json
import json
import sys
import klayout.db as db

sys.path.insert(0, '/flow')
import inventory as inv   # noqa: E402
from klconn import LAYERS, via_array   # noqa: E402

W = work
R = repo
fp = json.load(open(W+'/floorplan.json'))
ab = json.load(open(W+'/abstracts.json'))
report = dict(ok=False, notes=[], errors=[])
pdn_shapes = []

ly = db.Layout()
ly.dbu = 0.001
ly.read(R+'/'+inv.BASE_RING_GDS)
top = ly.cell(inv.BASE_RING_TOP)
top.name = 'pt_chip_top'
um = lambda v: int(round(v*1000))
def box(x1, y1, x2, y2):
    return db.Box(um(min(x1, x2)), um(min(y1, y2)), um(max(x1, x2)), um(max(y1, y2)))
li = {name: ly.layer(*LAYERS[name]) for name in LAYERS}

# ---------------------------------------------------------------- ring edits
# The packaging-assembly top cell carries its own interconnect between the custom_* and
# attached_tx_* cells (Metal4/Via4/Metal5). Those instances are removed or re-placed
# below, so that wiring is orphaned and lands on whatever the floorplan puts there (it
# bridged isw_debug VDD to VISL). Drop every shape drawn directly in the base top cell.
orphan = {}
for lidx in ly.layer_indexes():
    n = top.shapes(lidx).size()
    if n:
        info = ly.get_info(lidx)
        orphan[f'{info.layer}/{info.datatype}'] = n
        top.shapes(lidx).clear()
report['base_top_orphan_shapes_removed'] = orphan
removed = []
for inst in list(top.each_inst()):
    n = inst.cell.name
    if n.startswith('custom_') or n.startswith('attached_tx_'):
        removed.append(n)
        inst.delete()
ring = ly.cell('retained_provider_ring')
transforms = {e['name']: e for e in json.load(open(R+'/'+inv.PADS+'provider-assembly-inputs/placement-transforms.json'))}
rail_cell = next(c for c in [ly.cell(i) for i in ring.each_child_cell()] if c.name.startswith('5LM_METAL_RAIL'))
# Every site under a custom pad family must carry only the ring rail: provider IO cells there are swapped for the
# 5LM rail cell (sites that already hold the rail, the packaging custom sites, are kept). Generic in the site map,
# so a pad remap in inventory.CUSTOM_PADS needs no change here.
debug_sites = [s for p in inv.CUSTOM_PADS for s in p[4]]
replaced = {}
for site in debug_sites:
    t = transforms[site]
    hit = [i for i in ring.each_inst() if i.trans.disp == db.Point(t['x'], t['y']) and 'fill' not in i.cell.name
           and not i.cell.name.startswith('5LM')]
    assert len(hit) <= 1, (site, [h.cell.name for h in hit])
    if not hit:
        continue
    replaced[site] = hit[0].cell.name
    tr = hit[0].trans
    hit[0].delete()
    ring.insert(db.CellInstArray(rail_cell.cell_index(), tr))
# D2H[0] substitution and RESET_N cell identity at their sites.
site_cells = {}
for site in ('clk_pad', 'rst_n_pad'):
    t = transforms[site]
    site_cells[site] = [i.cell.name for i in ring.each_inst() if abs(i.trans.disp.x-t['x']) <= 1000
                        and abs(i.trans.disp.y-t['y']) <= 1000 and 'fill' not in i.cell.name]
report['site_cells'] = site_cells
report['d2h0_at_clk_pad'] = any(n.startswith('selected_host_output') for n in site_cells['clk_pad'])
report['ring_sites_replaced'] = replaced
report['removed_packaging_cells'] = sorted(set(removed))
for n in sorted(set(removed)):
    c = ly.cell(n)
    if c is not None and c.is_top():
        ly.prune_cell(c.cell_index(), -1)

# ---------------------------------------------------------------- import helper
imported = {}
def import_cell(key, path, cell_name, edit=None, drop=()):
    if key in imported:
        return imported[key]
    src = db.Layout()
    src.read(path)
    for lp in drop:
        i = src.find_layer(*lp)
        if i is not None:
            src.clear_layer(i)
    c = src.cell(cell_name)
    assert c is not None, (path, cell_name)
    if edit:
        c = edit(src, c)
    tgt = ly.create_cell(key)
    tgt.copy_tree(c)
    imported[key] = tgt
    return tgt

# ---------------------------------------------------------------- pad families
def wmon_b(src, c):
    """Single-leg minus bleed and rail shunt, clipped to one site pitch (shared-protection B)."""
    net = next(src.cell(i) for i in c.each_child_cell() if src.cell(i).name.endswith('protection_network'))
    gone = []
    for inst in list(net.each_inst()):
        if inst.cell.name.endswith(('bleed', 'stress_safe_rail_shunt_v2')):
            gone.append(inst.cell.name)
            inst.delete()
    c.flatten(-1, True)
    clip = db.Region(db.Box(-10000, -10000, 205000, 2000000))
    for lidx in src.layer_indexes():
        shapes = c.shapes(lidx)
        texts = [s.text for s in shapes.each() if s.is_text()]
        r = db.Region(shapes) & clip
        shapes.clear()
        shapes.insert(r)
        for tx in texts:
            if clip.bbox().contains(tx.trans.disp):
                shapes.insert(tx)
    report['wmon_b_removed'] = gone
    return c

pads = {}
for name, fam, edge, origin, sites, ports, replaces in inv.CUSTOM_PADS:
    if fam == 'single_leg_b':
        gds, cell, *_ = inv.PAD_FAMILIES['single_leg']
        pc = import_cell('pad_single_leg_b', R+'/'+gds, cell, edit=wmon_b)
    else:
        gds, cell, *_ = inv.PAD_FAMILIES[fam]
        pc = import_cell('pad_'+fam, R+'/'+gds, cell)
    t = transforms[origin]
    if name in inv.MIRRORED_PADS:
        a = t['y']+um(75.0+211.0)
        tr = db.Trans(db.Trans.M135, db.Vector(t['x'], a))
    elif edge == 'west':
        tr = db.Trans(db.Trans.M45, db.Vector(t['x'], t['y']))
    else:
        tr = db.Trans(db.Trans.R90, db.Vector(t['x'], t['y']))
    top.insert(db.CellInstArray(pc.cell_index(), tr))
    bb = tr*pc.bbox()
    # Physical bond map: the P port bonds at the first site unless the cell is mirrored.
    bond = dict(zip(ports, inv.MIRRORED_PADS[name] if name in inv.MIRRORED_PADS else sites))
    pads[name] = dict(cell=pc.name, _trans=tr, trans=str(tr), edge=edge, sites=sites, ports=ports,
                      bond={k: v for k, v in bond.items() if k}, pn_swapped_vs_contract=name in inv.MIRRORED_PADS,
                      bbox=[bb.left/1000, bb.bottom/1000, bb.right/1000, bb.top/1000])

# ---------------------------------------------------------------- masters
placed_cells = {}
for p in fp['placed']:
    m = p['master']
    if m.startswith('attached_tx_'):
        c = import_cell(m, R+'/'+inv.BASE_RING_GDS, m)
    else:
        gds, cell = inv.MASTERS[m][0], inv.MASTERS[m][1]
        c = import_cell(m, R+'/'+gds, cell)
    ox, oy = p['origin']
    # Orientation about the placed rect (lower-left X, Y; cell bbox b): R0, MX (y -> -y),
    # MY (x -> -x), R180. The displacement keeps the rect fixed.
    b = c.bbox()
    X, Y = um(p['rect'][0]), um(p['rect'][1])
    o = p.get('orient') or ('MY' if p.get('mirror_x') else 'R0')
    code, dx, dy = {'R0': (db.Trans.R0, X-b.left, Y-b.bottom), 'MX': (db.Trans.M0, X-b.left, Y+b.top),
                    'MY': (db.Trans.M90, X+b.right, Y-b.bottom), 'R180': (db.Trans.R180, X+b.right, Y+b.top),
                    'R90': (db.Trans.R90, X+b.top, Y-b.left),
                    # M135 = MX after R90 ((x, y) -> (-y, -x)): the mirror image of an R90 cell about
                    # a horizontal axis (I/Q pairs of rotated cells); M45 = (x, y) -> (y, x).
                    'M135': (db.Trans.M135, X+b.top, Y+b.right), 'M45': (db.Trans.M45, X-b.bottom, Y-b.left)}[o]
    tr = db.Trans(code, db.Vector(dx, dy))
    top.insert(db.CellInstArray(c.cell_index(), tr))
    got = tr*c.bbox()
    if max(abs(got.left/1000-p['rect'][0]), abs(got.right/1000-p['rect'][2]),
           abs(got.bottom/1000-p['rect'][1]), abs(got.top/1000-p['rect'][3])) > 0.01:
        report['errors'].append(f"{p['name']}: placed bbox {got} != floorplan rect {p['rect']}")
    placed_cells[p['name']] = m

# Digital macro: abstract outline only (non-mask layer 235/4) + name label.
dig = next(f for f in fp['fixed'] if f['name'] == 'digital')
dcell = ly.create_cell('pt_digital_macro_abstract')
bl = ly.layer(235, 4)
x1, y1, x2, y2 = dig['rect']
dcell.shapes(bl).insert(db.Box(0, 0, um(x2-x1), um(y2-y1)))
dcell.shapes(bl).insert(db.Text('pt_digital_macro', db.Trans(db.Vector(um(10), um(10)))))
top.insert(db.CellInstArray(dcell.cell_index(), db.Trans(db.Vector(um(x1), um(y1)))))

# ---------------------------------------------------------------- MIM decap banks
mim_src = W+'/mim/decap_mim_unit_raw.gds'
unit = import_cell('decap_mim_unit', mim_src, 'decap_mim_unit_raw', drop=[(0, 0)])
# The Magic gencell's Via4 field on the MIM top plate is Magic-clean but violates the KLayout deck's MIMTM.9
# (0.5 um spacing for a sea of vias on the top plate). Re-array every cut field inside its own extent at 0.76 um.
from klconn import MIM_TOP_PITCH
_v4 = db.Region(unit.shapes(li['V4'])).merged()
unit.shapes(li['V4']).clear()
_fields = _v4.sized(um(0.2)).merged()          # one polygon per original cut field
report['decap_unit_v4_fields'] = _fields.count()
for _f in _fields.each():
    _bb = _f.bbox()
    via_array(unit, li, 'V4', db.Box(_bb.left+um(0.2), _bb.bottom+um(0.2), _bb.right-um(0.2), _bb.top-um(0.2)),
              enc=0.0, pitch=MIM_TOP_PITCH)
ub = unit.bbox()
P = inv.MIM_PITCH_UM
bank_info = []
mos_info = []
_tile = None
for d in fp['decaps']:
    if d.get('kind') == 'mos':
        # v4 MOS decap tile rows (P5 pt_decap_tile, 40 x 40 um, Metal1/2 rails): odd rows mirrored about x so the
        # abutting rows share a rail. PDN hookup (Metal1 rails -> core grid straps) is a routing-step item.
        if _tile is None:
            _tile = import_cell('decap_tile', R+'/'+inv.MASTERS['decap_tile'][0], inv.MASTERS['decap_tile'][1])
        x0, y0 = um(d['rect'][0]), um(d['rect'][1])
        t = db.Trans(db.Trans.M0, db.Vector(x0, y0+um(40.0))) if d.get('mirror') else db.Trans(db.Vector(x0, y0))
        top.insert(db.CellInstArray(_tile.cell_index(), t, db.Vector(um(40.0), 0), db.Vector(0, um(40.0)), d['cols'], 1))
        mos_info.append(dict(name=d['name'], tiles=d['cols'], capacitance_f=d['capacitance_f'], pdn_connected=False))
        continue
    cell = ly.create_cell(d['name'])
    B = 12.0     # collector width (floorplan.DECAP_BUS_UM)
    x0, y0 = d['rect'][0]+B, d['rect'][1]+B
    cx0 = x0+inv.MIM_UNIT_UM/2.0+1.2
    cy0 = y0+inv.MIM_UNIT_UM/2.0+0.6
    n = 0
    centers = []
    for r in range(d['rows']):
        for c in range(d['cols']):
            if n >= d['units']:
                break
            cx, cy = cx0+c*P, cy0+r*P
            cell.insert(db.CellInstArray(unit.cell_index(), db.Trans(db.Vector(um(cx), um(cy)))))
            centers.append((cx, cy))
            n += 1
    # bridges: M4 (bottom plates) in the lower half, M5 (top plates) in the upper half
    cs = set(centers)
    for (cx, cy) in centers:
        if (cx+P, cy) in cs:
            cell.shapes(li['M4']).insert(box(cx+50, cy-45, cx+P-50, cy-5))
            cell.shapes(li['M5']).insert(box(cx+49, cy+5, cx+P-49, cy+45))
        if (cx, cy+P) in cs:
            cell.shapes(li['M4']).insert(box(cx-45, cy+50, cx-5, cy+P-50))
            cell.shapes(li['M5']).insert(box(cx+5, cy+49, cx+45, cy+P-49))
    # collectors: M4 (VSS) on the bottom edge row, M5 (supply) on the top edge row
    xs = [c[0] for c in centers]; ys = [c[1] for c in centers]
    left, right = min(xs)-50, max(xs)+50
    bot_row = [c for c in centers if c[1] == min(ys)]
    top_row = [c for c in centers if c[1] == max(ys)]
    cell.shapes(li['M4']).insert(box(left, min(ys)-50-B+1, right, min(ys)-49))
    for (cx, cy) in bot_row:
        cell.shapes(li['M4']).insert(box(cx-45, cy-50.5, cx-5, cy-49))
    cell.shapes(li['M5']).insert(box(left, max(ys)+49, right, max(ys)+50+B-1))
    for (cx, cy) in top_row:
        cell.shapes(li['M5']).insert(box(cx+5, cy+49, cx+45, cy+50.2))
    vdd_net = 'VDD' if d['island'] == 'core' else 'RAIL_'+d['island']
    cell.shapes(ly.layer(81, 10)).insert(db.Text(vdd_net, db.Trans(db.Vector(um(left+5), um(max(ys)+52)))))
    cell.shapes(ly.layer(46, 10)).insert(db.Text('VSS', db.Trans(db.Vector(um(left+5), um(min(ys)-52)))))
    fib = None
    if d.get('pool'):
        # FIB-cuttable strap: 10 um x 20 um Metal5 neck from the bank collector to its landing pad.
        sw, sl = inv.FIB_STRAP_UM
        mx = (left+right)/2
        cell.shapes(li['M5']).insert(box(mx-sw/2, max(ys)+50+B-1, mx+sw/2, max(ys)+50+B-1+sl))
        cell.shapes(li['M5']).insert(box(mx-20, max(ys)+50+B-1+sl, mx+20, max(ys)+50+B-1+sl+20))
        cell.shapes(ly.layer(81, 10)).insert(db.Text('VDD', db.Trans(db.Vector(um(mx), um(max(ys)+50+B+sl+9)))))
        fib = [mx-sw/2, max(ys)+50+B-1, mx+sw/2, max(ys)+50+B-1+sl]
    top.insert(db.CellInstArray(cell.cell_index(), db.Trans()))
    bank_info.append(dict(name=d['name'], units=n, net=vdd_net, fib_strap=fib, capacitance_f=d['capacitance_f']))
report['decap'] = dict(banks=bank_info, mos_rows=mos_info, unit_bbox_um=[v*0.001 for v in (ub.left, ub.bottom, ub.right, ub.top)])

# ---------------------------------------------------------------- core ring
# VSS outer (depth 380-405 um), VDD inner (411-436 um) from each die edge; Metal3 on the
# north/south sides, Metal4 on east/west; cut wherever the band meets foreign metal of
# the same layer (custom pad families cross it); fragments tie to the supply pads.
pdn = ly.create_cell('pt_pdn')
top.insert(db.CellInstArray(pdn.cell_index(), db.Trans()))
D1, D2 = 3932.0, 5122.0
ring_def = {'VSS': (380.0, 405.0), 'VDD': (411.0, 436.0)}
def side_box(side, a, b, lo, hi):
    if side == 'south':
        return box(lo, a, hi, b)
    if side == 'north':
        return box(lo, D2-b, hi, D2-a)
    if side == 'west':
        return box(a, lo, b, hi)
    return box(D1-b, lo, D1-a, hi)
foreign = {}
for lname in ('M2', 'M3', 'M4'):
    foreign[lname] = db.Region(top.begin_shapes_rec(li[lname])).merged()
ring_frag = []
grp_n = 0
for side in ('south', 'north', 'west', 'east'):
    lname = 'M3' if side in ('south', 'north') else 'M4'
    for net, (a, b) in ring_def.items():
        lo, hi = (381.0, D1-381.0) if side in ('south', 'north') else (381.0, D2-381.0)
        band = db.Region(side_box(side, a, b, lo, hi))
        cut = band - foreign[lname].sized(um(3.0))
        # A cut polygon is not a box when foreign metal lies inside the band (notch or
        # hole); its bbox would refill the gap and short into the pad cell. Decompose
        # each polygon into rectangles; rectangles of one polygon form one group.
        horiz = side in ('south', 'north')
        for poly in cut.each():
            pb = poly.bbox()
            if max(pb.width(), pb.height()) < um(30):
                continue
            pieces = db.Region(poly).decompose_trapezoids_to_region(db.Polygon.TD_htrapezoids if not horiz
                                                                    else db.Polygon.TD_vtrapezoids)
            grp_n += 1
            for piece in pieces.each():
                bb = piece.bbox()
                assert piece.is_box(), str(piece)
                if min(bb.width(), bb.height()) < um(2.0):
                    continue
                ring_frag.append(dict(side=side, net=net, layer=lname, box=bb, grp=grp_n))
# Supply-pad stubs: Metal2 from each dvdd/dvss core-side pin to its ring, via stack to the ring layer.
lef_pins = {'gf180mcu_fd_io__dvdd': ('VDD', [(1.36, 10.86), (13.76, 24.01), (25.61, 35.86), (39.14, 49.39), (50.99, 61.24), (64.14, 73.64)]),
            'gf180mcu_fd_io__dvss': ('VSS', [(1.36, 10.86), (13.76, 24.01), (25.61, 35.86), (39.14, 49.39), (50.99, 61.24), (64.14, 73.64)])}
pad_links = []
ring_used = set()
for inst in ring.each_inst():
    base = inst.cell.name.split('$')[0]
    if base not in lef_pins:
        continue
    net, spans = lef_pins[base]
    a, b = ring_def[net]
    tr = inst.dcplx_trans
    for (s0, s1) in spans:
        pin = tr*db.DBox(s0, 345.4, s1, 350.0)     # local pin rect at the cell's core edge
        # stub to the far edge of the ring band of this net
        if abs(pin.top-376.0) < 1.0:                 # south
            stub = db.DBox(pin.left, pin.bottom, pin.right, b)
            side = 'south'
        elif abs(pin.bottom-(D2-376.0)) < 1.0:       # north
            stub = db.DBox(pin.left, D2-b, pin.right, pin.top)
            side = 'north'
        elif abs(pin.right-376.0) < 1.0:             # west
            stub = db.DBox(pin.left, pin.bottom, b, pin.top)
            side = 'west'
        else:                                         # east
            stub = db.DBox(D1-b, pin.bottom, pin.right, pin.top)
            side = 'east'
        target = [f for f in ring_frag if f['side'] == side and f['net'] == net and
                  f['box'].overlaps(box(stub.left, stub.bottom, stub.right, stub.top))]
        if not target:
            continue
        # the stub must not touch the other ring's band on Metal2 conflicts (none: rings are M3/M4)
        pdn.shapes(li['M2']).insert(box(stub.left, stub.bottom, stub.right, stub.top))
        lname = target[0]['layer']
        if side in ('south', 'north'):
            yb = (a, b)
            vb = box(stub.left, yb[0] if side == 'south' else D2-yb[1], stub.right, yb[1] if side == 'south' else D2-yb[0])
        else:
            vb = box(a if side == 'west' else D1-b, stub.bottom, b if side == 'west' else D1-a, stub.top)
        via_array(pdn, li, 'V2', vb)
        if lname == 'M4':
            pdn.shapes(li['M3']).insert(vb)
            via_array(pdn, li, 'V3', vb)
        for f in target:
            ring_used.add(id(f))
        pad_links.append(dict(pad=inst.cell.name, net=net, side=side))
# Corner joins: same-net Metal3 (N/S) and Metal4 (E/W) fragments overlap at the corners.
parent = {id(f): id(f) for f in ring_frag}
def find(k):
    while parent[k] != k:
        parent[k] = parent[parent[k]]
        k = parent[k]
    return k
corner_vias = 0
for i, f in enumerate(ring_frag):
    for g in ring_frag[i+1:]:
        if f['net'] != g['net']:
            continue
        if f['layer'] != g['layer'] and f['box'].overlaps(g['box']):
            ov = f['box'] & g['box']
            corner_vias += via_array(pdn, li, 'V3', ov)
            parent[find(id(f))] = find(id(g))
        elif f['layer'] == g['layer'] and f['box'].touches(g['box']) and not (f['box'] & g['box']).empty() \
                and max((f['box'] & g['box']).width(), (f['box'] & g['box']).height()) >= um(2.0):
            # same-layer pieces of one decomposed band that share an edge of >= 2 um
            parent[find(id(f))] = find(id(g))
tied_roots = {find(k) for k in ring_used}
ring_used = {id(f) for f in ring_frag if find(id(f)) in tied_roots}
kept = 0
for f in ring_frag:
    if id(f) in ring_used:
        pdn.shapes(li[f['layer']]).insert(f['box'])
        pdn.shapes(ly.layer(LAYERS[f['layer']][0], 10)).insert(db.Text(f['net'], db.Trans(f['box'].center())))
        kept += 1
        pdn_shapes.append(dict(rect=[v*0.001 for v in (f['box'].left, f['box'].bottom, f['box'].right, f['box'].top)],
                               color='#000' if f['net'] == 'VSS' else '#c00', opacity=.9))
report['core_ring'] = dict(corner_via_cuts=corner_vias, fragments=len(ring_frag), kept_tied_to_supply_pads=kept,
                           dropped_untied=len(ring_frag)-kept, pad_stubs=len(pad_links))

# ---------------------------------------------------------------- RESET_N weak pull-down
# in_c at rst_n_pad: PD (Metal2, local x 10.33-10.71) -> VDD ring, PU (5.965-6.345) -> VSS ring.
rst = transforms['rst_n_pad']
ox = rst['x']/1000.0
ties = {}
for pin, (p0, p1), net in (('PD', (10.33, 10.71), 'VDD'), ('PU', (5.965, 6.345), 'VSS')):
    a, b = ring_def[net]
    frag = [f for f in ring_frag if f['side'] == 'south' and f['net'] == net and id(f) in ring_used
            and f['box'].left <= um(ox+p0) and f['box'].right >= um(ox+p1)]
    if not frag:
        ties[pin] = 'no ring fragment over the pin'
        continue
    pdn.shapes(li['M2']).insert(box(ox+p0, 356.0, ox+p1, (a+b)/2+0.45))
    pad = box(ox+(p0+p1)/2-0.45, (a+b)/2-0.45, ox+(p0+p1)/2+0.45, (a+b)/2+0.45)
    pdn.shapes(li['M2']).insert(pad)
    via_array(pdn, li, 'V2', pad, enc=0.3)
    ties[pin] = net
report['reset_n_ties'] = ties

# ---------------------------------------------------------------- island switch straps
# Each isw has VDD (top) and VISL (lower) Metal4 edge bars labelled at four points.
# Metal5 straps (20 um) at every labelled point: VISL straps run down to an island
# edge bar below the switch, VDD straps up to a supply bar above it.
strap_report = {}
for p in fp['placed']:
    if not p['master'].startswith('isw_'):
        continue
    a = ab[p['master']]
    ox, oy = p['origin']
    pts = {'VDD': [], 'VISL': []}
    for lab in a['labels']:
        if lab['text'] in pts and 'rect' in lab:
            pts[lab['text']].append((lab['x']+ox, lab['y']+oy, lab['rect']))
    r = p['rect']
    res = {}
    for net, below in (('VISL', True), ('VDD', False)):
        xs = sorted(pts[net])
        bar_y = (r[1]-30.0, r[1]-10.0) if below else (r[3]+10.0, r[3]+30.0)
        for (x, y, rect) in xs:
            yb = (rect[1]+oy, rect[3]+oy)
            s = box(x-10, bar_y[0] if below else yb[0], x+10, yb[1] if below else bar_y[1])
            # No Via4: the strap lands on the switch's own Metal5 comb, which already joins its Metal4 bar.
            # (Round 2 dropped a 20 um Via4 array here on top of the cell's own cuts: ~24k V4.1/V4.2 per switch.)
            pdn.shapes(li['M5']).insert(s)
        if xs:
            pdn.shapes(li['M5']).insert(box(min(v[0] for v in xs)-10, bar_y[0], max(v[0] for v in xs)+10, bar_y[1]))
            lab = 'RAIL_'+p['island'] if net == 'VISL' else 'VDD'
            pdn.shapes(ly.layer(81, 10)).insert(db.Text(lab, db.Trans(db.Vector(um(xs[0][0]), um(sum(bar_y)/2)))))
            pdn_shapes.append(dict(rect=[min(v[0] for v in xs)-10, bar_y[0], max(v[0] for v in xs)+10, bar_y[1]],
                                   color='#c00' if net == 'VDD' else '#06c'))
        res[net] = len(xs)
    strap_report[p['name']] = res
report['island_strapping'] = strap_report

# ---------------------------------------------------------------- shared debug buses
bus_report = {}
for a_name, b_name in inv.SHARED_PROTECTION:
    A, Bp = pads[a_name], pads[b_name]
    from klconn import build_bus
    res = build_bus(ly, top, pdn, li, A, Bp, inv.BUS_WIDTH_UM)
    bus_report[f'{a_name}+{b_name}'] = res
    for s in res.get('shapes', []):
        pdn_shapes.append(dict(rect=s, color='#0a0'))
report['debug_buses'] = bus_report

ly.cleanup()
ly.write(W+'/pt_chip_top.gds')
report['top_cells'] = [c.name for c in ly.top_cells()]
report['pads'] = {k: {kk: vv for kk, vv in v.items() if kk != '_trans'} for k, v in pads.items()}
report['placed_instances'] = len(placed_cells)
report['bond_map'] = {port: site for v in pads.values() for port, site in v['bond'].items()}
report['ok'] = (len(report['top_cells']) == 1 and not report['errors'] and report['d2h0_at_clk_pad'] and
                all(v == 'VDD' or v == 'VSS' for v in ties.values()) and
                all(r.get('ok') for r in bus_report.values()))
json.dump(report, open(W+'/assembly.json', 'w'), indent=1, default=str)
json.dump(pdn_shapes, open(W+'/pdn-shapes.json', 'w'))
print('ASSEMBLY', report['ok'])
