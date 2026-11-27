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
import island_trunks as TRK

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
PSITES = C.provider_sites(inst, C.bond(CHIP)) if C.KH_CONN else []      # provider cell per bond site, every core pin on a net or a VDD / VSS tie
for r_ in PSITES: centre.setdefault(r_['inst'], site_xy[r_['site']])
prov = [] if C.KH_CONN else C.provider_pins(inst, C.bond(CHIP))
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
# KLayout rotation/mirror -> DEF orientation
ORIENT = {'r0': 'N', 'r90': 'W', 'r180': 'S', 'r270': 'E', 'm0': 'FS', 'm90': 'FN', 'm45': 'FW', 'm135': 'FE'}   # checked in OpenDB: FW = (y, x)
ORIENT_INV = {v: k for k, v in ORIENT.items()}
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
    o_ = b.get('orient')       # floorplan plan (PLAN_FP=1): any DEF orientation of a real cell; else R0 / R90 from the outline
    if o_ and kind != 'placeholder':
        t0 = db.Trans.from_s(ORIENT_INV[o_] + ' 0,0'); g0 = t0*bb
        tr = db.Trans(db.Vector(X-g0.left, Y-g0.bottom))*t0
        if abs(fu(g0.width())-W) > 0.2 or abs(fu(g0.height())-H) > 0.2: man['notes'].append(f'{n}: orient {o_} gives {fu(g0.width())} x {fu(g0.height())} vs rect {W:.1f} x {H:.1f}')
    else:
        o_ = 'W' if rot else 'N'
        tr = db.Trans(db.Trans.R90, db.Vector(X+bb.top, Y-bb.left)) if rot else db.Trans(db.Trans.R0, db.Vector(X-bb.left, Y-bb.bottom))
    top.insert(db.CellInstArray(c.cell_index(), tr))
    got = tr*bb
    man['blocks'][n] = dict(master=m, kind=kind, trans=str(tr), bbox=[fu(got.left), fu(got.bottom), fu(got.right), fu(got.top)], in_conn=b['in_conn'])
    comps.append((n, m, fu(got.left), fu(got.bottom), o_))
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
def pin_shapes_die0(n, p):
    m = man['blocks'][n]['master']; t = db.Trans.from_s(man['blocks'][n]['trans']); info = MJ.get(m, {}); o = info.get('origin', [0, 0])
    return [(ln, t*db.Box(um(r[0]+o[0]), um(r[1]+o[1]), um(r[2]+o[0]), um(r[3]+o[1]))) for ln, r in info.get('pins', {}).get(p, [])]
# signal-pin windows: the grid's Metal4 keeps 3 um off every block signal pin on Metal1-3, and its Metal5 off every signal
# pin on Metal4, so the router can step up out of the pin (CHAR_RN_LNA / RAIL_rf_rx shorted into the Metal4 grid over
# atb_leaf NODE pins, 2026-11-24)
_pinwin = {'Metal4': db.Region(), 'Metal5': db.Region()}
for net_, users_ in (nets.items() if C.PIN_WINDOWS.get(CHIP) else []):
    if net_ in ('VDD', 'VSS'): continue
    for n_, p_ in users_:
        if n_ not in man['blocks'] or man['blocks'][n_]['master'] == 'decap': continue
        for ln_, b_ in pin_shapes_die0(n_, p_):
            if ln_ in ('Metal1', 'Metal2', 'Metal3'): _pinwin['Metal4'].insert(b_.enlarged(um(3), um(3)))
            elif ln_ == 'Metal4': _pinwin['Metal5'].insert(b_.enlarged(um(3), um(3)))
            elif ln_ == 'Metal5': _pinwin['Metal4'].insert(b_.enlarged(um(3), um(3)))      # HS_TERM_TRIM[2] into the Metal4 grid under a Metal5 pin
avoid['Metal4'] = (avoid['Metal4'] + _pinwin['Metal4']).merged(); avoid['Metal5'] = (avoid['Metal5'] + _pinwin['Metal5']).merged()
man['pin_windows_mm2'] = {k: round(v.merged().area()/1e12, 4) for k, v in _pinwin.items()}
bars = []          # island supply bars (common.ISLAND_BARS)
for bd in ([] if getattr(C, 'ISLAND_BARS_OFF', False) else C.ISLAND_BARS.get(CHIP, [])):
    reg = db.Region([db.Box(*[um(v) for v in r]) for r in bd['rects']]).merged()
    m4 = db.Region()
    if bd.get('rel') and bd['rel'][0] in man['blocks']:
        bx_, by_ = man['blocks'][bd['rel'][0]]['bbox'][:2]
        bw_ = man['blocks'][bd['rel'][0]]['bbox']
        for ln_, r_ in bd['rel'][1]:
            if isinstance(r_, str) and r_.startswith('pin:'):     # the named pin's shapes + 5 um (any orientation)
                for _l, _b in pin_shapes_die0(bd['rel'][0], r_[4:]): reg += db.Region(_b.enlarged(um(5), um(5)))
                continue
            if r_ == 'bbox': r_ = (0.0, 0.0, bw_[2]-bw_[0], bw_[3]-bw_[1])      # the whole outline, any orientation
            b_ = db.Box(um(bx_+r_[0]), um(by_+r_[1]), um(bx_+r_[2]), um(by_+r_[3]))
            if ln_ == 'Metal5': reg += db.Region(b_)
            else: m4 += db.Region(b_)
        reg = reg.merged()
    # same-net Metal5 of the listed cells (the polygons over their pin, e.g. the isw VISL plate) is joined, not cut
    same = db.Region(); other = db.Region(); cells_ = db.Region()
    for i_, p_ in bd['vias']:
        b_ = man['blocks'][i_]; c_ = ly.cell(b_['master']); t_ = db.Trans.from_s(b_['trans'])
        m5 = db.Region(c_.begin_shapes_rec(LI['Metal5'])).merged().transformed(t_)
        pins_ = db.Region([b for ln, b in pin_shapes_die0(i_, p_)])
        # same net = Metal5 joined to the pin's Metal4 by the cell's own Via4 (an xy overlap alone also catches the other
        # plate where the VDD and VISL fingers interleave over the pin strips: that joined VDD to VISL, 2026-11-23)
        v4 = db.Region(c_.begin_shapes_rec(ly.layer(41, 0))).transformed(t_) & pins_
        m5j = m5.interacting(v4)
        same += m5j; other += m5 - m5j
        cells_ += db.Region(db.Box(*[um(v) for v in b_['bbox']]))
    # cut: every other block's Metal5 (2.5 um), and the listed cells' other-net Metal5 (2.5 um); their same-net Metal5 is joined
    if bd.get('tie_merge') and bd['tie_merge'][0] in man['blocks']:      # same-net Metal5 ties of a block (e.g. the east island column)
        st_ = C.STAGED.get(CHIP, {}).get(bd['tie_merge'][0], {}); rp_ = R+st_.get('report', '')
        if os.path.isfile(rp_):
            ties_ = json.load(open(rp_)).get('ties', {}).get('VDD', {}); bx_, by_ = man['blocks'][bd['tie_merge'][0]]['bbox'][:2]
            for tn_ in bd['tie_merge'][1]:
                if tn_ in ties_: t_ = ties_[tn_]; same += db.Region(db.Box(um(bx_+t_[0]), um(by_+t_[2]), um(bx_+t_[1]), um(by_+t_[3])))
    cut = ((blkmetal['Metal5'] - cells_.sized(um(2.5))) + other.sized(um(2.5))) - same.sized(um(2.5)) + (other.sized(um(2.5)))
    reg = (reg - cut - padreg.sized(um(3)) - (ring['VDD'] + ring['VSS']).sized(um(2.5))).merged() + (same & reg.sized(um(50)))   # never on the core ring
    for i_, p_ in bd['vias']:       # the bar keeps 3 um off the listed cells' other pins (PG / EN joined RAIL_wired_cap, 2026-11-24)
        for pn_ in MJ.get(man['blocks'][i_]['master'], {}).get('pins', {}):
            if pn_ != p_ and pn_ not in ('VDD', 'VSS'):
                for ln_, b_ in pin_shapes_die0(i_, pn_): reg -= db.Region(b_.enlarged(um(3), um(3)))
    reg = (reg - noover).merged()      # never over the no-route-over (RF) blocks
    reg = db.Region([p for p in reg.each() if p.area() > um(20)*um(20)])
    # MSLOT5.1 (Metal5 wider than 30 um must be slotted): 3 x 3 um holes on a 24 um pitch where the bar is wider than 28 um
    bb_ = reg.bbox(); holes_ = db.Region()
    for xh in range(bb_.left + um(12), bb_.right, um(24)):
        for yh in range(bb_.bottom + um(12), bb_.top, um(24)): holes_.insert(db.Box(xh-um(1.5), yh-um(1.5), xh+um(1.5), yh+um(1.5)))
    wide5_ = reg.sized(-um(14)).sized(um(14))           # the parts wider than 28 um
    reg = (reg - (holes_ & wide5_.sized(-um(3)))).merged()
    bars.append(dict(bd, region=reg, m4=m4, merged=not same.is_empty()))
    avoid['Metal4'] = (avoid['Metal4'] + m4.sized(um(2.5))).merged()
    avoid['Metal5'] = (avoid['Metal5'] + reg.sized(um(2.5))).merged()
