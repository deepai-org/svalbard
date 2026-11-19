# Stage `place` (tool image, KLayout python):  tool.sh <chip> python3 /asm/kl_place.py
# Inputs  /run/ring.gds, pads.json, masters.json, lef/ (stage abstract), floorplan.json (stage floorplan), the chip conn.
# Outputs /run/placed.gds   ring + pads + every block (real GDS, or a placeholder cell named like the master) + the power grid
#         /run/lef/<placeholder>.lef, /run/lef/pt_pdn.lef   placeholder abstracts; the grid as one macro whose pins are the
#                                                         hook points of the block supply pins
#         /run/design.def, /run/nets.json, /run/place.json (manifest, hook table, unconnectable pins)
# Power grid (spec/power-delivery.md G1/G2/G8): core ring VDD (outer) + VSS (inner), 2 x 14 um on Metal4 + Metal5, following
# the free core boundary round the pad families; mesh of VDD/VSS pairs at 70 um pitch, 10.5 um each (15 % per net and
# layer), Metal4 horizontal, Metal5 vertical, cut where a block draws Metal4/5 (2 um spacing) and over no-route-over blocks;
# Via4 at every same-net crossing; supply pads tied to the ring with Metal2 stubs and Via2/Via3 stacks. Block VDD / VSS pins
# reach the grid through `hook` nets that the router draws (one 20 um piece of the nearest same-net strap per pin).
import json, os, sys, collections, math
import klayout.db as db
sys.path.insert(0, '/asm')
import common as C

CHIP = os.environ['CHIP']; R = '/repo/'
um = lambda v: int(round(v*1000)); fu = lambda v: v/1000.0
inst, ports, masters = C.load(CHIP)
FP = json.load(open('/run/floorplan.json')); PADS = json.load(open('/run/pads.json')); MJ = json.load(open('/run/masters.json'))
ly = db.Layout(); ly.dbu = 0.001; ly.read('/run/ring.gds'); top = ly.cell('pt_chip_top')
LI = {n: ly.layer(*d) for n, d, l, v in C.METALS}; LL = {n: ly.layer(*l) for n, d, l, v in C.METALS}
VIA = {'Via2': ly.layer(38, 0), 'Via3': ly.layer(40, 0), 'Via4': ly.layer(41, 0)}
L_BND = ly.layer(0, 0)
man = dict(chip=CHIP, blocks={}, placeholders={}, notes=[], hooks=[], unconnectable=[], single_pin_nets=[])

# ------------------------------------------------------------------------------------------- centres for pin sides
centre = {}
for n, b in FP['blocks'].items(): r = b['rect']; centre[n] = ((r[0]+r[2])/2, (r[1]+r[3])/2)
for n, v in PADS['pads'].items(): r = v['footprint'][0]; centre[n] = ((r[0]+r[2])/2, (r[1]+r[3])/2)
site_xy = {s: ((v['bbox'][0]+v['bbox'][2])/2, (v['bbox'][1]+v['bbox'][3])/2) for s, v in PADS['io'].items()}
prov = C.provider_pins(inst, C.bond(CHIP))
for i, p, s, iop in prov: centre.setdefault(i, site_xy[s])
nets = collections.defaultdict(list)
for n, i in inst.items():
    for p, (k, net) in i['pins'].items():
        if net != '-': nets[net].append((n, p))
SUP = {'VDD', 'VSS'}

