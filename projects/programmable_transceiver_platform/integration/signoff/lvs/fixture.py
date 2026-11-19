# KLayout: routed mini chip for the LVS positive and negative controls.
#   kl.sh lvs/fixture.py -rd insts=a,b,c [-rd bridge=1 | -rd openvia=1]
# Takes the cells of the named instances out of the skeleton GDS (real blocks and placeholders, exactly as assembled),
# places them in rows with routing channels and routes EVERY net of the chip conns that has two or more pins among them
# (reference: /run/lvs/fix/fixture.ref.spice from gen_netlist.py --only). Router: Lee maze on a 2 um grid, Metal4 and
# Metal5, via stacks from the pin layer; obstacles are the real block metal on every layer.
# Output /run/lvs/fix/fixture.gds (top pt_fixture) + fixture_manifest.json.  bridge=1 adds one Metal4 strap from a routed net
# across a real block's internal metal (negative control: short to block-internal nets).
import json, os, collections
import klayout.db as db
G = dict(globals())
want = G['insts'].split(',')
man = json.load(open('/run/chip/manifest.json'))
byname = {i['name']: i for i in man['instances']}
src = db.Layout(); src.read('/run/chip/pt_chip_top.gds')
ly = db.Layout(); ly.dbu = 0.001
top = ly.create_cell('pt_fixture')
um = lambda v: int(round(v*1000))
MET = {1: (34, 0), 2: (36, 0), 3: (42, 0), 4: (46, 0), 5: (81, 0)}
VIA = {1: (35, 0), 2: (38, 0), 3: (40, 0), 4: (41, 0)}
LBL = {1: 34, 2: 36, 3: 42, 4: 46, 5: 81}
g = 2000; HW = 300; CUT = 130      # grid, half wire width, half via cut (dbu)

# ---- placement: rows, 80 um channels
cells = {}; fman = dict(top='pt_fixture', instances=[])
x = y = 60000; rowh = 0
for n in want:
    i = byname[n]; cn = i['cell']
    if cn not in cells:
        c = ly.create_cell(cn); c.copy_tree(src.cell(cn)); cells[cn] = c
    c = cells[cn]; b = c.bbox()
    if x+b.width() > 1500000: x = 60000; y += rowh+80000; rowh = 0
    tr = db.Trans(db.Vector(x-b.left, y-b.bottom))
    top.insert(db.CellInstArray(c.cell_index(), tr))
    bb = tr*b
    fman['instances'].append(dict(name=n, master=i['master'], cell=cn, trans=str(tr), kind=i['kind'], bbox=[bb.left/1000, bb.bottom/1000, bb.right/1000, bb.top/1000]))
    x += b.width()+80000; rowh = max(rowh, b.height())
W = top.bbox().right+60000; H = top.bbox().top+60000
nx, ny = W//g+1, H//g+1

# ---- reference nets among the fixture instances
def read_spice(path):
    lines = []
    for ln in open(path):
        ln = ln.rstrip('\n')
        if ln.startswith('+') and lines: lines[-1] += ' '+ln[1:]
        else: lines.append(ln)
    sub, cur = {}, None
    for ln in lines:
        t = ln.split()
        if not t or t[0][0] == '*': continue
        if t[0].lower() == '.subckt': cur = dict(pins=t[2:], x=[]); sub[t[1]] = cur
        elif t[0].lower() == '.ends': cur = None
        elif t[0][0] in 'xX' and cur is not None: cur['x'].append((t[0][1:], t[1:-1], t[-1]))
    return sub
ref = read_spice('/run/lvs/fix/fixture.ref.spice')
nets = collections.defaultdict(list)
for name, ns, master in ref['pt_fixture']['x']:
    for p, n in zip(ref[master]['pins'], ns): nets[n].append((name, p))
nets = {n: m for n, m in nets.items() if len(m) > 1}