PITCH, SW = 70.0, float(os.environ.get('STRAP_W', '10.5'))   # G1 15 % nominal; wider per region from strap_widths.json
core = C.CORE
straps = {('VDD', 'Metal4'): db.Region(), ('VSS', 'Metal4'): db.Region(), ('VDD', 'Metal5'): db.Region(), ('VSS', 'Metal5'): db.Region()}
# strap directions (coordinator 2026-11-26, GRID_SWAP=1 default): Metal4 vertical and Metal5 horizontal, along the tech-LEF
# preferred directions, so signal Metal4 / Metal5 run between the straps; GRID_SWAP=0 is the old G1 (Metal4 horizontal)
GRID_SWAP = os.environ.get('GRID_SWAP', '1') == '1'
HL, VL = ('Metal5', 'Metal4') if GRID_SWAP else ('Metal4', 'Metal5')
# horizontal strap phase: with the swap the VDD rows sit on the macro's Metal5 VDD pin rows (DG9-29/30: 5 um pins, 70 um
# per net), so each macro VDD pin strap continues straight into a grid VDD strap
Y0 = core[1]+10
if GRID_SWAP and digi:
    _pv = sorted(b.center().y for ln_, b in pin_shapes_die0('digital', 'VDD') if ln_ == 'Metal5')
    if _pv: Y0 = fu(_pv[0]) - 5.25 - math.floor((fu(_pv[0]) - 5.25 - core[1]) / PITCH) * PITCH
man['grid'] = dict(swap=GRID_SWAP, horizontal=HL, vertical=VL, y0=round(Y0, 3))
# strap width per core region (3 x 3: rows S/M/N, columns W/C/E, as in pdn_regions_pct): strap_widths.json
# {"<chip>": {"default": um, "SE": um, ...}}, set from the power owner's IR/EM answer (PDS-8); the strap axis stays on
# the 70 um pitch, so pieces of different width meet on the region border. The default is STRAP_W (10.5 um).
SWJ = json.load(open('/asm/strap_widths.json')).get(CHIP, {}) if os.path.exists('/asm/strap_widths.json') else {}
SW = float(SWJ.get('default', SW))
def cells3():
    for i, cx in enumerate('WCE'):
        for j, ry in enumerate('SMN'):
            x0 = round(core[0]+(core[2]-core[0])*i/3); x1 = round(core[0]+(core[2]-core[0])*(i+1)/3)      # 1 um grid
            y0 = round(core[1]+(core[3]-core[1])*j/3); y1 = round(core[1]+(core[3]-core[1])*(j+1)/3)
            # outer cells reach the die edge so the straps still meet the core ring
            yield ry+cx, (0 if i == 0 else x0, 0 if j == 0 else y0, C.DIE[2] if i == 2 else x1, C.DIE[3] if j == 2 else y1)
for key, (x0, y0, x1, y1) in cells3():
    w = float(SWJ.get(key, SW)); cell = db.Region(db.Box(um(x0), um(y0), um(x1), um(y1)))
    y = Y0
    while y+PITCH <= core[3]+PITCH/2:
        for net, off in (('VDD', 0.0), ('VSS', PITCH/2)):
            c = y+off+5.25
            if c+w/2 <= core[3]: straps[(net, HL)] += db.Region(db.Box(0, um(c-w/2), um(C.DIE[2]), um(c+w/2))) & cell
        y += PITCH
    x = core[0]+10
    while x+PITCH <= core[2]+PITCH/2:
        for net, off in (('VDD', 0.0), ('VSS', PITCH/2)):
            c = x+off+5.25
            if c+w/2 <= core[2]: straps[(net, VL)] += db.Region(db.Box(um(c-w/2), 0, um(c+w/2), um(C.DIE[3]))) & cell
        x += PITCH
man['strap_widths'] = dict(SWJ, default=SW)
# staged blocks with a strap-width rule over them (ptrim r12: a 16-22 um strap would reach its VDD_WIRE_SW strap)
for n_, v_ in C.STAGED.get(CHIP, {}).items():
    if v_.get('strap_w') and n_ in man['blocks']:
        bb_ = db.Box(*[um(x) for x in man['blocks'][n_]['bbox']]).enlarged(um(3), um(3)); box_ = db.Region(bb_)
        for key_ in list(straps):
            if key_[1] != VL: continue
            keep_ = straps[key_] - box_; thin_ = db.Region()
            for p_ in (straps[key_] & box_).each():
                b_ = p_.bbox(); cx_ = b_.center().x; hw_ = um(v_['strap_w'])//2
                thin_.insert(db.Box(cx_-hw_, b_.bottom, cx_+hw_, b_.top))
            straps[key_] = (keep_ + thin_).merged()
raw_straps = {k: v.dup() for k, v in straps.items()}
for (net, ln), reg in straps.items():
    reg = (reg & reach[net]) - avoid[ln] - (ring['VSS' if net == 'VDD' else 'VDD'] if net == 'VSS' else db.Region())
    keep = db.Region([p for p in reg.merged().each() if p.area() >= um(10.5)*um(20)])
    straps[(net, ln)] = keep
for net_, ln_, r_ in C.GRID_STITCH.get(CHIP, []) if os.environ.get('PLAN_FP') != '1' else []:      # common.GRID_STITCH (for the packer floorplan)
    if GRID_SWAP: ln_ = {'Metal4': 'Metal5', 'Metal5': 'Metal4'}[ln_]      # stitch bars follow the horizontal layer
    st_ = (db.Region(db.Box(*[um(v) for v in r_])) - avoid[ln_]).merged()
    man.setdefault('grid_stitch', []).append(dict(net=net_, layer=ln_, rect=list(r_), kept_um2=round(st_.area()/1e6)))
    straps[(net_, ln_)] = (straps[(net_, ln_)] + db.Region([q for q in st_.each() if q.area() >= um(4)*um(20)])).merged()
# digital macro supply (PDS-25 finding 1): the grid never reached the macro's PDN. Digital's macros carry horizontal Metal5
# VDD / VSS straps as LEF pins (5 um, 70 um pitch per net, Via4 inside the macro; coordinator 2026-11-25): the top level draws
# Metal5 exactly over each such pin and carries it MSTRAP_EXT um out through both macro edges, where Via4 onto the same-net
# Metal4 strap joins the grid (the vertical Metal5 straps give way in that zone). No top-level Via4 over the macro.
# Older macros (vertical Metal4 stripes only): horizontal Metal5 straps on the Metal4 strap tracks with Via4 onto the stripes.
# man['macro_supply'] is the check (place prints MACRO SUPPLY OPEN; run.sh lvs repeats it): LVS by name cannot see it.
MSTRAP_EXT = 30.0
MSTRAP_W = 10.0      # top-level width of a macro supply strap outside the outline (PDS-25)
macro_vias = []
if digi and GRID_SWAP:
    # swapped grid: no top-level grid over the macro (it draws its own Metal4 / Metal5); each macro Metal5 pin strap is drawn
    # at pin width through the outline edge and out to MSTRAP_REACH um, where it meets the vertical Metal4 straps of the same
    # net (Via4 at every crossing). The horizontal Metal5 grid rows are cut in that zone; the VDD rows line up with the VDD pin
    # rows (Y0), so VDD runs on at full width beyond the zone, VSS ends at its last crossing.
    mb_ = db.Box(*[um(v) for v in digi])
    # reach per side: to the farther of the nearest VDD / VSS vertical Metal4 strap that spans the macro rows, plus the via
    # landing; the horizontal grid rows give way only in that zone
    def _reach(side_):
        r_ = 0
        for net in ('VDD', 'VSS'):
            d_ = [ (mb_.left - q.bbox().right) if side_ < 0 else (q.bbox().left - mb_.right) for q in straps[(net, 'Metal4')].each()
                   if q.bbox().bottom <= mb_.bottom and q.bbox().top >= mb_.top - um(20) and ((q.bbox().right < mb_.left) if side_ < 0 else (q.bbox().left > mb_.right))]
            d_ = [d for d in d_ if d >= 0]
            r_ = max(r_, (min(d_) + um(SW) + um(1)) if d_ else um(100))
        return min(r_, um(100))
    REACH_ = {-1: _reach(-1), 1: _reach(1)}
    man['macro_strap_reach_um'] = {str(k): fu(v) for k, v in REACH_.items()}
    MSTRAP_REACH = 100.0
    for side_ in (-1, 1):
        z_ = db.Box(mb_.left-REACH_[side_], mb_.bottom-um(6), mb_.left, mb_.top) if side_ < 0 else db.Box(mb_.right, mb_.bottom-um(6), mb_.right+REACH_[side_], mb_.top)
        for net in ('VDD', 'VSS'): straps[(net, 'Metal5')] = (straps[(net, 'Metal5')] - db.Region(z_).sized(um(0), um(0))).merged()
    for net in ('VDD', 'VSS'): straps[(net, 'Metal5')] = (straps[(net, 'Metal5')] - db.Region(mb_).sized(um(2.5))).merged()
    for net in ('VDD', 'VSS'):
        p5_ = [b for ln_, b in pin_shapes_die0('digital', net) if ln_ == 'Metal5']
        ends_ = []; ext_ = db.Region()
        for b in p5_:
            ne_ = 0
            for side_ in (-1, 1):
                rch_ = REACH_[side_] - (0 if net == 'VDD' else um(6))      # VSS stops 6 um short of the full-width VDD row
                e_ = db.Box(mb_.left-rch_, b.bottom, b.left, b.top) if side_ < 0 else db.Box(b.right, b.bottom, mb_.right+rch_, b.top)
                inside_ = db.Box(mb_.left, b.bottom, b.left, b.top) if side_ < 0 else db.Box(b.right, b.bottom, mb_.right, b.top)
                oth_ = 'VSS' if net == 'VDD' else 'VDD'
                out_ = (db.Region(e_) - db.Region(mb_)) - (avoid['Metal5'] - db.Region(mb_.enlarged(um(3), um(0)))) - ring.get(oth_, db.Region()).sized(um(2))
                # keep the part joined to the outline edge
                out_ = out_.interacting(db.Region(db.Box(mb_.left-um(1), b.bottom, mb_.left, b.top) if side_ < 0 else db.Box(mb_.right, b.bottom, mb_.right+um(1), b.top)))
                hit_ = out_ & straps[(net, 'Metal4')]
                if hit_.is_empty(): man.setdefault('macro_supply_open', []).append([net, side_, fu(b.bottom), 'no same-net Metal4 strap within reach']); continue
                if inside_.width() > 0: ext_ += db.Region(inside_)
                ext_ += out_; ne_ += 1
            ends_.append(ne_)
        straps[(net, 'Metal5')] = (straps[(net, 'Metal5')] + ext_).merged()
        man.setdefault('macro_supply', {})[net] = dict(kind='metal5 pins, swapped grid', stripes=len(p5_), joined=sum(1 for e in ends_ if e == 2),
                                                      one_end=sum(1 for e in ends_ if e == 1), via4=-1)