# ------------------------------------------------------------------------------------------- placeholders
def edge_pins(n, w, h, pins):
    """pin side by direction to the other ends of its net; evenly spread per side, ordered along the side"""
    c0 = centre[n]; side = collections.defaultdict(list)
    for p in pins:
        net = inst[n]['pins'].get(p, ('', '-'))[1]
        others = [centre[o] for o, q in nets.get(net, []) if o != n and o in centre] if net not in {'-'} | SUP else []
        if others:
            tx = sum(o[0] for o in others)/len(others); ty = sum(o[1] for o in others)/len(others)
        else: tx, ty = c0[0], c0[1]-1
        dx, dy = (tx-c0[0])/max(w, 1), (ty-c0[1])/max(h, 1)
        s = ('E' if dx > 0 else 'W') if abs(dx) > abs(dy) else ('N' if dy > 0 else 'S')
        side[s].append((p, tx if s in 'NS' else ty))
    out = {}
    cap = {s: int(((w if s in 'NS' else h)-4)/1.68) for s in 'NSEW'}
    order = 'NESW'
    for s in order:                     # overflow to the next side
        while len(side[s]) > cap[s]:
            nxt = order[(order.index(s)+1) % 4]; side[nxt].append(side[s].pop())
    for s, lst in side.items():
        lst.sort(key=lambda t: t[1]); L = (w if s in 'NS' else h); k = len(lst)
        for j, (p, _) in enumerate(lst):
            t = round((2+(L-4)*(j+0.5)/k)/0.01)*0.01        # 10 nm grid (manufacturing grid 5 nm)
            wd = 2.0 if inst[n]['pins'].get(p, ('', ''))[1] in SUP or str(inst[n]['pins'].get(p, ('', ''))[1]).startswith(('RAIL_', 'VREG_', 'VDD_')) else 0.56
            if s == 'N': out[p] = ('Metal2', [t-wd/2, h-1.4, t+wd/2, h])
            if s == 'S': out[p] = ('Metal2', [t-wd/2, 0, t+wd/2, 1.4])
            if s == 'E': out[p] = ('Metal3', [w-1.4, t-wd/2, w, t+wd/2])
            if s == 'W': out[p] = ('Metal3', [0, t-wd/2, 1.4, t+wd/2])
    return out

def write_lef(key, w, h, pins, full_upto):
    Lr = [f'MACRO {key}', '  CLASS BLOCK ;', '  ORIGIN 0 0 ;', f'  FOREIGN {key} 0 0 ;', f'  SIZE {w:.3f} BY {h:.3f} ;', '  SYMMETRY X Y R90 ;']
    for p, (ln, r) in sorted(pins.items()):
        Lr += [f'  PIN {p}', '    DIRECTION INOUT ;', '    USE SIGNAL ;', '    PORT', f'      LAYER {ln} ; RECT {r[0]:.3f} {r[1]:.3f} {r[2]:.3f} {r[3]:.3f} ;', '    END', f'  END {p}']
    Lr.append('  OBS')
    for ln, *_ in C.METALS[:full_upto]:
        reg = db.Region(db.Box(0, 0, um(w), um(h))) - db.Region([db.Box(*[um(v) for v in r]).enlarged(um(0.6), um(0.6)) for p, (l2, r) in pins.items() if l2 == ln])
        Lr.append(f'    LAYER {ln} ;')
        for poly in reg.merged().each():
            for t in poly.decompose_trapezoids(1):
                b = t.bbox(); Lr.append(f'      RECT {fu(b.left):.3f} {fu(b.bottom):.3f} {fu(b.right):.3f} {fu(b.top):.3f} ;')
    Lr += ['  END', f'END {key}', '']
    open(f'/run/lef/{key}.lef', 'w').write('\n'.join(Lr))

ph_cells = {}
def placeholder(n, m, w, h):
    if m in ph_cells: return ph_cells[m]
    w, h = round(w, 2), round(h, 2)
    pins = [] if m == 'decap' else (C.master_pins(masters, m) or list(inst[n]['pins']))
    pp = edge_pins(n, w, h, pins) if pins else {}
    c = ly.create_cell(m); c.shapes(L_BND).insert(db.Box(0, 0, um(w), um(h)))
    c.shapes(L_BND).insert(db.Text('PLACEHOLDER '+m, db.Trans(db.Vector(um(1), um(1)))))
    for p, (ln, r) in pp.items():
        b = db.Box(*[um(v) for v in r]); c.shapes(LI[ln]).insert(b); c.shapes(LL[ln]).insert(db.Text(p, db.Trans(b.center())))
    full = 5 if m in C.NO_OVER else 4 if m == 'pt_digital_macro' else 2 if m == 'decap' else 3     # decap tile: MOS + local wiring on Metal1-2
    write_lef(m, w, h, pp, full)
    ph_cells[m] = (c, w, h, pp)
    MJ[m] = dict(w=w, h=h, origin=[0, 0], pins={p: [v] for p, v in pp.items()}, kind='placeholder', full_obs=full == 5)
    man['placeholders'][m] = dict(w=w, h=h, pins=len(pp), first_instance=n)
    return ph_cells[m]