# ---- obstacles: block metal per layer, grown by wire half width + 1 um clearance
blk = {}
for L in range(1, 6):
    r = db.Region(top.begin_shapes_rec(ly.layer(*MET[L]))).merged().sized(HW+1000)
    a = bytearray(nx*ny)
    for t in r.decompose_trapezoids_to_region().each():
        bb = t.bbox()
        x0, x1 = max(0, -(-bb.left//g)), min(nx-1, bb.right//g); y0, y1 = max(0, -(-bb.bottom//g)), min(ny-1, bb.top//g)
        if x1 >= x0:
            for iy in range(y0, y1+1): a[iy*nx+x0:iy*nx+x1+1] = b'\x01'*(x1-x0+1)
    blk[L] = a

# ---- pin access nodes
inst_tr = {i['name']: db.Trans.from_s(i['trans']) for i in fman['instances']}
inst_cell = {i['name']: ly.cell(i['cell']) for i in fman['instances']}
pinpoly_cache = {}
obs = {L: db.Region(top.begin_shapes_rec(ly.layer(*MET[L]))).merged() for L in range(1, 6)}
def pin_access(inst, pin):
    """-> (pin layer, {grid node: stack point or None}) or (None, {}) when the pin has no label.
    Metal4/Metal5 pins are entered on any grid node inside the pin. Lower pins get a via stack up to Metal4 at a point P
    of the pin where the layers above it are clear, and a jog from P to the nearest node."""
    c = inst_cell[inst]; tr = inst_tr[inst]
    key = (c.name, pin)
    if key not in pinpoly_cache:
        found = None
        for L in (5, 4, 3, 2, 1):
            for d in (10, 0):
                li = ly.find_layer(LBL[L], d)
                if li is None: continue
                for s in c.shapes(li).each(db.Shapes.STexts):
                    if s.text.string == pin and found is None:
                        pt = s.text.trans.disp
                        reg = db.Region(c.begin_shapes_rec_touching(ly.layer(*MET[L]), db.Box(pt.x-1, pt.y-1, pt.x+1, pt.y+1))).merged()
                        poly = [q for q in reg.each() if q.inside(db.Point(pt.x, pt.y))]
                        if poly: found = (L, poly[0], db.Point(pt.x, pt.y))
        pinpoly_cache[key] = found
    f = pinpoly_cache[key]
    if f is None: return None, {}, None
    L, poly, pt = f
    q = poly.transformed(tr)
    acc = {}          # grid node -> (P, routing layer): P None = the routing-layer wire lands on the pin itself at the node
    def jog(P, K):
        kx, ky = (K % nx)*g, (K//nx)*g
        return [db.Box(min(P.x, kx)-HW, P.y-HW, max(P.x, kx)+HW, P.y+HW), db.Box(kx-HW, min(P.y, ky)-HW, kx+HW, max(P.y, ky)+HW)]
    def clear(layer, boxes, margin=400):
        r = db.Region(); [r.insert(bx.enlarged(margin, margin)) for bx in boxes]
        return obs[layer].interacting(r).is_empty()
    if L >= 4:
        for t in db.Region(q).sized(-HW).decompose_trapezoids_to_region().each():
            bb = t.bbox()
            for ix in range(-(-bb.left//g), bb.right//g+1):
                for iy in range(-(-bb.bottom//g), bb.top//g+1): acc[iy*nx+ix] = (None, L)
    if not acc:       # no grid node on the pin (thin or low pin): via stack at a point P of the pin, then a jog on the layer above
        cands = [tr*pt]+[t.bbox().center() for t in db.Region(q).decompose_trapezoids_to_region().each()][:400]
        for P in cands:
            pad = db.Box(P.x-HW, P.y-HW, P.x+HW, P.y+HW)
            K = int(round(P.y/g))*nx+int(round(P.x/g))
            if L < 4 and not db.Region(pad).inside(db.Region(q)).count(): continue
            if L >= 4:
                same = (obs[L] - db.Region(q)).interacting(db.Region([bx.enlarged(400, 400) for bx in jog(P, K)])).is_empty()
                if same: acc.setdefault(K, (P, L))                               # jog on the pin's own layer, clear of other metal
                elif L == 4 and clear(5, [pad]+jog(P, K)) and (obs[4] - db.Region(q)).interacting(db.Region(pad.enlarged(400, 400))).is_empty(): acc.setdefault(K, (P, 5))    # Via4 at P, jog on Metal5
            elif all(clear(j, [pad], 600) for j in range(L+1, 5)): acc.setdefault(K, (P, 4))   # low pin: stack to Metal4, clear above the pin
            if len(acc) >= 24: break
    return L, acc, q

occ = {4: bytearray(nx*ny), 5: bytearray(nx*ny)}      # wires already routed (other nets), with their spacing halo
shapes = collections.defaultdict(list)                   # (layer, datatype) -> boxes
def box_at(k, h): ix, iy = k % nx, k//nx; return db.Box(ix*g-h, iy*g-h, ix*g+h, iy*g+h)
def draw_via(k, j):        # cut j between metal j and j+1 at node k
    shapes[VIA[j]].append(box_at(k, CUT)); shapes[MET[j]].append(box_at(k, HW)); shapes[MET[j+1]].append(box_at(k, HW))
report = dict(routed=0, failed=[], no_label=[], no_access=[], wire_um=0.0)
for n, mem in sorted(nets.items(), key=lambda kv: len(kv[1])):
    tree = {}          # state (layer, node) -> True
    pins = []; passable = set()
    for inst, pin in mem:
        L, acc, q = pin_access(inst, pin)
        if L is None: report['no_label'].append(f'{inst}.{pin}'); continue
        if not acc: report['no_access'].append(f'{inst}.{pin}'); continue
        pins.append((inst, pin, L, acc))
        if L >= 4:        # the clearance halo of the net's own pin metal is not an obstacle for this net
            own = db.Region(q); band = own.sized(HW+1000+g)
            other = ((obs[L] & band.sized(HW+1000)) - own).sized(HW+1000)
            for t in (band - other).decompose_trapezoids_to_region().each():
                bb = t.bbox()
                for ix in range(max(0, -(-bb.left//g)), min(nx-1, bb.right//g)+1):
                    for iy in range(max(0, -(-bb.bottom//g)), min(ny-1, bb.top//g)+1): passable.add((L, iy*nx+ix))
    if len(pins) < len(mem) or len(pins) < 2: continue
    ok = True
    def attach(L, a, K):          # pin metal -> (via stack at P up to the access layer, jog to grid node K) -> routing state
        P, rl = a
        if P is None: shapes[MET[rl]].append(box_at(K, HW)); return (rl, K)
        for j in range(L, rl):
            b = db.Box(P.x-CUT, P.y-CUT, P.x+CUT, P.y+CUT); m = db.Box(P.x-HW, P.y-HW, P.x+HW, P.y+HW)
            shapes[VIA[j]].append(b); shapes[MET[j]].append(m); shapes[MET[j+1]].append(m)
        kx, ky = (K % nx)*g, (K//nx)*g
        shapes[MET[rl]].append(db.Box(min(P.x, kx)-HW, P.y-HW, max(P.x, kx)+HW, P.y+HW))
        shapes[MET[rl]].append(db.Box(kx-HW, min(P.y, ky)-HW, kx+HW, max(P.y, ky)+HW))
        return (rl, K)
    inst, pin, L, acc = pins[0]
    for K, a in acc.items():      # the whole first pin is the start of the tree
        tree[(a[1], K)] = (L, a)
    for inst, pin, L, acc in pins[1:]:
        goal = {(a[1], K) for K, a in acc.items()}
        prev = {s: None for s in tree}; q = collections.deque(tree); hit = None
        while q:
            s = q.popleft()
            if s in goal: hit = s; break
            l, k = s; ix, iy = k % nx, k//nx
            cand = []
            if ix > 0: cand.append((l, k-1))
            if ix < nx-1: cand.append((l, k+1))
            if iy > 0: cand.append((l, k-nx))
            if iy < ny-1: cand.append((l, k+nx))
            cand.append((9-l, k))
            for c2 in cand:
                if c2 in prev: continue
                if c2 not in goal and (occ[c2[0]][c2[1]] or (blk[c2[0]][c2[1]] and c2 not in passable)): continue
                prev[c2] = s; q.append(c2)
        if hit is None: ok = False; report['failed'].append(f'{n}: {inst}.{pin}'); continue
        attach(L, acc[hit[1]], hit[1])
        s = hit; path = []
        while s is not None: path.append(s); s = prev[s]
        root = path[-1]
        if tree[root] is not True: attach(tree[root][0], tree[root][1], root[1])      # entry node of a pin of this net: draw its access once
        for a_, b_ in zip(path, path[1:]):
            if a_[0] != b_[0]: draw_via(a_[1], 4)
            else: shapes[MET[a_[0]]].append(box_at(a_[1], HW)+box_at(b_[1], HW)); report['wire_um'] += g/1000
        for s in path: tree[s] = True
        for K, a in acc.items(): tree.setdefault((a[1], K), (L, a))     # this pin's other nodes are entry points for later pins
    for l, k in tree: occ[l][k] = 1          # 2 um grid, 0.6 um wires: neighbouring tracks keep 1.4 um
    report['routed'] += ok
if G.get('bridge'):
    # a Metal4 strap across the first real block, from its left edge to its right edge, through whatever is inside
    i = next(i for i in fman['instances'] if i['kind'] != 'placeholder')
    b = i['bbox']; yb = um((b[1]+b[3])/2)
    shapes[MET[4]].append(db.Box(um(b[0])-4000, yb-HW, um(b[2])+4000, yb+HW)); report['bridge_over'] = i['name']
if G.get('openvia'):      # negative control: one routed Via4 removed (an open)
    report['removed_via4'] = str(shapes[VIA[4]].pop(len(shapes[VIA[4]])//2))
for (l, d), bx in shapes.items():
    reg = db.Region(); [reg.insert(q) for q in bx]
    top.shapes(ly.layer(l, d)).insert(reg.merged())
os.makedirs('/run/lvs/fix', exist_ok=True)
SUF = '_bridge' if G.get('bridge') else '_openvia' if G.get('openvia') else ''
ly.write('/run/lvs/fix/fixture'+SUF+'.gds')
json.dump(fman, open('/run/lvs/fix/fixture_manifest.json', 'w'), indent=0)
report['nets'] = len(nets)
json.dump(report, open('/run/lvs/fix/route_report'+SUF+'.json', 'w'), indent=0)
print(f"fixture {len(want)} instances, {W/1000:.0f} x {H/1000:.0f} um; nets {len(nets)}, fully routed {report['routed']}, wire {report['wire_um']:.0f} um")
for k in ('failed', 'no_label', 'no_access'):
    if report[k]: print(f' {k}: {len(report[k])}', report[k][:10])