elif digi:
    mb_ = db.Box(*[um(v) for v in digi]); zone_ = db.Region(mb_.enlarged(um(MSTRAP_EXT), um(3)))
    _m5pins = any(ln_ == 'Metal5' for n_ in ('VDD', 'VSS') for ln_, b in pin_shapes_die0('digital', n_))
    for net in ('VDD', 'VSS'):
        straps[(net, 'Metal5')] = (straps[(net, 'Metal5')] - (db.Region(mb_) if _m5pins else zone_).sized(um(2.5))).merged()
    for net in ('VDD', 'VSS'):
        p5_ = [b for ln_, b in pin_shapes_die0('digital', net) if ln_ == 'Metal5']
        p4_ = db.Region([b for ln_, b in pin_shapes_die0('digital', net) if ln_ == 'Metal4'])
        if p5_:
            # each pin strap runs out on Metal5 to the nearest same-net vertical Metal5 grid strap on either side that spans
            # its height; the other net's vertical straps in between are cut round it (they stay joined by their Via4 onto the
            # Metal4 straps); a block / window in the way leaves that end open (counted)
            ends_ = []; hz_ = db.Region(p5_)
            other_ = 'VSS' if net == 'VDD' else 'VDD'
            o5_ = [b for ln_, b in pin_shapes_die0('digital', other_) if ln_ == 'Metal5']
            for b in p5_:
                ne_ = 0
                for side_ in (-1, 1):
                    best_ = None
                    for q in straps[(net, 'Metal5')].each():
                        qb_ = q.bbox()
                        if qb_.bottom > b.bottom or qb_.top < b.top: continue
                        if side_ < 0 and qb_.right < mb_.left - um(3): d_ = mb_.left - qb_.right
                        elif side_ > 0 and qb_.left > mb_.right + um(3): d_ = qb_.left - mb_.right
                        else: continue
                        if d_ < um(100) and (best_ is None or d_ < best_[0]): best_ = (d_, qb_)
                    if best_ is None: man.setdefault('macro_supply_open', []).append([net, side_, fu(b.bottom), 'no same-net vertical strap within 100 um']); continue
                    qb_ = best_[1]
                    # outside the outline the strap is MSTRAP_W wide, widened away from the nearest other-net pin strap (the
                    # macro's VDD / VSS straps sit 1.7 um apart); inside, the 5 um pin is bridged to the outline at its own width
                    up_ = min((ob.bottom - b.top for ob in o5_ if ob.bottom >= b.top), default=um(1e4)) > min((b.bottom - ob.top for ob in o5_ if ob.top <= b.bottom), default=um(1e4))
                    lo_, hi_ = (b.bottom, max(b.top, b.bottom + um(MSTRAP_W))) if up_ else (min(b.bottom, b.top - um(MSTRAP_W)), b.top)
                    e_ = db.Box(qb_.left, lo_, mb_.left, hi_) if side_ < 0 else db.Box(mb_.right, lo_, qb_.right, hi_)
                    br_ = db.Box(mb_.left, b.bottom, b.left, b.top) if side_ < 0 else db.Box(b.right, b.bottom, mb_.right, b.top)
                    if br_.width() > 0: hz_ += db.Region(br_)
                    if not (db.Region(e_) & (avoid['Metal5'] - db.Region(mb_.enlarged(um(3), um(0))))).is_empty():
                        man.setdefault('macro_supply_open', []).append([net, side_, fu(b.bottom), 'blocked', fu(qb_.left)]); continue
                    hz_ += db.Region(e_); ne_ += 1
                    straps[(other_, 'Metal5')] = (straps[(other_, 'Metal5')] - db.Region(e_).sized(um(1.5))).merged()      # 1.5 um: the macro's own VDD / VSS straps are 1.7 apart
                ends_.append(ne_)
            hz_ = hz_.merged()
            straps[(net, 'Metal5')] = (straps[(net, 'Metal5')] + hz_).merged()
            man.setdefault('macro_supply', {})[net] = dict(kind='metal5 pins', stripes=len(p5_), joined=sum(1 for e in ends_ if e == 2),
                                                          one_end=sum(1 for e in ends_ if e == 1), via4=-1)
        else:
            tr_ = db.Region()
            for poly in raw_straps[(net, 'Metal4')].each():
                b_ = poly.bbox()
                if b_.top < mb_.bottom or b_.bottom > mb_.top: continue
                tr_.insert(db.Box(mb_.left-um(MSTRAP_EXT), b_.bottom, mb_.right+um(MSTRAP_EXT), b_.top))
            tr_ = (tr_.merged() & db.Region(db.Box(mb_.left-um(MSTRAP_EXT), mb_.bottom+um(1), mb_.right+um(MSTRAP_EXT), mb_.top-um(1))))
            tr_ = (tr_ - avoid['Metal5']).merged()        # macro / block Metal5 (2.5 um), no-route-over, pin windows, pads, bars
            hz_ = db.Region([q for q in tr_.each() if q.area() >= um(10)*um(10)])
            straps[(net, 'Metal5')] = (straps[(net, 'Metal5')] + hz_).merged()
            macro_vias.append((net, (p4_ & hz_).merged()))
            man.setdefault('macro_supply', {})[net] = dict(kind='metal4 stripes', stripes=p4_.count(), joined=p4_.interacting((p4_ & hz_).merged().sized(-um(0.4))).count(),
                                                          crossings=(p4_ & hz_).merged().count(), strap_pieces=hz_.count())
# island strap regions (coordinator 2026-11-24: island rails sized for their current, not 1 um routes): inside the box round
# an island's switch and its loads (+40 um), the grid VDD straps become that island's rail (RAIL_<island>, same width,
# Via4 at its own crossings); the loads' rail pins and the switch VISL hook to them like VDD pins hook to the grid. Smaller
# islands claim first; a 3 um gap separates a rail strap from the VDD straps round it. RAIL_wired_tx keeps its bar.
ISL = sorted({n for n in nets if n.startswith('RAIL_')} - {bd['net'] for bd in bars}) if os.environ.get('ISLAND_STRAPS') == '1' else []   # experimental, off: rails fragment (see README)
isl_box = {}
for net in ISL:
    mem = [man['blocks'][n]['bbox'] for n, p in nets[net] if n in man['blocks'] and man['blocks'][n]['master'] != 'decap']
    if len(mem) < 2: continue
    # region = each member's outline + 25 um, joined by 70 um-wide L corridors along a Manhattan minimum spanning tree of the
    # member centres (a 70 um corridor always holds one VDD axis of the 70 um grid pitch per layer, so the rail is continuous)
    cen = [((b[0]+b[2])/2, (b[1]+b[3])/2) for b in mem]
    rg = db.Region([db.Box(um(b[0]-25), um(b[1]-25), um(b[2]+25), um(b[3]+25)) for b in mem])
    done = {0}; rest = set(range(1, len(cen)))
    while rest:
        i_, j_ = min(((i, j) for i in done for j in rest), key=lambda e: abs(cen[e[0]][0]-cen[e[1]][0])+abs(cen[e[0]][1]-cen[e[1]][1]))
        (x1, y1), (x2, y2) = cen[i_], cen[j_]
        rg.insert(db.Box(um(min(x1, x2)-35), um(y1-35), um(max(x1, x2)+35), um(y1+35)))
        rg.insert(db.Box(um(x2-35), um(min(y1, y2)-35), um(x2+35), um(max(y1, y2)+35)))
        done.add(j_); rest.discard(j_)
    isl_box[net] = rg.merged()
claimed = db.Region(); man['island_straps'] = {}
for net in sorted(isl_box, key=lambda n: isl_box[n].area()):
    reg_ = (isl_box[net] - claimed.sized(um(3))) - (ring['VDD'] + ring['VSS']).sized(um(3))
    claimed += reg_
    for ln in ('Metal4', 'Metal5'):
        piece = (straps[('VDD', ln)] & reg_).merged()
        straps[('VDD', ln)] = (straps[('VDD', ln)] - reg_.sized(um(3))).merged()
        straps[(net, ln)] = db.Region([p_ for p_ in piece.each() if p_.area() >= um(10.5)*um(20)])
    bb_ = isl_box[net].bbox(); pieces_ = (straps[(net, 'Metal4')] + straps[(net, 'Metal5')]).merged().count()
    man['island_straps'][net] = dict(box=[fu(bb_.left), fu(bb_.bottom), fu(bb_.right), fu(bb_.top)], area_mm2=round(reg_.area()/1e12, 3), pieces=pieces_,
                                     m4_mm2=round(straps[(net, 'Metal4')].area()/1e12, 4), m5_mm2=round(straps[(net, 'Metal5')].area()/1e12, 4))