# ------------------------------------------------------------------------------------------- blocks
imported = {}
def import_cell(m):
    if m in imported: return imported[m]
    src = db.Layout(); src.read(R+MJ[m]['gds']); c = src.cell(MJ[m]['cell'])
    t = ly.create_cell(m); t.copy_tree(c); imported[m] = t
    return t

comps = []          # (name, macro, x, y, orient)
# KLayout rotation/mirror -> DEF orientation (OpenDB: FE = MXR90 = (y, x), FW = MYR90 = (-y, -x))
ORIENT = {'r0': 'N', 'r90': 'W', 'r180': 'S', 'r270': 'E', 'm0': 'FS', 'm90': 'FN', 'm45': 'FE', 'm135': 'FW'}
booked = {}
for n, b in FP['blocks'].items():
    m = b['master']; r = b['rect']; W, H = r[2]-r[0], r[3]-r[1]
    if n not in inst and m != 'decap':          # ledger booking without a conn instance (future block): kept free of wiring below Metal4
        booked[n] = r; continue
    if MJ.get(m, {}).get('gds') and MJ[m].get('w'):
        c = import_cell(m); bb = c.bbox(); kind = MJ[m]['kind']
        w, h = bb.width(), bb.height()
        if abs(fu(w)-W) < 0.2 and abs(fu(h)-H) < 0.2: rot = False
        elif abs(fu(h)-W) < 0.2 and abs(fu(w)-H) < 0.2: rot = True
        else: man['notes'].append(f'{n}: cell {fu(w)} x {fu(h)} vs rect {W:.1f} x {H:.1f}'); rot = b['rot']
    else:
        c, w0, h0, pp = placeholder(n, m, W, H)       # cell drawn in the first instance's orientation
        bb = c.bbox(); rot = not (abs(w0-W) < 0.05 and abs(h0-H) < 0.05); kind = 'placeholder'
    X, Y = um(r[0])//10*10, um(r[1])//10*10          # placement on the 10 nm grid
    tr = db.Trans(db.Trans.R90, db.Vector(X+bb.top, Y-bb.left)) if rot else db.Trans(db.Trans.R0, db.Vector(X-bb.left, Y-bb.bottom))
    top.insert(db.CellInstArray(c.cell_index(), tr))
    got = tr*bb
    man['blocks'][n] = dict(master=m, kind=kind, trans=str(tr), bbox=[fu(got.left), fu(got.bottom), fu(got.right), fu(got.top)], in_conn=b['in_conn'])
    comps.append((n, m, fu(got.left), fu(got.bottom), 'W' if rot else 'N'))
for n, v in PADS['pads'].items():
    t = db.Trans.from_s(v['trans']); m = v['master']; o = MJ[m]['origin']
    # DEF location = lower-left of the placed outline; orientation from the transformation
    orient = ORIENT[str(t).split()[0]]
    comps.append((n, m, v['bbox'][0], v['bbox'][1], orient))
iomap = {}
for s, v in PADS['io'].items():
    m = 'gf180mcu_fd_io__'+v['cell'].split('gf180mcu_fd_io__')[-1] if 'gf180mcu_fd_io__' in v['cell'] else v['cell']
    if m not in MJ or not MJ[m].get('w'): continue
    t = db.Trans.from_s(v['trans'])
    orient = ORIENT[str(t).split()[0]]
    nm = 'io_'+s.replace('[', '_').replace('].pad', '').replace('.pad', '')
    iomap[s] = nm; comps.append((nm, m, v['bbox'][0], v['bbox'][1], orient))

# ------------------------------------------------------------------------------------------- power grid
pdn = ly.create_cell('pt_pdn')
W_, G_ = C.RING_W, C.RING_GAP
inner = db.Region(db.Box(um(C.IO_INNER+2), um(C.IO_INNER+2), um(C.DIE[2]-C.IO_INNER-2), um(C.DIE[3]-C.IO_INNER-2)))
padreg = db.Region([db.Box(*[um(x) for x in r]).enlarged(um(2), um(2)) for v in PADS['pads'].values() for r in v['footprint']]).merged()
free = (inner - padreg).merged()
ring = {'VDD': (free - free.sized(-um(W_))).merged(), 'VSS': (free.sized(-um(W_+G_)) - free.sized(-um(2*W_+G_))).merged()}
reach = {'VDD': free.sized(-um(1)), 'VSS': free.sized(-um(W_+G_+1))}
# what the straps must avoid, per layer
noover = db.Region([db.Box(*[um(x) for x in b['bbox']]).enlarged(um(8), um(8)) for n, b in man['blocks'].items() if b['master'] in C.NO_OVER])
blkmetal = {}
for ln in ('Metal4', 'Metal5'):
    reg = db.Region()
    for i in top.each_inst():
        if i.cell.name in ('retained_provider_ring', 'pt_pdn') or i.cell.name.startswith(('gf180mcu_ws', 'sealring')): continue
        reg += db.Region(i.cell.begin_shapes_rec(LI[ln])).transformed(i.trans)
    blkmetal[ln] = reg.merged().sized(um(2.5)).merged()
digi = man['blocks'].get('digital', {}).get('bbox')
blk4 = blkmetal['Metal4'] + (db.Region(db.Box(*[um(x) for x in digi]).enlarged(um(2), um(2))) if digi else db.Region())
avoid = {'Metal4': (blk4 + noover + padreg.sized(um(3))).merged(), 'Metal5': (blkmetal['Metal5'] + noover + padreg.sized(um(3))).merged()}
PITCH, SW = 70.0, 10.5
core = C.CORE
straps = {('VDD', 'Metal4'): db.Region(), ('VSS', 'Metal4'): db.Region(), ('VDD', 'Metal5'): db.Region(), ('VSS', 'Metal5'): db.Region()}
y = core[1]+10
while y+PITCH/2+SW <= core[3]:
    for net, off in (('VDD', 0.0), ('VSS', PITCH/2)):
        straps[(net, 'Metal4')].insert(db.Box(0, um(y+off), um(C.DIE[2]), um(y+off+SW)))
    y += PITCH
x = core[0]+10
while x+PITCH/2+SW <= core[2]:
    for net, off in (('VDD', 0.0), ('VSS', PITCH/2)):
        straps[(net, 'Metal5')].insert(db.Box(um(x+off), 0, um(x+off+SW), um(C.DIE[3])))
    x += PITCH
for (net, ln), reg in straps.items():
    reg = (reg & reach[net]) - avoid[ln] - (ring['VSS' if net == 'VDD' else 'VDD'] if net == 'VSS' else db.Region())
    keep = db.Region([p for p in reg.merged().each() if p.area() >= um(SW)*um(20)])
    straps[(net, ln)] = keep
# the VSS ring gives way where a VDD strap crosses it on the same layer (the other layer stays continuous)
metal = {}
for net in ('VDD', 'VSS'):
    for ln in ('Metal4', 'Metal5'):
        rg = ring[net]
        if net == 'VSS': rg = rg - straps[('VDD', ln)].sized(um(2))
        rg = rg - (blkmetal[ln] if ln == 'Metal5' else blk4)
        metal[(net, ln)] = (rg + straps[(net, ln)]).merged()