GRID_NETS = ['VDD', 'VSS']+[n for n in man['island_straps'] if not (straps[(n, 'Metal4')].is_empty() and straps[(n, 'Metal5')].is_empty())]
# staged blocks with declared grid ties (owner report: ties.VSS chan*): the VSS Metal5 strap in each Metal5-free channel is
# carried onto its tab (the 2.5 um cut is closed there); grid VDD never ties to a block (its VDD is an island rail)
man['tab_ties'] = []
for n, v in C.STAGED.get(CHIP, {}).items():
    if n not in man['blocks'] or not os.path.exists(R+v['report']): continue
    rep = json.load(open(R+v['report'])); x0, y0 = man['blocks'][n]['bbox'][:2]
    for tn, t in rep.get('ties', {}).get('VSS', {}).items():
        if not tn.startswith(('chan', 'grid_tie')): continue      # channel tabs and top-edge landings (WT47)
        tab = db.Region(db.Box(um(x0+t[0]), um(y0+t[2]-3.0), um(x0+t[1]), um(y0+t[3]+3.0)))
        if GRID_SWAP:
            # swapped grid: the tie is a Metal5 run up the block's Metal5-free channel from the tab to the first horizontal
            # VSS Metal5 strap above or below the block; the VDD rows it crosses give way 2 um round it
            bx_ = man['blocks'][n]['bbox']
            run_ = db.Region(db.Box(um(x0+t[0]), um(bx_[1]-PITCH), um(x0+t[1]), um(bx_[3]+PITCH))) - (blkmetal['Metal5'] - tab).sized(um(0))
            run_ = (run_ - straps[('VDD', 'Metal5')].sized(um(2))).interacting(tab)      # never across a VDD row (plan-wired1 touch)
            hit = run_ if not (run_ & straps[('VSS', 'Metal5')]).is_empty() else db.Region()
            if not hit.is_empty():
                straps[('VSS', 'Metal5')] = (straps[('VSS', 'Metal5')] + hit).merged()
        else: hit = raw_straps[('VSS', 'Metal5')] & tab
        if not hit.is_empty() and not GRID_SWAP:
            straps[('VSS', 'Metal5')] = (straps[('VSS', 'Metal5')] + hit).merged()
        man['tab_ties'].append(dict(inst=n, tab=tn, tied=not hit.is_empty(), at=[round(x0+t[0], 2), round(y0+t[2], 2)]))
# the VSS ring gives way where a VDD strap crosses it on the same layer (the other layer stays continuous)
metal = {}
for net in GRID_NETS:
    for ln in ('Metal4', 'Metal5'):
        rg = ring.get(net, db.Region())
        if net == 'VSS': rg = rg - straps[('VDD', ln)].sized(um(2))
        rg = rg - (blkmetal[ln] if ln == 'Metal5' else blk4)
        m_ = (rg + straps[(net, ln)]).merged()
        metal[(net, ln)] = m_.sized(-um(0.6)).sized(um(0.6)).merged()     # no piece narrower than 1.2 um (M4.1 / MT.1)
# dead grid metal (coordinator 2026-11-27): strap pieces of VDD / VSS that reach the core ring through no chain of same-net
# Metal4 / Metal5 overlaps (Via4 sits on every such overlap) are removed, so floating metal cannot hide real opens later
man['grid_dead_mm2'] = {}
for net in ('VDD', 'VSS'):
    m4_, m5_ = metal[(net, 'Metal4')].merged(), metal[(net, 'Metal5')].merged()
    seed_ = ring.get(net, db.Region())
    l4_, l5_ = m4_.overlapping(seed_), m5_.overlapping(seed_)
    while True:
        n4_ = m4_.overlapping(l5_) + l4_; n5_ = m5_.overlapping(l4_) + l5_
        n4_ = m4_.overlapping(n4_); n5_ = m5_.overlapping(n5_)
        if n4_.count() == l4_.count() and n5_.count() == l5_.count(): break
        l4_, l5_ = n4_, n5_
    man['grid_dead_mm2'][net] = dict(Metal4=round((m4_ - l4_).area()/1e12, 4), Metal5=round((m5_ - l5_).area()/1e12, 4),
                                     pieces=(m4_.count() - l4_.count()) + (m5_.count() - l5_.count()))
    metal[(net, 'Metal4')], metal[(net, 'Metal5')] = l4_, l5_
print('grid dead metal removed', man['grid_dead_mm2'])
# self-check: grid metal of different nets must not touch on a layer (a VDD / VSS join in the drawn grid)
man['grid_touch'] = []
for ln in ('Metal4', 'Metal5'):
    for a_, b_ in [(x, y) for i_, x in enumerate(GRID_NETS) for y in GRID_NETS[i_+1:]]:
        t_ = metal[(a_, ln)].interacting(metal[(b_, ln)])
        for p_ in (metal[(a_, ln)] & metal[(b_, ln)].sized(um(0.01))).each():
            b0 = p_.bbox(); man['grid_touch'].append([ln, a_, b_, fu(b0.left), fu(b0.bottom), fu(b0.right), fu(b0.top)])