def via_fill(cell, lay, region, inset=0.5):
    vc = ly.cell('via_'+str(lay)) or ly.create_cell('via_'+str(lay))
    if vc.shapes(lay).is_empty(): vc.shapes(lay).insert(db.Box(0, 0, 260, 260))
    n = 0
    for poly in region.merged().sized(-um(inset)).each():
        for t in poly.decompose_trapezoids(1):
            b = t.bbox(); nx = int((b.width()-260)//620)+1; ny = int((b.height()-260)//620)+1
            if b.width() < 260 or b.height() < 260: continue
            ox = b.left+(b.width()-((nx-1)*620+260))//2; oy = b.bottom+(b.height()-((ny-1)*620+260))//2
            cell.insert(db.CellInstArray(vc.cell_index(), db.Trans(db.Vector(ox, oy)), db.Vector(620, 0), db.Vector(0, 620), nx, ny)); n += nx*ny
    return n
nvia = 0
for net in ('VDD', 'VSS'):
    for ln in ('Metal4', 'Metal5'): pdn.shapes(LI[ln]).insert(metal[(net, ln)])
    nvia += via_fill(pdn, VIA['Via4'], metal[(net, 'Metal4')] & metal[(net, 'Metal5')])
# supply pads: Metal2 strips at the inner edge of every dvdd / dvss cell, extended into their ring; Metal3 + Via2/Via3 there
stubs = {'VDD': db.Region(), 'VSS': db.Region()}
rcache = {}
for s, v in PADS['io'].items():
    cn = v['cell']
    if not cn.startswith(('gf180mcu_fd_io__dvdd', 'gf180mcu_fd_io__dvss')): continue
    net = 'VDD' if 'dvdd' in cn else 'VSS'
    c = next(ly.cell(i) for i in ly.cell('retained_provider_ring').each_child_cell() if ly.cell(i).name.split('$')[0] == cn.split('$')[0])
    t = db.Trans.from_s(v['trans'])
    edge = db.Region(c.begin_shapes_rec_touching(LI['Metal2'], db.Box(0, 349000, 75000, 350000))).merged() & db.Region(db.Box(-1000, 340000, 76000, 350000))
    for poly in edge.transformed(t).each():
        b = poly.bbox()
        bx, by, BX, BY = b.left, b.bottom, b.right, b.top
        d = um(C.IO_INNER+2*W_+G_+2)
        if bx < um(500): BX = d
        elif BX > um(C.DIE[2]-500): bx = um(C.DIE[2])-d
        elif by < um(500): BY = d
        else: by = um(C.DIE[3])-d
        stubs[net].insert(db.Box(bx, by, BX, BY))
for net in ('VDD', 'VSS'):
    land = (stubs[net] & metal[(net, 'Metal4')]).merged()
    pdn.shapes(LI['Metal2']).insert(stubs[net]); pdn.shapes(LI['Metal3']).insert(land)
    nvia += via_fill(pdn, VIA['Via2'], land) + via_fill(pdn, VIA['Via3'], land)
    man[f'pad_stubs_{net}'] = stubs[net].count()
top.insert(db.CellInstArray(pdn.cell_index(), db.Trans()))
man['pdn'] = {f'{n}_{l}_mm2': round(metal[(n, l)].area()/1e12, 3) for n, l in metal}
coreA = (core[2]-core[0])*(core[3]-core[1])
man['pdn'].update({f'{n}_{l}_coverage_pct': round(100*(metal[(n, l)] & db.Region(db.Box(*[um(v) for v in core]))).area()/1e6/coreA, 1) for n, l in metal}, vias=nvia)

# ------------------------------------------------------------------------------------------- hooks (block supply pins -> grid)
def pin_shapes_die(n, p):
    """die-coordinate pin rectangles of instance n, pin p (from its abstract)"""
    if n in man['blocks']: m = man['blocks'][n]['master']; t = db.Trans.from_s(man['blocks'][n]['trans'])
    elif n in PADS['pads']: m = PADS['pads'][n]['master']; t = db.Trans.from_s(PADS['pads'][n]['trans'])
    else: return []
    info = MJ.get(m, {}); o = info.get('origin', [0, 0])
    out = []
    for ln, r in info.get('pins', {}).get(p, []):
        b = db.Box(um(r[0]+o[0]), um(r[1]+o[1]), um(r[2]+o[0]), um(r[3]+o[1]))
        out.append((ln, t*b))
    return out
strap_pieces = {}
for net in ('VDD', 'VSS'):
    lst = []
    for ln in ('Metal4', 'Metal5'):
        for poly in straps[(net, ln)].each():
            for tz in poly.decompose_trapezoids(1): lst.append((ln, tz.bbox()))
    strap_pieces[net] = lst
# every strap piece is cut into 20 um slots with 2 um between them; each hook takes the nearest free slot of its net
slots = {}
for net in ('VDD', 'VSS'):
    lst = []
    for ln, b in strap_pieces[net]:
        if min(b.width(), b.height()) < um(5): continue          # slivers of the decomposition are no hook slots
        horiz = b.width() >= b.height(); L = b.width() if horiz else b.height(); n_ = max(1, int(L // um(22)))
        for j in range(n_):
            a0 = (b.left if horiz else b.bottom)+j*um(22)
            cb = db.Box(a0, b.bottom, min(a0+um(20), b.right), b.top) if horiz else db.Box(b.left, a0, b.right, min(a0+um(20), b.top))
            lst.append([ln, cb, False])
    slots[net] = lst
hook_pins = {}; man['digital_ties_not_hooked'] = 0
k = 0
for net in ('VDD', 'VSS'):
    for n, p in nets.get(net, []):
        if n in man['blocks'] and man['blocks'][n]['master'] == 'decap': continue
        if n == 'digital': man['digital_ties_not_hooked'] += 1; continue      # tie-offs belong inside the macro (tie cells)
        sh = pin_shapes_die(n, p)
        if not sh:
            if n in man['blocks'] or n in PADS['pads']: man['unconnectable'].append(dict(inst=n, pin=p, net=net, why='no pin shape (label) in the abstract'))
            continue
        c = sh[0][1].center(); best = None
        for sl in slots[net]:
            if sl[2]: continue
            b = sl[1]; d = max(b.left-c.x, c.x-b.right, 0)+max(b.bottom-c.y, c.y-b.top, 0)
            if best is None or d < best[0]: best = (d, sl)
        if best is None: man['unconnectable'].append(dict(inst=n, pin=p, net=net, why='no free strap slot')); continue
        d, sl = best; sl[2] = True; ln, cb = sl[0], sl[1]
        hn = f'HK{k}'; k += 1; hook_pins[hn] = (ln, cb, net)
        man['hooks'].append(dict(net=f'{net}__{hn}', inst=n, pin=p, layer=ln, piece=[fu(cb.left), fu(cb.bottom), fu(cb.right), fu(cb.top)], dist_um=round(fu(d), 1)))
# grid LEF: hook pieces are pins, everything else of the grid is an obstruction
Lp = ['MACRO pt_pdn', '  CLASS BLOCK ;', '  ORIGIN 0 0 ;', '  FOREIGN pt_pdn 0 0 ;', f'  SIZE {C.DIE[2]:.3f} BY {C.DIE[3]:.3f} ;', '  SYMMETRY X Y ;']
for hn, (ln, cb, net) in hook_pins.items():
    Lp += [f'  PIN {hn}', '    DIRECTION INOUT ;', '    USE SIGNAL ;', '    PORT', f'      LAYER {ln} ; RECT {fu(cb.left):.3f} {fu(cb.bottom):.3f} {fu(cb.right):.3f} {fu(cb.top):.3f} ;', '    END', f'  END {hn}']
Lp.append('  OBS')
for ln in ('Metal2', 'Metal3', 'Metal4', 'Metal5'):
    reg = db.Region(pdn.begin_shapes_rec(LI[ln])).merged() - db.Region([cb for hn, (l2, cb, net) in hook_pins.items() if l2 == ln])
    Lp.append(f'    LAYER {ln} ;')
    for poly in reg.merged().each():
        for tz in poly.decompose_trapezoids(1):
            b = tz.bbox(); Lp.append(f'      RECT {fu(b.left):.3f} {fu(b.bottom):.3f} {fu(b.right):.3f} {fu(b.top):.3f} ;')
Lp += ['  END', 'END pt_pdn', '']
open('/run/lef/pt_pdn.lef', 'w').write('\n'.join(Lp))
comps.append(('pdn', 'pt_pdn', 0.0, 0.0, 'N'))

# ------------------------------------------------------------------------------------------- nets
macro_of = {c[0]: c[1] for c in comps}
def has_pin(i, p): return p in MJ.get(macro_of.get(i, ''), {}).get('pins', {})
def cls(net):
    if net.startswith(('RAIL_', 'VREG_', 'VDD_')): return 'supply'
    u = net.upper()
    if u.startswith(('RF_', 'LNA_', 'LO_', 'BB_', 'MIX', 'RFI', 'RFO', 'TXRF', 'RX_LO', 'TX_LO', 'LOI', 'LOQ')) or 'LO_' in u: return 'rf'
    if u.startswith(('HSRX', 'URX', 'SL_', 'WTX', 'WIRE_TX', 'USB', 'HS_', 'D2H', 'H2D', 'WMON')) or u in ('AUX_CLK_P', 'AUX_CLK_N', 'REF_IN', 'REF_IN_N'): return 'hs'
    if 'CK' in u or 'CLK' in u or u.startswith(('TXPH', 'CDRPH', 'PH', 'FC_SRC')): return 'clock'
    return 'signal'
NETS = {}
for net, users in nets.items():
    if net in SUP: continue
    ends = []
    for n, p in users:
        if inst[n]['master'].startswith(C.PROVIDER): continue
        if has_pin(n, p): ends.append((n, p))
        else: man['unconnectable'].append(dict(inst=n, pin=p, net=net, why='pin not in the abstract (no label on the block edge or in the cell)' if n in macro_of else 'instance not placed'))
    for i, p, s, iop in prov:
        if inst[i]['pins'].get(p, ('', ''))[1] == net and s in iomap and has_pin(iomap[s], iop): ends.append((iomap[s], iop))
    ends = sorted(set(ends))
    if len(ends) >= 2: NETS[net] = dict(ends=ends, cls=cls(net))
    elif users: man['single_pin_nets'].append(net)
for h in man['hooks']:
    NETS[h['net']] = dict(ends=[(h['inst'], h['pin']), ('pdn', h['net'].split('__')[1])], cls='hook')

# ------------------------------------------------------------------------------------------- DEF
D = ['VERSION 5.8 ;', 'DIVIDERCHAR "/" ;', 'BUSBITCHARS "[]" ;', 'DESIGN pt_chip_top ;', 'UNITS DISTANCE MICRONS 1000 ;',
     f'DIEAREA ( 0 0 ) ( {um(C.DIE[2])} {um(C.DIE[3])} ) ;', f'COMPONENTS {len(comps)} ;']
for n, m, x, y, o in comps: D.append(f'- {n} {m} + FIXED ( {um(x)} {um(y)} ) {o} ;')
D += ['END COMPONENTS', f'NETS {len(NETS)} ;']
for net, v in NETS.items():
    D.append(f'- {net} '+' '.join(f'( {i} {p} )' for i, p in v['ends'])+' + USE SIGNAL ;')
D += ['END NETS']
blk = [(n, r) for n, r in list(booked.items())+list(FP['reserves'].items()) if n != 'd2h_strip']
if blk:
    D.append(f'BLOCKAGES {3*len(blk)} ;')
    for n, r in blk:
        for ln in ('Metal1', 'Metal2', 'Metal3'): D.append(f'- LAYER {ln} RECT ( {um(r[0])} {um(r[1])} ) ( {um(r[2])} {um(r[3])} ) ;')
    D.append('END BLOCKAGES')
D += ['END DESIGN', '']
man['booked'] = booked
open('/run/design.def', 'w').write('\n'.join(D))
json.dump({k: dict(cls=v['cls'], ends=v['ends']) for k, v in NETS.items()}, open('/run/nets.json', 'w'), indent=0)
for c in [c for c in ly.top_cells() if c.name != 'pt_chip_top']: ly.prune_cell(c.cell_index(), -1)
ly.write('/run/placed.gds')
json.dump(man, open('/run/place.json', 'w'), indent=0)
cnt = collections.Counter(v['cls'] for v in NETS.values())
print(f"{CHIP}: {len(man['blocks'])} blocks ({len(man['placeholders'])} placeholder masters), {len(comps)} components, nets {dict(cnt)}, "
      f"hooks {len(man['hooks'])}, unconnectable pins {len(man['unconnectable'])}, single-pin nets {len(man['single_pin_nets'])}")
print('pdn', man['pdn'])
for n in man['notes'][:20]: print(' note:', n)