if man['grid_touch']: print('GRID VDD/VSS TOUCH', len(man['grid_touch']), man['grid_touch'][:8])
GCELL = 8400        # FastRoute gcell (dbu) of the route stage
def via_fill(cell, lay, region, inset=0.5, single=False):
    vc = ly.cell('via_'+str(lay)) or ly.create_cell('via_'+str(lay))
    if vc.shapes(lay).is_empty(): vc.shapes(lay).insert(db.Box(0, 0, 260, 260))
    n = 0
    for poly in region.merged().sized(-um(inset)).each():
        for t in poly.decompose_trapezoids(1):
            # cuts on one global 620 nm lattice, so arrays of neighbouring rectangles keep the array spacing (V4.2a)
            b = t.bbox(); ox = -(-b.left//620)*620; oy = -(-b.bottom//620)*620
            nx = (b.right-260-ox)//620+1; ny = (b.top-260-oy)//620+1
            if nx < 1 or ny < 1:
                if single and b.width() >= 260 and b.height() >= 260:       # narrow landing: one centred row of cuts at 620 nm pitch
                    horiz = b.width() >= b.height(); L_ = b.width() if horiz else b.height(); k_ = max(1, (L_-260)//620+1)
                    s0 = ((b.left if horiz else b.bottom) + (L_-260-(k_-1)*620)//2)//5*5
                    c0 = ((b.bottom+b.top-260)//2 if horiz else (b.left+b.right-260)//2)//5*5
                    v_ = db.Vector(620, 0) if horiz else db.Vector(0, 620)
                    org_ = db.Vector(s0, c0) if horiz else db.Vector(c0, s0)
                    cell.insert(db.CellInstArray(vc.cell_index(), db.Trans(org_), v_, db.Vector(0, 620) if horiz else db.Vector(620, 0), k_, 1)); n += k_
                continue
            cell.insert(db.CellInstArray(vc.cell_index(), db.Trans(db.Vector(ox, oy)), db.Vector(620, 0), db.Vector(0, 620), nx, ny)); n += nx*ny
    return n
# Via4 from the grid VSS Metal5 straps onto a staged block's declared VSS Metal4 pin (ptrim r12 VSS strap, full height)
for n_, v_ in C.STAGED.get(CHIP, {}).items():
    if v_.get('via_pin') and n_ in man['blocks']:
        b_ = man['blocks'][n_]; t_ = db.Trans.from_s(b_['trans']); info_ = MJ.get(b_['master'], {}); o_ = info_.get('origin', [0, 0])
        pr_ = db.Region([t_*db.Box(um(r[0]+o_[0]), um(r[1]+o_[1]), um(r[2]+o_[0]), um(r[3]+o_[1])) for ln, r in info_.get('pins', {}).get(v_['via_pin'], []) if ln == 'Metal4'])
        land_ = pr_ & straps[('VSS', 'Metal5')]
        man.setdefault('staged_vias', {})[n_] = via_fill(pdn, VIA['Via4'], land_, inset=0.3) if not land_.is_empty() else 0
nvia = 0
for net in GRID_NETS:
    for ln in ('Metal4', 'Metal5'): pdn.shapes(LI[ln]).insert(metal[(net, ln)])
    nvia += via_fill(pdn, VIA['Via4'], metal[(net, 'Metal4')] & metal[(net, 'Metal5')])
for net_, land_ in macro_vias:       # Via4 from the horizontal Metal5 straps onto the macro's own Metal4 stripes
    man['macro_supply'][net_]['via4'] = via_fill(pdn, VIA['Via4'], land_ & metal[(net_, 'Metal5')], inset=0.2)
    nvia += man['macro_supply'][net_]['via4']
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
    land = land.sized(-um(0.5)).sized(um(0.5)).merged()      # no Metal3 sliver where a strap cut ends on the stub (M3.1, swapped grid)
    pdn.shapes(LI['Metal2']).insert(stubs[net]); pdn.shapes(LI['Metal3']).insert(land)
    nvia += via_fill(pdn, VIA['Via2'], land) + via_fill(pdn, VIA['Via3'], land)
    man[f'pad_stubs_{net}'] = stubs[net].count()
top.insert(db.CellInstArray(pdn.cell_index(), db.Trans()))
man['pdn'] = {f'{n}_{l}_mm2': round(metal[(n, l)].area()/1e12, 3) for n, l in metal}
coreA = (core[2]-core[0])*(core[3]-core[1])
# coverage per region (3 x 3 over the core, columns W/C/E, rows S/M/N) for the power owner's model (asm9_drawn.py)
reg = {}
for i, cx in enumerate('WCE'):
    for j, ry in enumerate('SMN'):
        x0 = core[0]+(core[2]-core[0])*i/3; x1 = core[0]+(core[2]-core[0])*(i+1)/3
        y0 = core[1]+(core[3]-core[1])*j/3; y1 = core[1]+(core[3]-core[1])*(j+1)/3
        bx = db.Region(db.Box(um(x0), um(y0), um(x1), um(y1))); A_ = (x1-x0)*(y1-y0)
        reg[ry+cx] = {f'{n}_{l}': round(100*(metal[(n, l)] & bx).area()/1e6/A_, 1) for n, l in metal}
man['pdn_regions_pct'] = reg
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
for net in GRID_NETS:
    lst = []
    for ln in ('Metal4', 'Metal5'):
        for poly in straps[(net, ln)].each():
            for tz in poly.decompose_trapezoids(1): lst.append((ln, tz.bbox()))
    strap_pieces[net] = lst
# every strap piece is cut into 20 um slots with 2 um between them; each hook takes the nearest free slot of its net
# grid pieces cut off from the core ring (blocks round them cut every strap: the pt_lo_lf VSS hook landed on a floating
# 929-via VSS island, 2026-11-24) carry no hook slots: keep only metal joined to the ring through same-net Metal4/Metal5
# overlaps (Via4 sits at every same-net crossing)
live = {}
for net in [n_ for n_ in GRID_NETS if n_ in ring]:
    m4_ = metal.get((net, 'Metal4'), db.Region()).merged(); m5_ = metal.get((net, 'Metal5'), db.Region()).merged()
    seed = ring.get(net, db.Region())
    # Metal4 and Metal5 count as joined only where their overlap is large enough for the Via4 lattice to place a cut
    # (a thin overlap gets none: two pt_rf VSS hooks landed on such an island, 2026-11-24)
    cx_ = (m4_ & m5_).merged().sized(-um(0.75)).sized(um(0.75))
    keep4 = m4_.interacting(seed); keep5 = m5_.interacting(seed)
    while True:
        n4 = m4_.interacting(cx_.interacting(keep5 + seed)) + m4_.interacting(seed); n5 = m5_.interacting(cx_.interacting(keep4 + seed)) + m5_.interacting(seed)
        n4 = n4.merged(); n5 = n5.merged()
        if n4.count() == keep4.count() and n5.count() == keep5.count(): break
        keep4, keep5 = n4, n5
    live[net] = {'Metal4': keep4, 'Metal5': keep5}
    man.setdefault('grid_floating', {})[net] = dict(m4=m4_.count()-keep4.count(), m5=m5_.count()-keep5.count(), m4_total=m4_.count(), m5_total=m5_.count(), m4_float_mm2=round((m4_-keep4).area()/1e12, 4), m5_float_mm2=round((m5_-keep5).area()/1e12, 4))
    man.setdefault('grid_floating_big', {})[net] = [[ln_, [fu(q.bbox().left), fu(q.bbox().bottom), fu(q.bbox().right), fu(q.bbox().top)], round(q.area()/1e6)] for ln_, r_ in (('Metal4', m4_-keep4), ('Metal5', m5_-keep5)) for q in r_.merged().each() if q.area() >= um(50)*um(50)]
_blkreg = db.Region([db.Box(*[um(v) for v in b_['bbox']]) for n_, b_ in man['blocks'].items() if b_['master'] != 'decap']).merged()
slots = {}
for net in GRID_NETS:
    lst = []
    # slots are cut from the drawn, ring-joined metal (the uncut strap pieces gave pdn pins where blocks / pin windows had
    # removed the metal: iso_clamp_x4 VSS hooks landed on nothing, 2026-11-24)
    pieces_ = [(ln_, tz.bbox()) for ln_ in ('Metal4', 'Metal5') for poly in live[net][ln_].each() for tz in poly.decompose_trapezoids(1)] if net in live else strap_pieces[net]
    for ln, b in pieces_:
        if min(b.width(), b.height()) < um(5): continue          # slivers of the decomposition are no hook slots
        horiz = b.width() >= b.height(); L = b.width() if horiz else b.height(); n_ = max(1, int(L // um(22)))
        for j in range(n_):
            a0 = (b.left if horiz else b.bottom)+j*um(22)
            cb = db.Box(a0, b.bottom, min(a0+um(20), b.right), b.top) if horiz else db.Box(b.left, a0, b.right, min(a0+um(20), b.top))
            if not _blkreg.interacting(db.Region(cb)).is_empty(): continue     # no slot over a block: the hook dropped into adc_q's own Metal4 (SEN_A), 2026-11-24
            if any(cb.contains(db.Point(um(ax), um(ay))) for ax, ay in C.HOOK_SLOT_AVOID.get(CHIP, [])): continue   # common.HOOK_SLOT_AVOID
            lst.append([ln, cb, False])
    slots[net] = lst
PLATED = TRK.build(globals(), 'plates') if os.environ.get('PLATES', '1') == '1' else set()     # heavy supply pins: drawn plates to the grid (island_trunks.py, PDS-25 / ASM-17)
hook_pins = {}; man['digital_ties_not_hooked'] = 0
dland = ly.create_cell('pt_direct_land'); top.insert(db.CellInstArray(dland.cell_index(), db.Trans()))   # direct pin landings (own cell: checks can drop it)
k = 0
for net in GRID_NETS:
    for n, p in nets.get(net, []):
        if net != 'VDD' and net != 'VSS' and man['blocks'].get(n, {}).get('master') == 'decap': continue
        if n in man['blocks'] and man['blocks'][n]['master'] == 'decap': continue
        if n == 'digital' and not C.KH_CONN: man['digital_ties_not_hooked'] += 1; continue      # pre-KH: tie-offs left to the macro
        if n == 'digital': man['digital_ties_not_hooked'] += 1      # KH_CONN: macro inputs the conn ties to VDD / VSS: hooked at the top level (coordinator ruling 2026-11-26; the macro pins stay as hardened)
        if (n, p, net) in PLATED: continue      # plated (island_trunks._plates)
        if n in PADS['pads'] and n not in C.PAD_HOOK.get(CHIP, ()): continue      # pad-family supply pins land on the provider ring rails (DVDD / VSS bands), not on the grid; common.PAD_HOOK: pads whose supply pins do not reach the rails are hooked
        sh = pin_shapes_die(n, p)
        if not sh:
            if n in man['blocks'] or n in PADS['pads']: man['unconnectable'].append(dict(inst=n, pin=p, net=net, why='no pin shape (label) in the abstract'))
            continue
        # pin under (or on) its own strap: land it directly (Via4 from a Metal5 strap onto a Metal4 pin, or plain overlap)
        # instead of a hook net. Such a hook has both ends in one gcell: FastRoute gives it no guide and TritonRoute
        # leaves it unwired (43 rf / 59 wired open hooks, 2026-11-24).
        direct = 0; touched = False
        for pl, pb in sh:
            for sl_ in ('Metal4', 'Metal5'):       # the drawn grid metal (cut round blocks), not the uncut strap pieces
                ov = db.Region(pb) & (live[net][sl_] if net in live else metal.get((net, sl_), db.Region()))
                for on_ in GRID_NETS:
                    if on_ != net: ov -= metal.get((on_, sl_), db.Region()).sized(um(1))
                if ov.is_empty(): continue
                # only landings with room for >= 4 cuts (one-cut landings at a strap edge left isolated vias: atb_leaf_s
                # VSS open, 2026-11-24); same-layer overlaps are hooked like any other pin (an abstract pin rectangle can be
                # larger than its metal)
                if pl == 'Metal4' and sl_ == 'Metal5':
                    if ov.sized(-um(0.4)).area() >= um(1.24)*um(1.24): direct += via_fill(dland, VIA["Via4"], ov, inset=0.4)
                    elif min(pb.width(), pb.height()) >= um(0.46): direct += via_fill(dland, VIA["Via4"], ov, inset=0.1, single=True)   # thin pin strip under the strap (atb cells): a row of cuts
        if direct >= 4:
            man.setdefault('direct_landings', []).append(dict(net=net, inst=n, pin=p, via4=direct)); continue
        c = sh[0][1].center(); best = None
        for sl in slots[net]:
            if sl[2]: continue
            b = sl[1]; d = max(b.left-c.x, c.x-b.right, 0)+max(b.bottom-c.y, c.y-b.top, 0)
            # a slot sharing a global-route gcell (8.4 um grid) with the pin gives a local net that FastRoute leaves
            # without a guide and TritonRoute leaves unwired: such slots rank behind every other one
            pb_ = sh[0][1]; gx = lambda v: v // GCELL
            same = not (gx(b.right) < gx(pb_.left) or gx(pb_.right) < gx(b.left) or gx(b.top) < gx(pb_.bottom) or gx(pb_.top) < gx(b.bottom))
            key = (same, d)
            if best is None or key < best[0]: best = (key, sl)
        if best is not None: best = (best[0][1], best[1])
        if best is None: man['unconnectable'].append(dict(inst=n, pin=p, net=net, why='no free strap slot')); continue
        d, sl = best; sl[2] = True; ln, cb = sl[0], sl[1]
        hn = f'HK{k}'; k += 1; hook_pins[hn] = (ln, cb, net)
        man['hooks'].append(dict(net=f'{net}__{hn}', inst=n, pin=p, layer=ln, piece=[fu(cb.left), fu(cb.bottom), fu(cb.right), fu(cb.top)], dist_um=round(fu(d), 1)))
# provider pad ties (KH-1, pt_provider_io.sv via chips/provider_io): the core pins a pad cell ties to VDD (IE / PU / PD / CS /
# PDRV of the model) or VSS (A / OE / SL / ...) join one hook net per cell and polarity, to the nearest free grid slot
def io_pin_shapes(site, p):
    v = PADS['io'][site]; info = MJ.get(macro_of_io.get(site, ''), {}); o = info.get('origin', [0, 0]); t = RING_T*db.Trans.from_s(v['trans'])
    return [(ln, t*db.Box(um(r[0]+o[0]), um(r[1]+o[1]), um(r[2]+o[0]), um(r[3]+o[1]))) for ln, r in info.get('pins', {}).get(p, [])]
RING_T = next((i.trans for i in top.each_inst() if i.cell.name == 'retained_provider_ring'), db.Trans())
_cm = {c_[0]: c_[1] for c_ in comps}; macro_of_io = {s_: _cm[nm_] for s_, nm_ in iomap.items()}
man['io_ties'] = []
for r_ in PSITES:
    if r_['site'] not in iomap: continue
    for net in ('VDD', 'VSS'):
        tp_ = [p_ for p_, n_ in r_['pins'].items() if n_ == net and p_ in C.PIO.CORE[r_['cell']]]
        if not tp_: continue
        sh_ = [(p_, io_pin_shapes(r_['site'], p_)) for p_ in tp_]
        miss_ = [p_ for p_, x_ in sh_ if not x_]
        for p_ in miss_: man['unconnectable'].append(dict(inst=iomap[r_['site']], pin=p_, net=net, why='provider tie pin not in the abstract'))
        sh_ = [(p_, x_) for p_, x_ in sh_ if x_]
        if not sh_: continue
        c = db.Region([x_[0][1] for p_, x_ in sh_]).bbox().center(); best = None
        for sl in slots[net]:
            if sl[2]: continue
            b = sl[1]; d = max(b.left-c.x, c.x-b.right, 0)+max(b.bottom-c.y, c.y-b.top, 0)
            if best is None or d < best[0]: best = (d, sl)
        if best is None: man['unconnectable'] += [dict(inst=iomap[r_['site']], pin=p_, net=net, why='no free strap slot') for p_, x_ in sh_]; continue
        d, sl = best; sl[2] = True; ln, cb = sl[0], sl[1]
        io_ = iomap[r_['site']]
        if (io_, sh_[0][0]) in C.PAD_DIRECT_TIE.get(CHIP, ()) and len(sh_) == 1:
            # drawn tie (common.PAD_DIRECT_TIE): the pin strip carried out of the cell on Metal2 to the strap slot, Via2 /
            # Via3 (/ Via4) stack onto it; the router never has to reach a pin 20 um inside the pad cell (DRT, 2026-11-27)
            pb_ = max((b_ for l_, b_ in sh_[0][1] if l_ == 'Metal2'), key=lambda b_: max(b_.width(), b_.height()))
            horiz_ = pb_.width() >= pb_.height(); tc_ = cb.center(); hw_ = um(0.3)
            if horiz_:
                end_ = pb_.left if abs(pb_.left - tc_.x) < abs(pb_.right - tc_.x) else pb_.right; y_ = pb_.center().y
                m2_ = db.Box(min(end_, tc_.x) - um(1.5), y_ - hw_, max(end_, tc_.x) + um(1.5), y_ + hw_)
                land_ = db.Box(tc_.x - um(1.5), y_ - um(1.5), tc_.x + um(1.5), y_ + um(1.5))
            else:
                end_ = pb_.bottom if abs(pb_.bottom - tc_.y) < abs(pb_.top - tc_.y) else pb_.top; x_ = pb_.center().x
                m2_ = db.Box(x_ - hw_, min(end_, tc_.y) - um(1.5), x_ + hw_, max(end_, tc_.y) + um(1.5))
                land_ = db.Box(x_ - um(1.5), tc_.y - um(1.5), x_ + um(1.5), tc_.y + um(1.5))
            land_ = land_ & cb if (land_ & cb).area() > 0 else land_
            dland.shapes(LI['Metal2']).insert(m2_); dland.shapes(LI['Metal2']).insert(land_); dland.shapes(LI['Metal3']).insert(land_)
            nv_ = via_fill(dland, VIA['Via2'], db.Region(land_), inset=0.3) + via_fill(dland, VIA['Via3'], db.Region(land_), inset=0.3)
            if ln == 'Metal5': dland.shapes(LI['Metal4']).insert(land_); nv_ += via_fill(dland, VIA['Via4'], db.Region(land_), inset=0.3)
            man.setdefault('io_direct_ties', []).append(dict(inst=io_, pin=sh_[0][0], net=net, slot=[fu(cb.left), fu(cb.bottom), fu(cb.right), fu(cb.top)], vias=nv_))
            man['io_ties'].append(dict(site=r_['site'], cell=r_['cell'], net=net, pins=[sh_[0][0]], direct=True)); continue
        hn = f'HK{k}'; k += 1; hook_pins[hn] = (ln, cb, net)
        man['hooks'].append(dict(net=f'{net}__{hn}', inst=io_, pin=sh_[0][0], more=[[io_, p_] for p_, x_ in sh_[1:]], layer=ln,
                                 piece=[fu(cb.left), fu(cb.bottom), fu(cb.right), fu(cb.top)], dist_um=round(fu(d), 1)))
        man['io_ties'].append(dict(site=r_['site'], cell=r_['cell'], net=net, pins=[p_ for p_, x_ in sh_]))
barcell = ly.create_cell('pt_island_bar') if bars else None
man['island_bars'] = []
for bd in bars:
    barcell.shapes(LI['Metal5']).insert(bd['region']); barcell.shapes(LI['Metal4']).insert(bd['m4'])
    nv = via_fill(barcell, VIA['Via4'], bd['m4'] & bd['region'], inset=0.5) if not bd['m4'].is_empty() else 0
    if bd.get('tie_vias') and bd['tie_vias'][0] in man['blocks']:
        st_ = C.STAGED.get(CHIP, {}).get(bd['tie_vias'][0], {}); rp_ = R+st_.get('report', '')
        if os.path.isfile(rp_):
            ties_ = json.load(open(rp_)).get('ties', {}).get('VDD', {}); bx_, by_ = man['blocks'][bd['tie_vias'][0]]['bbox'][:2]
            for tn_ in bd['tie_vias'][1]:
                if tn_ in ties_:
                    t_ = ties_[tn_]; land_ = bd['m4'] & db.Region(db.Box(um(bx_+t_[0]), um(by_+t_[2]), um(bx_+t_[1]), um(by_+t_[3])))
                    nv += via_fill(barcell, VIA['Via4'], land_, inset=0.4)
    for i_, p_ in bd['vias']:
        for ln, b in pin_shapes_die(i_, p_):
            land = db.Region(b) & bd['region']
            if ln == 'Metal4' and not bd.get('merged'): nv += via_fill(barcell, VIA['Via4'], land, inset=0.3)
    man['island_bars'].append(dict(net=bd['net'], merged_with_cell_metal5=bd['merged'], area_mm2=round(bd['region'].area()/1e12, 4), via4=nv,
                                   bbox=[fu(v) for v in (bd['region'].bbox().left, bd['region'].bbox().bottom, bd['region'].bbox().right, bd['region'].bbox().top)]))
if barcell: top.insert(db.CellInstArray(barcell.cell_index(), db.Trans()))
# grid LEF: hook pieces are pins, everything else of the grid is an obstruction
Lp = ['MACRO pt_pdn', '  CLASS BLOCK ;', '  ORIGIN 0 0 ;', '  FOREIGN pt_pdn 0 0 ;', f'  SIZE {C.DIE[2]:.3f} BY {C.DIE[3]:.3f} ;', '  SYMMETRY X Y ;']
# HOOK_DUAL (default on for pt_wired, fp-wired 2026-11-27): a Metal5 hook slot over same-net Metal4 (ring, crossings) is a
# pin on Metal4 too (1 um inside the slot, opened in the Metal4 obstruction); the Metal4 under it is drawn and joined by
# the grid's Via4 array, so the router lands on Metal4 instead of putting a Via4 off the slot (fpw-2: 20 Metal5 shorts)
HOOK_DUAL = os.environ.get('HOOK_DUAL', '1') == '1'      # on for both chips (plan-rf6: 40+ ring hook shorts without it)
dual4 = {}
for hn, (ln, cb, net) in hook_pins.items():
    if HOOK_DUAL and ln == 'Metal5' and (net, 'Metal4') in metal:
        r4_ = (db.Region(cb).sized(-um(1.0)) & metal[(net, 'Metal4')]).merged()
        r4_ = db.Region([p_ for p_ in r4_.each() if min(p_.bbox().width(), p_.bbox().height()) >= um(2.0)])
        if not r4_.is_empty(): dual4[hn] = r4_
for hn, (ln, cb, net) in hook_pins.items():
    Lp += [f'  PIN {hn}', '    DIRECTION INOUT ;', '    USE SIGNAL ;', '    PORT', f'      LAYER {ln} ; RECT {fu(cb.left):.3f} {fu(cb.bottom):.3f} {fu(cb.right):.3f} {fu(cb.top):.3f} ;']
    for p_ in dual4.get(hn, db.Region()).each():
        for tz in p_.decompose_trapezoids(1):
            b = tz.bbox(); Lp.append(f'      LAYER Metal4 ; RECT {fu(b.left):.3f} {fu(b.bottom):.3f} {fu(b.right):.3f} {fu(b.top):.3f} ;')
    Lp += ['    END', f'  END {hn}']
# exposed bars (ISLAND_BARS expose=True): the bar's Metal5 is a pin of its rail net; the switch VISL pins under it leave the
# routed net (the bar joins them by Via4), so the router never digs into the switch for VISL (RAIL_rf_tx-VDD, 2026-11-24)
bar_pins = {}
for k_, bd in enumerate(bars):
    if not bd.get('expose'): continue
    pn_ = f'BAR{k_}'; bar_pins[pn_] = bd
    Lp += [f'  PIN {pn_}', '    DIRECTION INOUT ;', '    USE SIGNAL ;', '    PORT']
    for poly in bd['region'].merged().each():
        for tz in poly.decompose_trapezoids(1):
            b = tz.bbox(); Lp.append(f'      LAYER Metal5 ; RECT {fu(b.left):.3f} {fu(b.bottom):.3f} {fu(b.right):.3f} {fu(b.top):.3f} ;')
    Lp += ['    END', f'  END {pn_}']
Lp.append('  OBS')
for ln in ('Metal2', 'Metal3', 'Metal4', 'Metal5'):
    reg = (db.Region(pdn.begin_shapes_rec(LI[ln])) + (db.Region(barcell.begin_shapes_rec(LI[ln])) if barcell else db.Region())).merged() - db.Region([cb for hn, (l2, cb, net) in hook_pins.items() if l2 == ln])
    if ln == 'Metal5':
        for bd in bar_pins.values(): reg -= bd['region']
    # wide-metal spacing (M4.2b / MT.2b: space to metal wider than 10 um) is not in the router's tech LEF: wide grid / ring /
    # bar shapes are obstructions 0.5 um larger, so router wiring keeps the wide-metal spacing (165 of the 180 pt_rf precheck
    # DRC errors were router wiring at the straps, 2026-11-24)
    if ln in ('Metal4', 'Metal5'):
        # the wide test runs on the full metal (hook slots included), so a slot pin keeps a 0.5 um halo too: hook wires along
        # their own strap stayed 0.28 um off it (plan-rf4: 22 x M4.2b with the vertical Metal4 straps, 2026-11-27)
        full_ = reg if os.environ.get('SLOT_HALO', '1') == '0' else (db.Region(pdn.begin_shapes_rec(LI[ln])) + (db.Region(barcell.begin_shapes_rec(LI[ln])) if barcell else db.Region())).merged()
        wide_ = full_.sized(-um(5.0)).sized(um(5.0))
        reg = (reg + wide_.sized(um(0.5))).merged() - db.Region([cb for hn, (l2, cb, net) in hook_pins.items() if l2 == ln])
        if ln == 'Metal4':
            for r4_ in dual4.values(): reg -= r4_
        if ln == 'Metal5':
            for bd in bar_pins.values(): reg -= bd['region']
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
    if net in ('LO_IP', 'LO_IN', 'LO_QP', 'LO_QN'): return 'lo'      # coordinator: shielded differential pair to the mixers
    if net.startswith(('RAIL_', 'VREG_', 'VDD_')): return 'supply'
    u = net.upper()
    if u.startswith(('RF_', 'LNA_', 'LO_', 'BB_', 'MIX', 'RFI', 'RFO', 'TXRF', 'RX_LO', 'TX_LO', 'LOI', 'LOQ')) or 'LO_' in u: return 'rf'
    if u.startswith(('HSRX', 'URX', 'SL_', 'WTX', 'WIRE_TX', 'USB', 'HS_', 'D2H', 'H2D', 'WMON')) or u in ('AUX_CLK_P', 'AUX_CLK_N', 'REF_IN', 'REF_IN_N'): return 'hs'
    if 'CK' in u or 'CLK' in u or u.startswith(('TXPH', 'CDRPH', 'PH', 'FC_SRC')): return 'clock'
    return 'signal'
io_ends = collections.defaultdict(list)      # net -> provider cell pins on it (chips/provider_io)
for r_ in PSITES:
    for iop, pn_ in r_['pins'].items(): io_ends[pn_].append((r_['site'], iop))
NETS = {}
for net, users in nets.items():
    if net in SUP or net in GRID_NETS: continue      # grid and island-strap nets reach their pins through hooks
    ends = []
    for n, p in users:
        if inst[n]['master'].startswith(C.PROVIDER): continue
        if has_pin(n, p): ends.append((n, p))
        else: man['unconnectable'].append(dict(inst=n, pin=p, net=net, why='pin not in the abstract (no label on the block edge or in the cell)' if n in macro_of else 'instance not placed'))
    for s_, iop in io_ends.get(net, []):
        if s_ in iomap and has_pin(iomap[s_], iop): ends.append((iomap[s_], iop))
    for i, p, s, iop in prov:
        if inst[i]['pins'].get(p, ('', ''))[1] == net and s in iomap and has_pin(iomap[s], iop): ends.append((iomap[s], iop))
    for pn_, bd in bar_pins.items():
        if bd['net'] == net: ends = [e for e in ends if e not in [tuple(v) for v in bd['vias']]] + [('pdn', pn_)]
    ends = sorted(set(ends))
    if len(ends) >= 2: NETS[net] = dict(ends=ends, cls=cls(net))
    elif users: man['single_pin_nets'].append(net)
for h in man['hooks']:
    NETS[h['net']] = dict(ends=[(h['inst'], h['pin'])]+[tuple(e) for e in h.get('more', [])]+[('pdn', h['net'].split('__')[1])], cls='hook')

# ------------------------------------------------------------------------------------------- top-level antenna diodes
# common.ANT_DIODE nets: a 2 x 2 um n+ / p-substrate diode (COMP 22/0 + Nplus 32/0, 3 x 3 contacts, Metal1, Via1, Metal2 pin) next to
# every block receiver of the net, wired by the router (deck ANT.16 tail that router jumpers do not close, 2026-11-25)
import fnmatch as _fn
_adp = C.ANT_DIODE.get(CHIP, ())
AD_NETS = {n_ for n_ in NETS if any(_fn.fnmatchcase(n_, p_) for p_ in _adp)}
for n_, v_ in NETS.items():     # long nets (common.ANT_DIODE_LEN): pin bounding box half perimeter over the threshold
    if v_.get('cls') in ('hook', 'supply', 'lo') or n_ in ('VDD', 'VSS') or any(_fn.fnmatchcase(n_, p_) for p_ in C.ANT_LEN_EXCLUDE): continue
    pts_ = [sh_[0][1].center() for i_, p_ in v_['ends'] if i_ in man['blocks'] for sh_ in [pin_shapes_die0(i_, p_)] if sh_]
    if len(pts_) > 1 and fu(max(p.x for p in pts_)-min(p.x for p in pts_)+max(p.y for p in pts_)-min(p.y for p in pts_)) > C.ANT_DIODE_LEN: AD_NETS.add(n_)
man['antenna_diode_nets'] = sorted(AD_NETS)
man['antenna_diodes'] = []
if AD_NETS:
    dc = ly.create_cell('pt_antdiode')
    L_ = lambda a: ly.layer(a, 0)
    # 6 x 6 um n+ (36 um2, 2026-11-27): with the swapped grid long nets carry more Metal4; the deck counts 2 x diode area
    # (ANT.16 MF 2), so a 2 x 2 diode covered only about 1.7 mm of Metal4 at the 400 ratio
    dc.shapes(L_(22)).insert(db.Box(um(0.25), um(0.25), um(6.25), um(6.25)))           # COMP 6 x 6
    dc.shapes(L_(32)).insert(db.Box(0, 0, um(6.5), um(6.5)))                          # Nplus, 0.25 enclosure
    dc.shapes(L_(22)).insert(db.Box(um(7.3), um(0.25), um(7.9), um(6.25)))            # substrate tap (DF.14_LV: p+ within 20 um of n+)
    dc.shapes(L_(31)).insert(db.Box(um(7.05), 0, um(8.15), um(6.5)))                   # Pplus
    for i_ in range(11):
        for j_ in range(11):
            x_ = um(0.25+0.36+0.5*i_); y_ = um(0.25+0.36+0.5*j_)
            dc.shapes(L_(33)).insert(db.Box(x_, y_, x_+um(0.22), y_+um(0.22)))       # contacts 0.22, 0.28 space, 0.36 COMP enclosure
    dc.shapes(LI['Metal1']).insert(db.Box(um(0.45), um(0.45), um(6.05), um(6.05)))
    dc.shapes(L_(35)).insert(db.Box(um(3.12), um(3.12), um(3.38), um(3.38)))         # Via1
    dc.shapes(LI['Metal2']).insert(db.Box(um(2.85), um(2.85), um(3.65), um(3.65)))
    open('/run/lef/pt_antdiode.lef', 'w').write('\n'.join(['MACRO pt_antdiode', '  CLASS BLOCK ;', '  ORIGIN 0 0 ;', '  FOREIGN pt_antdiode 0 0 ;',
        '  SIZE 8.200 BY 6.500 ;', '  SYMMETRY X Y ;', '  PIN A', '    DIRECTION INOUT ;', '    USE SIGNAL ;', '    ANTENNADIFFAREA 36.0 ;', '    PORT',
        '      LAYER Metal2 ; RECT 2.850 2.850 3.650 3.650 ;', '    END', '  END A', '  OBS', '    LAYER Metal1 ;', '      RECT 0.000 0.000 8.200 6.500 ;',
        '  END', 'END pt_antdiode', '']))
    occ = db.Region([db.Box(*[um(v) for v in b_['bbox']]) for b_ in man['blocks'].values()]).merged().sized(um(3))
    occ += db.Region(db.Box(0, 0, um(C.DIE[2]), um(C.DIE[3]))) - db.Region(db.Box(*[um(v) for v in C.CORE]))
    # custom pad families reach into the core (pt_rf west pads to x 975): no diode in their footprint (plan-rf7: 25 diodes
    # inside pad_bb_q / pad_rf_tx, Metal2 shorts of the diode routes with the pad cells)
    occ += db.Region([db.Box(*[um(v) for v in r_]) for v_ in PADS['pads'].values() for r_ in v_['footprint']]).sized(um(3))
    # booked ledger items and floorplan reserves become Metal1-3 blockages in the DEF: no diode there (fpw-3 antd in a booking, Metal2 short)
    occ += db.Region([db.Box(*[um(v) for v in r_]) for n_, r_ in list(booked.items())+list(FP['reserves'].items())
                      if n_ != 'd2h_strip' and not n_.startswith(('chan_', 'corridor', 'pocket'))]).sized(um(2))
    # ANT_AVOID_GRID (default on for pt_wired, fp-wired 2026-11-27): no diode under grid Metal4 / Metal5; the router then
    # climbed from the diode's Metal2 pin through the strap (fpw-2: RAIL_wired_tx diode antd_113 under a VDD strap, VDD short)
    if os.environ.get('ANT_AVOID_GRID', '1') == '1':
        for k_ in [k_ for k_ in metal if k_[1] in ('Metal4', 'Metal5')]: occ += metal[k_].sized(um(0.5))      # 0.5 um: 22 um straps leave 13 um gaps (pt_wired MC/ME/SE)
    for net_ in sorted(AD_NETS & set(NETS)):
        ends_ = [e for e in NETS[net_]['ends'] if e[0] not in ('digital', 'pdn') and e[0] in man['blocks']]
        # fallback: where no receiver has room, the diode goes by the macro pin (plan-rf6: adc_q / bbfilter_q corners full)
        ends_ += [e for e in NETS[net_]['ends'] if e[0] == 'digital']
        for i_, p_ in ends_:
            if i_ == 'digital' and any(x_['placed'] for x_ in man['antenna_diodes'] if x_['net'] == net_): continue
            # island rails: one diode per rail protects every gate on it; a diode at each load added rail branches into the
            # switch / iso cells (plan-rf5: 8 rail DRT at isw_rf_tx VDD and iso_conv_clk)
            if net_.startswith('RAIL_') and any(x_['placed'] for x_ in man['antenna_diodes'] if x_['net'] == net_): break
            sh_ = pin_shapes_die0(i_, p_)
            if not sh_: continue
            c_ = sh_[0][1].center(); spot = None
            # nearest free spot within 150 um: the free area round the pin eroded by the diode half-size + 2 um margin; its
            # vertices are legal diode centres (8-direction probing found too few spots between the grid straps)
            for rw_ in (40, 150, 400):
                win_ = db.Region(db.Box(c_.x-um(rw_), c_.y-um(rw_), c_.x+um(rw_), c_.y+um(rw_)))
                cand_ = (win_ - (occ & win_.sized(um(10)))).merged().sized(-um(4.1+1.0), -um(3.25+1.0))
                best_ = None
                for poly_ in cand_.each():
                    for pt_ in poly_.each_point_hull():
                        d_ = abs(pt_.x-c_.x)+abs(pt_.y-c_.y)
                        if best_ is None or d_ < best_[0]: best_ = (d_, pt_)
                if best_:
                    q_ = best_[1]; q_ = db.Point(q_.x//10*10, q_.y//10*10)
                    b_ = db.Box(q_.x-um(4.1), q_.y-um(3.25), q_.x+um(4.1), q_.y+um(3.25))
                    if (occ & db.Region(b_.enlarged(um(1), um(1)))).is_empty(): spot = b_; break
            if spot is None: man['antenna_diodes'].append(dict(net=net_, pin=f'{i_}.{p_}', placed=False)); continue
            nm_ = f'antd_{len(man["antenna_diodes"])}'
            top.insert(db.CellInstArray(dc.cell_index(), db.Trans(db.Vector(spot.left, spot.bottom))))
            comps.append((nm_, 'pt_antdiode', fu(spot.left), fu(spot.bottom), 'N'))
            NETS[net_]['ends'].append((nm_, 'A')); occ += db.Region(spot.enlarged(um(1.5), um(1.5)))
            man['antenna_diodes'].append(dict(net=net_, pin=f'{i_}.{p_}', placed=True, at=[fu(spot.left), fu(spot.bottom)]))

# ------------------------------------------------------------------------------------------- DEF
D = ['VERSION 5.8 ;', 'DIVIDERCHAR "/" ;', 'BUSBITCHARS "[]" ;', 'DESIGN pt_chip_top ;', 'UNITS DISTANCE MICRONS 1000 ;',
     f'DIEAREA ( 0 0 ) ( {um(C.DIE[2])} {um(C.DIE[3])} ) ;', f'COMPONENTS {len(comps)} ;']
for n, m, x, y, o in comps: D.append(f'- {n} {m} + FIXED ( {um(x)} {um(y)} ) {o} ;')
D += ['END COMPONENTS', f'NETS {len(NETS)} ;']
for net, v in NETS.items():
    D.append(f'- {net} '+' '.join(f'( {i} {p} )' for i, p in v['ends'])+' + USE SIGNAL ;')
D += ['END NETS']
# routing channels and corridors of the floorplan stay open; booked items are Metal1-3 blockages; nothing is routed in the
# provider-ring band outside the IO cells' inner edge (5 um short of it, so the IO pins stay reachable) or over the seal ring
blk = [(n, r, ('Metal1', 'Metal2', 'Metal3')) for n, r in list(booked.items())+list(FP['reserves'].items())
       if n != 'd2h_strip' and not n.startswith(('chan_', 'corridor', 'pocket'))]
e = C.IO_INNER-5; W_, H_ = C.DIE[2], C.DIE[3]; ML = tuple(n for n, *_ in C.METALS)
# the 5 um access strip inside the IO inner edge is open only in front of pad cells (custom pads and provider signal cells,
# whose pins are there); between pads it carries the provider ring's rails (atb1_sw[5/12/59] ran into 3LM/5LM_METAL_RAIL
# and their via cells at y 4747.6-4749, joining VDD and VSS, 2026-11-24)
_padx = db.Region([db.Box(um(v['bbox'][0]), um(v['bbox'][1]), um(v['bbox'][2]), um(v['bbox'][3])) for v in list(PADS['pads'].values())+[w for w in PADS['io'].values() if not w['cell'].endswith(('dvss', 'dvdd'))]]).merged()      # supply cells: no pins, rails only
_strip = db.Region(db.Box(0, 0, um(W_), um(H_))) - db.Region(db.Box(um(C.IO_INNER+0.3), um(C.IO_INNER+0.3), um(W_-C.IO_INNER-0.3), um(H_-C.IO_INNER-0.3)))
_strip -= db.Region(db.Box(0, 0, um(W_), um(H_))) - db.Region(db.Box(um(e), um(e), um(W_-e), um(H_-e)))      # the outer band is blocked below
for _poly in (_strip - _padx.sized(um(0.5))).merged().each():
    for _t in _poly.decompose_trapezoids(1):
        _b = _t.bbox(); blk.append(('ring_strip', (fu(_b.left), fu(_b.bottom), fu(_b.right), fu(_b.top)), ML))
# MIMTM.1: routed Metal4 keeps 1.2 um from a MIM bottom plate; plates near a block edge reach outside its abstract, so the
# FuseTop (75/0) of every placed block, grown 2.3 um, is a top-level Metal4 blockage (10 MIMTM.1 in pt_rf router wiring)
_ft = ly.find_layer(75, 0)
if _ft is not None:
    _mim = db.Region(top.begin_shapes_rec(_ft)).merged().sized(um(2.3)).merged()
    for _poly in _mim.each():
        for _t in _poly.decompose_trapezoids(1):
            _b = _t.bbox(); blk.append(('mim_keepout', (fu(_b.left), fu(_b.bottom), fu(_b.right), fu(_b.top)), ('Metal4',)))
# island switches: Metal2-3 blocked 1 um round the outline (the router ran RAIL_rf_tx along the switch edge into its own
# Metal3 = VISL joined to VDD through the switch, 2026-11-24)
for n_, b_ in man['blocks'].items():
    if b_['master'].startswith('isw'):
        bb_ = b_['bbox']; blk.append(('isw_halo', (bb_[0]-1.0, bb_[1]-1.0, bb_[2]+1.0, bb_[3]+1.0), ('Metal2', 'Metal3')))
for r in ((0, 0, W_, e), (0, H_-e, W_, H_), (0, 0, e, H_), (W_-e, 0, W_, H_)): blk.append(('ring_band', r, ML))
# the provider ring's filler / rail / corner cells carry supply rails up to their inner edge, inside the 5 um access margin
# above: those cells (no pins) are blocked on every metal out to their full extent + 0.3 um (WSMP_CK ran 0.11 um into
# the fill10 / METAL_RAIL rails on pt_wired and joined VDD to VSS, 2026-11-24)
_pr = ly.cell('retained_provider_ring')
_prt = next((i.cplx_trans for i in top.each_inst() if i.cell.name == 'retained_provider_ring'), None)
if _pr is not None and _prt is not None:
    _rg = db.Region()
    for _i in _pr.each_inst():
        if any(k in _i.cell.name for k in ('fill', 'RAIL', '__cor', 'CDNS')): _rg.insert(_i.bbox().transformed(_prt).enlarged(um(0.3), um(0.3)))
    for _poly in _rg.merged().each():
        for _t in _poly.decompose_trapezoids(1):
            _b = _t.bbox(); blk.append(('ring_fill', (fu(_b.left), fu(_b.bottom), fu(_b.right), fu(_b.top)), ML))
blk += TRK.blockages()      # 0.6 um Metal5 ring round each island trunk (TRUNKS=1 only; empty otherwise)
D.append(f'BLOCKAGES {sum(len(l) for n, r, l in blk)} ;')
for n, r, lays in blk:
    for ln in lays: D.append(f'- LAYER {ln} RECT ( {um(r[0])} {um(r[1])} ) ( {um(r[2])} {um(r[3])} ) ;')
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
      f"hooks {len(man['hooks'])}, direct landings {len(man.get('direct_landings', []))}, unconnectable pins {len(man['unconnectable'])}, single-pin nets {len(man['single_pin_nets'])}")
_ms = man.get('macro_supply', {})
# fail: a strap with no end on the grid (or no strap at all); one-end straps (the other end against a pad family) are reported
_mv = 'OK' if _ms and all(v['stripes'] > 0 and v['joined'] + v.get('one_end', 0) == v['stripes'] and v.get('via4', 0) != 0 for v in _ms.values()) else 'MACRO SUPPLY OPEN'
print("pdn", man["pdn"], "| macro supply", _mv, {k: (v["joined"], v.get("one_end", 0), v["stripes"]) for k, v in _ms.items()})
for n in man['notes'][:20]: print(' note:', n)
