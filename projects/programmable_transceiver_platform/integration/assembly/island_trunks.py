# Island supply trunks (stage place; kl_place.py calls build(globals()) after the island bars and adds blockages() to the DEF).
# Coordinator ruling 2026-11-24 / PDS-19 / PDS-20 (README "Island rail plan"): every switched-island load above about 1 mA gets
# a drawn trunk from its switch (VISL plate / pins, or the island bar) sized at about 1 mA/um of its own current, wider where
# the IR allowance needs it; loads <= 1 mA stay router leaves (1 um) to the trunk, whose Metal5 is a pin of the rail net.
#   * One path per load (star from the source): Dijkstra on a 4 um raster over Metal5 (preferred) and Metal4 (cost x1.6,
#     Via4 change 24 um, turn 40 um); the centre line inside the free space eroded by half the width, the drawn metal clipped
#     to the free space. Free = core minus each layer's block metal + 2.5 um, the no-route-over set + 8 um, pads, core ring,
#     signal-pin windows (the rail's own pins excepted), the digital macro, MIM keep-out (Metal4), other nets' bars / trunks
#     + 3 um. Grid straps give way (avoid += trunk + 2.5 um).
#   * Landing: a corridor (pin length wide) from the pin to 16 um outside the block edge, free of that block's other-net
#     metal (+2.5 um); Metal5 onto a Metal5 pin, Metal4 onto a Metal4 pin (same-layer overlap), or Metal5 over a Metal4 pin
#     with Via4 where the block has no Metal5 / Via4 there. A switch is reached on its VISL Metal5 plate or VISL Metal4 pins.
#   * Metal5 of the trunk joins the island's bar (or becomes a new exposed bar: a pin of the rail net); Metal4 of the trunk
#     and its Via4 at layer changes go into pt_pdn (an obstruction for the router). MSLOT: 3 x 3 um holes on 24 um pitch where
#     Metal5 is wider than 28 um. MT.2b: 0.6 um Metal5 blockage ring round the trunk (router wiring keeps the wide spacing).
#   * IR / EM: resistive mesh of the drawn trunk (2 um cells, Metal5 0.070 / Metal4 0.104 ohm/sq = tech-LEF maximum, Via4 0.5
#     ohm per 2 x 2 um of overlap), each switch a node behind its on-resistance, the design current of each load spread over
#     its landing. Per load the drop from the reference switch node; per switch its current; peak mA/um per layer (body,
#     and the landing necks within 20 um of a pin separately). Result: place.json 'island_trunks'.
import math, json
import numpy as np
import scipy.sparse as sp, scipy.sparse.linalg as spl
from scipy.sparse import csgraph

RS = {'Metal5': 0.070, 'Metal4': 0.104}      # ohm/sq maximum (tech LEF; scratch/integration/m1-pdn/model.py)
R_VIA_CELL = 0.5                              # ohm per 2 x 2 um of Via4 array (about 9 cuts)
J_TARGET = 1.0                                # mA per um of drawn width (coordinator sizing rule)
G = 4.0; TURN = 40.0; VIA_COST = 24.0; LCOST = {'Metal5': 1.0, 'Metal4': 1.6}
W_MAX = 120.0
LAYERS = ('Metal5', 'Metal4')
# Switch on-resistance (ohm) for current sharing: isw_wired 0.124 for two (PDS-20), isw_rf 13.1 mV / 43.6 mA, isw_debug from
# isw_wired || isw_debug = 0.151 (power-delivery 2), isw_conv 11.2 mV / 18.7 mA (e7 conv split).
R_SW = {'isw_wired': 0.248, 'isw_rf': 0.30, 'isw_debug': 0.386, 'isw_conv': 0.60}
# Per island: switches (first = drop reference), loads above ~1 mA with worst mA (README rail plan / PDS-19; rf_tx lo_txbuf r3
# 59.3 mA extracted, PDS-20), the design total (PDS-19 / PDS-20, loads scaled to it) and the strap allowance (mV): the e7
# split's 15 mV strap plus the island's worst tap margin to 117 mV ('pess-81.8' column of
# scratch/integration/m1-pdn/out/<chip>/e7_static_base.txt); debug (not in e7) gets the G5 15 mV.
ISLANDS = {
 'rf': {
  'RAIL_rf_tx':  dict(sw=['isw_rf_tx', 'isw_rf_tx_b'], loads={'lo_txbuf': 59.3, 'rfdriver': 24.3, 'txmix_i': 2.0, 'txmix_q': 2.0, 'txsum': 2.0}, design=91.6, allow=67.9),
  'RAIL_lod':    dict(sw=['isw_lod'], loads={'lo_mmd': 34.8, 'lo_ext': 13.7, 'lo_mmd_qdum': 10.0, 'lo_obs': 8.0, 'lo_obs_q': 8.0, 'qvco': 4.0}, design=79.0, allow=36.0),
  'RAIL_rf_rx':  dict(sw=['isw_rf_rx'], loads={'lna': 21.4, 'bbfilter_i': 5.3, 'bbfilter_q': 5.3, 'rxmix_i': 3.1, 'rxmix_q': 3.1}, design=43.6, allow=75.5),
  'RAIL_debug':  dict(sw=['isw_debug'], loads={'vco_replica': 11.8, 'clk_obs': 5.1, 'rx_aux_clk': 5.1}, design=40.0, allow=15.0),
  'RAIL_pll':    dict(sw=['isw_pll'], loads={'pll_vreg2': 20.9, 'prescale': 2.4, 'prescale_hf': 2.4, 'prescale_conv': 2.4, 'cdr': 2.0}, design=30.7, allow=79.7),
  'RAIL_lo':     dict(sw=['isw_lo'], loads={'lo_vreg': 27.5}, design=28.1, allow=53.4),
  'RAIL_conv':   dict(sw=['isw_conv'], loads={'adc_i': 6.3, 'adc_q': 6.3, 'dac_i': 2.3, 'dac_q': 2.3, 'refbuf': 1.6}, design=18.7, allow=76.4)},
 'wired': {
  'RAIL_wired_tx':  dict(sw=['isw_wired_tx_a', 'isw_wired_tx_b'], loads={'wiredtx': 60.0, 'pad_wire_tx': 21.0, 'usb_txdrv': 20.0}, design=131.3, allow=33.0),
  'RAIL_wired_cap': dict(sw=['isw_wired_cap'], loads={'wrx_cap': 46.6, 'ptrim': 21.0, 'wordclk_rx': 2.4}, design=72.9, allow=22.8),
  'RAIL_debug':     dict(sw=['isw_debug'], loads={'vco_replica': 11.8, 'clk_obs': 5.1, 'rx_aux_clk': 5.1, 'rx_wtx_ext': 5.1}, design=40.0, allow=15.0),
  'RAIL_wired_rx':  dict(sw=['isw_wired_rx'], loads={'slicer': 9.8, 'ctle': 5.3, 'detect': 2.4, 'rxselect': 2.0, 'termination': 1.6}, design=30.9, allow=49.5),
  'RAIL_pll':       dict(sw=['isw_pll'], loads={'pll_vreg2': 20.9, 'prescale': 2.4, 'prescale_hf': 2.4, 'cdr': 2.0, 'clockmux': 1.6}, design=29.4, allow=60.4)}}
LP = dict(own=0.7, opin=1.0, all_sides=True)      # landing parameters; _plates retries a failed pin with LEGACY_LP
LEGACY_LP = dict(own=2.5, opin=3.0, all_sides=False)   # before 2026-11-28: clk_obs / rx_aux_clk plated only with these
_RES = [None]            # reserved plate landing area (reserve -> _plates)
_BLK = []                # DEF blockage rectangles (name, (x0, y0, x1, y1), layers)


def blockages():
    return list(_BLK)


def build(g, mode='trunks'):
    db = g['db']; um = g['um']; fu = g['fu']; C = g['C']; ly = g['ly']; man = g['man']; MJ = g['MJ']; LI = g['LI']
    CHIP = g['CHIP']; PADS = g['PADS']; nets = g['nets']; bars = g['bars']; avoid = g['avoid']; pdn = g['pdn']; top = g['top']
    spec = ISLANDS.get(CHIP, {})
    rep = man.setdefault('island_trunks' if mode == 'trunks' else 'grid_plates', {})
    if mode == 'trunks' and not spec: return
    core = db.Box(*[um(v) for v in C.CORE])
    L_V4 = ly.layer(41, 0)

    def placed(n):
        if n in man['blocks']: b = man['blocks'][n]; return b['master'], db.Trans.from_s(b['trans']), db.Box(*[um(v) for v in b['bbox']])
        if n in PADS['pads']: v = PADS['pads'][n]; return v['master'], db.Trans.from_s(v['trans']), db.Box(*[um(x) for x in v['bbox']])
        return None
    mcache = {}
    def cell_m(n, ln):
        k = (n, ln)
        if k not in mcache:
            pl = placed(n); c = ly.cell(pl[0]) if pl else None
            lay = L_V4 if ln == 'Via4' else ly.layer(40, 0) if ln == 'Via3' else LI[ln]
            mcache[k] = db.Region(c.begin_shapes_rec(lay)).merged().transformed(pl[1]) if c else db.Region()
        return mcache[k]
    def pins(n, p):
        pl = placed(n)
        if not pl: return []
        m, t, bb = pl; info = MJ.get(m, {}); o = info.get('origin', [0, 0])
        return [(ln, t*db.Box(um(r[0]+o[0]), um(r[1]+o[1]), um(r[2]+o[0]), um(r[3]+o[1]))) for ln, r in info.get('pins', {}).get(p, [])]
    def pin_of(n, net):
        ps = [p for (i, p) in nets.get(net, []) if i == n]
        if (n, net) in PIN_SEL and PIN_SEL[(n, net)] in ps: return PIN_SEL[(n, net)]
        if net in ('VDD', 'VSS'): ps = [p for p in ps if p.upper().startswith(net)] or []     # supply pins, not tie-offs (EN, SE tied low)
        return ps[0] if ps else None
    blk_boxes = {n: db.Box(*[um(v) for v in b['bbox']]) for n, b in man['blocks'].items()}
    ringr = (g['ring']['VDD'] + g['ring']['VSS']).merged()
    outside = db.Region(db.Box(-um(10), -um(10), um(C.DIE[2]+10), um(C.DIE[3]+10))) - db.Region(core)
    digi = man['blocks'].get('digital', {}).get('bbox')
    digr = db.Region(db.Box(*[um(v) for v in digi]).enlarged(um(3), um(3))) if digi else db.Region()
    ft = ly.find_layer(75, 0)
    mim = db.Region(top.begin_shapes_rec(ft)).merged().sized(um(2.3)) if ft is not None else db.Region()
    base_obs = {'Metal5': (avoid['Metal5'] + ringr.sized(um(3)) + outside + digr).merged(),
                'Metal4': (avoid['Metal4'] + ringr.sized(um(3)) + outside + digr + mim).merged()}
    nx = int(math.ceil((core.right-core.left)/um(G))); ny = int(math.ceil((core.top-core.bottom)/um(G)))
    X0, Y0 = core.left, core.bottom; GU = um(G)

    def raster(reg):
        """cells whose centre lies in reg"""
        a = np.zeros((nx, ny), dtype=bool)
        for poly in reg.each():
            for tz in poly.decompose_trapezoids(1):
                b = tz.bbox()
                i0 = max(0, int(math.ceil((b.left-X0)/GU-0.5))); i1 = min(nx, int(math.floor((b.right-X0)/GU-0.5))+1)
                j0 = max(0, int(math.ceil((b.bottom-Y0)/GU-0.5))); j1 = min(ny, int(math.floor((b.top-Y0)/GU-0.5))+1)
                if i1 > i0 and j1 > j0: a[i0:i1, j0:j1] = True
        return a

    def route(free, src, dst):
        """free / src / dst: {layer: bool raster}. Dijkstra on (layer, axis, cell) states; returns [(layer, i, j), ...] or None"""
        cells = {}; idx = {}; N = {}; off = {}; tot = 0
        for ln in LAYERS:
            f = free[ln] | src[ln] | dst[ln]; c = np.argwhere(f); cells[ln] = c; N[ln] = len(c)
            ix = -np.ones((nx, ny), dtype=np.int64); ix[c[:, 0], c[:, 1]] = np.arange(len(c)); idx[ln] = ix
            off[ln] = tot; tot += 2*len(c)
        rows, cols, w = [], [], []
        for ln in LAYERS:
            ix = idx[ln]; n_ = N[ln]; o = off[ln]
            for ax, (di, dj) in enumerate(((1, 0), (0, 1))):
                a = ix[:nx-di, :ny-dj]; b = ix[di:, dj:]; ok = (a >= 0) & (b >= 0); u = a[ok]; v = b[ok]; s = o+ax*n_
                rows += [u+s, v+s]; cols += [v+s, u+s]; w += [np.full(len(u), G*LCOST[ln])]*2
            r_ = np.arange(n_)
            rows += [r_+o, r_+o+n_]; cols += [r_+o+n_, r_+o]; w += [np.full(n_, TURN)]*2
        a5, a4 = idx['Metal5'], idx['Metal4']; both = (a5 >= 0) & (a4 >= 0); u = a5[both]; v = a4[both]
        for ax in (0, 1):
            s5 = off['Metal5']+ax*N['Metal5']; s4 = off['Metal4']+ax*N['Metal4']
            rows += [u+s5, v+s4]; cols += [v+s4, u+s5]; w += [np.full(len(u), VIA_COST)]*2
        A = sp.csr_matrix((np.concatenate(w), (np.concatenate(rows), np.concatenate(cols))), shape=(tot, tot))
        def nodes(m):
            out = []
            for ln in LAYERS:
                k = idx[ln][m[ln]]; k = k[k >= 0]
                out += [k+off[ln], k+off[ln]+N[ln]]
            return np.concatenate(out) if out else np.zeros(0, dtype=np.int64)
        s_ = nodes(src); d_ = nodes(dst)
        if len(s_) == 0 or len(d_) == 0: return None
        dist, pred, _ = csgraph.dijkstra(A, directed=True, indices=s_, min_only=True, return_predecessors=True)
        k = int(np.argmin(dist[d_]))
        if not np.isfinite(dist[d_[k]]): return None
        node = d_[k]; path = []
        while node >= 0:
            ln = 'Metal5' if node < off['Metal4'] else 'Metal4'; r_ = (node-off[ln]) % N[ln]
            c = cells[ln][r_]; t = (ln, int(c[0]), int(c[1]))
            if not path or path[-1] != t: path.append(t)
            node = pred[node]
        return path[::-1]

    def path_rects(path, W):
        """straight runs of the path per layer as rectangles W wide (centre line through the cell centres)"""
        out = {ln: db.Region() for ln in LAYERS}; h = um(W/2)//10*10
        cen = lambda c: (X0+int((c[1]+0.5)*GU), Y0+int((c[2]+0.5)*GU))
        def key(a, b): return (a[0], 'h' if a[2] == b[2] and a[0] == b[0] else 'v' if a[0] == b[0] else 'x')
        runs = []; st = 0
        for k in range(1, len(path)):
            if k == len(path)-1 or key(path[k-1], path[k]) != key(path[k], path[k+1]): runs.append((path[st], path[k])); st = k
        if not runs: runs = [(path[0], path[0])]
        for a, b in runs:
            (xa, ya), (xb, yb) = cen(a), cen(b)
            box = db.Box(min(xa, xb)-h, min(ya, yb)-h, max(xa, xb)+h, max(ya, yb)+h)
            out[a[0]].insert(box)
            if b[0] != a[0]: out[b[0]].insert(db.Box(xb-h, yb-h, xb+h, yb+h))
        return {ln: r.merged() for ln, r in out.items()}

    def other_obstacles(n, box, ln):
        """obstacles on layer ln near box, without instance n's own metal / halo"""
        win = db.Region(box.enlarged(um(60), um(60)))
        pads_ = db.Region([db.Box(*[um(x) for x in r]).enlarged(um(5), um(5)) for k, v in PADS['pads'].items() if k != n for r in v['footprint']])
        own_ = db.Region([b.enlarged(um(3.5), um(3.5)) for (i_, p_) in nets.get(cur_net[0], []) for l_, b in pins(i_, p_)])
        o = (ringr.sized(um(3)) + pads_ + ((g['_pinwin'][ln] & win) - own_) + taken[ln].sized(um(3)) + digr + outside) & win
        if ln == 'Metal4': o += mim & win
        for k, b in blk_boxes.items():
            if k == n or k == 'digital' or not b.enlarged(um(65), um(65)).overlaps(box): continue
            o += cell_m(k, ln).sized(um(2.5)) & win
            if man['blocks'][k]['master'] in C.NO_OVER: o += db.Region(b.enlarged(um(8), um(8))) & win
        for bd in bars:
            if bd['net'] != cur_net[0]: o += (bd['region'] if ln == 'Metal5' else bd['m4']).sized(um(3)) & win
        return o.merged()

    def landing(n, net):
        """per layer: same-net metal of the pin, carve (legal area near the pin), target; Metal4 pin boxes for Via4 landings"""
        p = pin_of(n, net); sh = pins(n, p) if p else []
        if not sh: return None
        m, t, bb = placed(n)
        p4 = db.Region([b for ln, b in sh if ln == 'Metal4']); p5 = db.Region([b for ln, b in sh if ln == 'Metal5'])
        m5 = cell_m(n, 'Metal5'); m4 = cell_m(n, 'Metal4'); v4 = cell_m(n, 'Via4')
        same = {'Metal5': (m5.interacting(p5) + m5.interacting(v4 & p4)).merged(), 'Metal4': m4.interacting(p4).merged() if not p4.is_empty() else db.Region()}
        cor = db.Region()
        for ln, b in sh:
            dl, dr, dbt, dtp = b.left-bb.left, bb.right-b.right, b.bottom-bb.bottom, bb.top-b.top
            e = min(dl, dr, dbt, dtp); o = um(16)
            # every side (the carve removes the blocked ones); a no-route-over (RF) block only on its nearest edge
            sides = [e] if (m in C.NO_OVER or not LP['all_sides']) else [dl, dr, dbt, dtp]
            for e_ in sides:
                if e_ == dl: cor.insert(db.Box(bb.left-o, b.bottom, b.right, b.top))
                if e_ == dr: cor.insert(db.Box(b.left, b.bottom, bb.right+o, b.top))
                if e_ == dbt: cor.insert(db.Box(b.left, bb.bottom-o, b.right, b.top))
                if e_ == dtp: cor.insert(db.Box(b.left, b.bottom, b.right, bb.top+o))
                if m in C.NO_OVER or not LP['all_sides']: break
        info_ = MJ.get(m, {}); o_ = info_.get('origin', [0, 0])
        opins = db.Region([t*db.Box(um(r[0]+o_[0]), um(r[1]+o_[1]), um(r[2]+o_[0]), um(r[3]+o_[1])).enlarged(um(LP['opin']), um(LP['opin']))
                           for q, lst in info_.get('pins', {}).items() if q != p for ln_, r in lst]) - db.Region([b for ln_, b in sh]).sized(um(0.5))   # 1 um round the cell's other pins
        L = dict(pin=p, same=same, carve={}, tgt={}, bbox=bb, vialand=db.Region(), via3land=db.Region(), pinreg={'Metal5': p5, 'Metal4': p4})
        for ln, b in sh:
            if ln == 'Metal3' and min(b.width(), b.height()) >= um(1.8) and (cell_m(n, 'Metal4') & db.Region(b)).is_empty() and (cell_m(n, 'Via3') & db.Region(b)).is_empty():
                L['via3land'].insert(b)
        for ln in LAYERS:
            other = (cell_m(n, ln) - same[ln]).merged()
            cv = ((cor + same[ln].sized(um(3))) - other.sized(um(LP['own'])) - other_obstacles(n, bb, ln) - opins).merged()      # 0.7 um to the cell's own other metal (MT.2b 0.6): RF supply stubs sit 1 um apart
            cv += same[ln] & cv.sized(um(5))
            L['carve'][ln] = cv.merged()
            pl = p5 if ln == 'Metal5' else (p4 + L['via3land'])
            if ln == 'Metal5':       # Metal5 over a Metal4 pin (Via4 landing) where the block has no Metal5 / Via4 there
                for b in p4.each():
                    bb_ = b.bbox()
                    if min(bb_.width(), bb_.height()) >= um(0.6) and (v4 & db.Region(bb_)).is_empty() and (m5 & db.Region(bb_)).is_empty():      # thin strips get a single row of cuts
                        L['vialand'].insert(bb_)
                pl = pl + L['vialand']
            L['tgt'][ln] = ((pl.sized(um(2)) & (L['carve'][ln] + same[ln])) - opins).merged()
            L['pinreg'][ln] = pl
        return L

    def via_cells(region, cell, lay=None):
        """Via4 cuts on the global 620 nm lattice (as kl_place.via_fill), 0.5 um inside region"""
        n = 0; L_ = L_V4 if lay is None else lay
        for poly in region.merged().each():
            for tz in poly.decompose_trapezoids(1):
                full = tz.bbox(); b = full.enlarged(-um(0.5), -um(0.5))
                if b.width() >= 260 and b.height() >= 260:
                    ox = -(-b.left//620)*620; oy = -(-b.bottom//620)*620
                    for x in range(ox, b.right-260+1, 620):
                        for y in range(oy, b.top-260+1, 620): cell.shapes(L_).insert(db.Box(x, y, x+260, y+260)); n += 1
                elif min(full.width(), full.height()) >= 600:      # thin strip (0.6-1.3 um): one centred row, 0.17 um enclosure min
                    horiz = full.width() >= full.height(); Lh = (full.width() if horiz else full.height()) - 1000
                    k = max(0, Lh//620 + 1) if Lh >= 260 else 0
                    s0 = (full.left if horiz else full.bottom) + 500; c0 = ((full.bottom+full.top)//2 if horiz else (full.left+full.right)//2) - 130
                    for j in range(k):
                        a = (s0 + j*620)//5*5; c = c0//5*5
                        cell.shapes(L_).insert(db.Box(a, c, a+260, c+260) if horiz else db.Box(c, a, c+260, a+260)); n += 1
        return n

    taken = {ln: db.Region() for ln in LAYERS}
    cur_net = ['']
    if mode == 'plates':
        return _plates(g, locals())
    for net in sorted(spec, key=lambda k: -spec[k]['design']):
        S = spec[net]; cur_net[0] = net
        sws = [s for s in S['sw'] if s in man['blocks']]
        if not sws: rep[net] = dict(error='no switch placed'); continue
        own_bar = next((bd for bd in bars if bd['net'] == net), None)
        allowed = {ln: (db.Region(core) - (base_obs[ln] + taken[ln].sized(um(3)))).merged() for ln in LAYERS}
        src_land = {s: L for s in sws for L in [landing(s, net)] if L}
        loads = {n: dict(L, mA=mA) for n, mA in S['loads'].items() if placed(n) for L in [landing(n, net)] if L}
        scale = S['design']/max(1e-9, sum(S['loads'].values()))
        A_land = {}
        for ln in LAYERS:
            la = db.Region()
            for L in list(src_land.values())+list(loads.values()): la += L['carve'][ln]
            if own_bar is not None and ln == 'Metal5':
                la += (own_bar['region'].sized(um(3)) - other_obstacles(None, own_bar['region'].bbox(), ln)) + own_bar['region']
            A_land[ln] = (allowed[ln] + la).merged()
        if g['os'].environ.get('TRUNK_DEBUG') == net:
            dl = db.Layout(); dl.dbu = 0.001; dc = dl.create_cell('dbg')
            for k_, r_ in ((1, allowed['Metal5']), (2, allowed['Metal4']), (4, sum((L['tgt']['Metal5'] + L['tgt']['Metal4'] for L in loads.values()), db.Region())),
                           (3, sum((L['same']['Metal5'] + L['same']['Metal4'] for L in src_land.values()), db.Region()))):
                dc.shapes(dl.layer(k_, 0)).insert(r_)
            dl.write('/run/trunk_debug.gds')
        s0 = src_land.get(sws[0])
        src0 = {'Metal5': ((own_bar['region'] if own_bar else db.Region()) + (s0['same']['Metal5'] if s0 else db.Region())).merged(),
                'Metal4': s0['same']['Metal4'] if s0 else db.Region()}
        src_zone = {ln: (src0[ln] + (s0['carve'][ln] if s0 else db.Region())).merged() for ln in LAYERS}
        sbox = (src0['Metal5'] + src0['Metal4']).bbox()
        width = {}
        for n, L in loads.items():
            c0 = sbox.center(); c1 = (L['tgt']['Metal5'] + L['tgt']['Metal4']).bbox().center()
            Lm = 1.2*fu(abs(c0.x-c1.x)+abs(c0.y-c1.y)); I = L['mA']*scale
            width[n] = min(W_MAX, max(3.0, J_TARGET*I, RS['Metal5']*Lm*I/(0.6*S['allow'])))
        for s in sws[1:]:            # a further switch of the island: path sized for its share
            if s in src_land: width[s] = min(W_MAX, max(3.0, J_TARGET*S['design']/len(sws)))
        ecache = {}
        def eroded(ln, W):
            k = (ln, round(W, 1))
            if k not in ecache: ecache[k] = allowed[ln].sized(-um(W/2))
            return ecache[k]
        res = None
        for it in range(3):
            tr = {ln: db.Region() for ln in LAYERS}; pathlen = {}; unrouted = []; vias = db.Region()
            for n in sorted(width, key=lambda k: -width[k]):
                L = loads.get(n) or src_land.get(n)
                tgt = {ln: raster(L['tgt'][ln] if n in loads else L['same'][ln]) for ln in LAYERS}
                srcm = {ln: raster(src0[ln]) & ~tgt[ln] for ln in LAYERS}
                P = None
                for W in (width[n], max(3.0, width[n]/2), max(3.0, width[n]/4)):
                    near = {ln: ((L['carve'][ln] + L['tgt'][ln] + src_zone[ln]).sized(um(W/2+8)) & A_land[ln]) for ln in LAYERS}
                    free = {ln: raster((eroded(ln, W) + near[ln]).merged()) for ln in LAYERS}
                    P = route(free, srcm, tgt)
                    if P is not None: break
                if P is None: unrouted.append(n); continue
                width[n] = W
                rr = path_rects(P, W)
                for ln in LAYERS: tr[ln] += rr[ln] & A_land[ln]
                pathlen[n] = dict(um=round(G*len(P)), m4_um=round(G*sum(1 for q in P if q[0] == 'Metal4')))
            for ln in LAYERS:
                t_ = tr[ln].merged().sized(-um(0.6)).sized(um(0.6)).merged()      # no sliver under 1.2 um
                tr[ln] = t_
            # keep what is joined to the source (through either layer)
            seed5 = src0['Metal5']; seed4 = src0['Metal4']; k5 = tr['Metal5'].interacting(seed5); k4 = tr['Metal4'].interacting(seed4)
            for _ in range(20):
                ov = (tr['Metal4'] & tr['Metal5']).sized(-um(0.75))
                n5 = (k5 + tr['Metal5'].interacting(ov.interacting(k4))).merged(); n4 = (k4 + tr['Metal4'].interacting(ov.interacting(k5 + seed5))).merged()
                if n5.area() == k5.area() and n4.area() == k4.area(): break
                k5, k4 = n5, n4
            tr = {'Metal5': k5.merged(), 'Metal4': k4.merged()}
            landed = db.Region()
            for n_ in list(loads)+list(src_land): landed += cell_m(n_, 'Via4')
            vias = ((tr['Metal4'] & tr['Metal5']) - landed.sized(um(1.0))).merged()
            res = solve(np, sp, spl, db, um, tr, vias, sws, src_land, own_bar, loads, scale, man)
            bad = [n for n, d in res['loads'].items() if math.isfinite(d['drop_mV']) and d['drop_mV'] > S['allow'] and n in width and width[n] < W_MAX]
            if not bad: break
            for n in bad: width[n] = min(W_MAX, width[n]*1.3*res['loads'][n]['drop_mV']/S['allow'])
        t5, t4 = tr['Metal5'], tr['Metal4']
        if t5.is_empty() and t4.is_empty(): rep[net] = dict(res or {}, error='no trunk drawn', unrouted=unrouted); continue
        # MSLOT holes where the Metal5 is wider than 28 um
        bb_ = t5.bbox(); holes = db.Region()
        for xh in range(bb_.left+um(12), bb_.right, um(24)):
            for yh in range(bb_.bottom+um(12), bb_.top, um(24)): holes.insert(db.Box(xh-um(1.5), yh-um(1.5), xh+um(1.5), yh+um(1.5)))
        t5 = (t5 - (holes & t5.sized(-um(14)).sized(um(14)).sized(-um(3)))).merged()
        vl = db.Region()
        for L in loads.values(): vl += L['vialand'] & t5
        joined = [(n, L['pin']) for n, L in loads.items() if not ((t5 & L['tgt']['Metal5']) + (t4 & L['tgt']['Metal4'])).is_empty()]
        joined += [(n, L['pin']) for n, L in src_land.items() if (n != sws[0] or own_bar is None) and not ((t5 & L['same']['Metal5']) + (t4 & L['same']['Metal4'])).is_empty()]
        if own_bar is not None:
            own_bar['region'] = (own_bar['region'] + t5).merged()
            own_bar['m4'] = (own_bar['m4'] + vl).merged()
            own_bar['vias'] = list(own_bar['vias']) + [j for j in joined if j not in [tuple(v) for v in own_bar['vias']]]
        elif not t5.is_empty():
            bars.append(dict(net=net, rects=[], expose=True, vias=joined, region=t5, m4=vl.merged(), merged=True))
        else:
            rep[net] = dict(res or {}, error='Metal4-only trunk: no bar pin (not drawn)', unrouted=unrouted); continue
        pdn.shapes(LI['Metal4']).insert(t4); nv = via_cells(vias, pdn)
        avoid['Metal5'] = (avoid['Metal5'] + t5.sized(um(2.5))).merged()
        avoid['Metal4'] = (avoid['Metal4'] + (t4 + vl).sized(um(2.5))).merged()
        taken['Metal5'] += t5; taken['Metal4'] += t4 + vl
        for poly in (t5.sized(um(0.6)) - t5).merged().each():
            for tz in poly.decompose_trapezoids(1):
                b = tz.bbox(); _BLK.append(('trunk_halo', (fu(b.left), fu(b.bottom), fu(b.right), fu(b.top)), ('Metal5',)))
        res.update(widths_um={k: round(v, 1) for k, v in width.items()}, path=pathlen, unrouted=unrouted, joined=[f'{a}.{b}' for a, b in joined],
                   not_joined=[n for n in list(loads)+sws if n not in [a for a, b in joined] and not (n == sws[0] and own_bar is not None)],
                   m5_mm2=round(t5.area()/1e12, 4), m4_mm2=round(t4.area()/1e12, 4), via4_transitions=nv, design_mA=S['design'], allow_mV=S['allow'])
        rep[net] = res


def solve(np, sp, spl, db, um, tr, vias, sws, src_land, own_bar, loads, scale, man):
    """two-layer resistive mesh of the trunk (2 um cells); switches as nodes behind R_SW; loads at design current"""
    g = 2.0; GU = um(g)
    cond = {'Metal5': (tr['Metal5'] + (own_bar['region'] if own_bar else db.Region())).merged(), 'Metal4': tr['Metal4'].dup()}
    for s, L in src_land.items():
        for ln in LAYERS: cond[ln] += L['same'][ln]
    for n, L in loads.items():
        cond['Metal4'] += L['same']['Metal4'] & tr['Metal4'].sized(um(4))
    bb = (cond['Metal5'] + cond['Metal4']).bbox()
    nx = max(1, int(math.ceil(bb.width()/GU))); ny = max(1, int(math.ceil(bb.height()/GU)))
    def ras(reg):
        a = np.zeros((nx, ny), dtype=bool)
        for poly in (reg & db.Region(bb)).each():
            for tz in poly.decompose_trapezoids(1):
                b = tz.bbox()
                i0 = max(0, int(math.ceil((b.left-bb.left)/GU-0.5))); i1 = min(nx, int(math.floor((b.right-bb.left)/GU-0.5))+1)
                j0 = max(0, int(math.ceil((b.bottom-bb.bottom)/GU-0.5))); j1 = min(ny, int(math.floor((b.top-bb.bottom)/GU-0.5))+1)
                if i1 > i0 and j1 > j0: a[i0:i1, j0:j1] = True
        return a
    m = {ln: ras(cond[ln]) for ln in LAYERS}; idx = {}; cells = {}; off = {}; tot = 0
    for ln in LAYERS:
        c = np.argwhere(m[ln]); ix = -np.ones((nx, ny), dtype=np.int64); ix[c[:, 0], c[:, 1]] = np.arange(len(c)) + tot
        idx[ln] = ix; cells[ln] = c; off[ln] = tot; tot += len(c)
    NS = len(sws); NT = tot+NS
    rows, cols, vals = [], [], []
    def link(u, v, gv):
        rows.extend([u, v, u, v]); cols.extend([v, u, u, v]); vals.extend([-gv, -gv, gv, gv])
    for ln in LAYERS:
        ix = idx[ln]; gc = 1.0/RS[ln]
        for di, dj in ((1, 0), (0, 1)):
            a = ix[:nx-di, :ny-dj]; b = ix[di:, dj:]; ok = (a >= 0) & (b >= 0); u = a[ok]; v = b[ok]
            link(u, v, gc*np.ones(len(u)))
    # Via4: the trunk's own transitions, and the landed cells' own Via4 (switch plates onto their VISL pins, Metal4 pins)
    vr = vias.dup()
    for s, L in src_land.items(): vr += L['same']['Metal5'] & L['same']['Metal4']
    vm = ras(vr) & m['Metal5'] & m['Metal4']; u = idx['Metal5'][vm]; v = idx['Metal4'][vm]
    link(u, v, np.full(len(u), 1.0/R_VIA_CELL))
    sw_cells = {}
    for k, s in enumerate(sws):
        node = tot+k; c = []
        if s in src_land:
            for ln in LAYERS: x = idx[ln][ras(src_land[s]['same'][ln]) & m[ln]]; c.append(x[x >= 0])
        if k == 0 and own_bar is not None: x = idx['Metal5'][ras(own_bar['region'].interacting(src_land[s]['same']['Metal5']) if s in src_land else own_bar['region']) & m['Metal5']]; c.append(x[x >= 0])
        c = np.unique(np.concatenate(c)) if c else np.zeros(0, dtype=np.int64); sw_cells[s] = c
        if len(c): link(c, np.full(len(c), node), np.full(len(c), 1e4/len(c)))
        rows.append(np.array([node])); cols.append(np.array([node])); vals.append(np.array([1.0/R_SW.get(man['blocks'][s]['master'], 0.3)]))
    Y = sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(NT, NT))
    inj = np.zeros(NT); land = {}
    for n, L in loads.items():
        c = np.concatenate([idx[ln][ras(L['tgt'][ln] & tr[ln]) & m[ln]] for ln in LAYERS]); c = c[c >= 0]
        if len(c) == 0: continue
        land[n] = c; inj[c] -= L['mA']*scale*1e-3/len(c)
    lab = csgraph.connected_components(Y, directed=False)[1]
    live = {lab[tot+k] for k in range(NS) if len(sw_cells[sws[k]])}
    keep = np.isin(lab, list(live)); kk = np.where(keep)[0]
    V = np.full(NT, np.nan)
    if len(kk): V[kk] = spl.spsolve(Y[kk][:, kk].tocsc(), inj[kk])
    out = dict(loads={}, switches={})
    vref = V[tot]
    for k, s in enumerate(sws):
        r_ = R_SW.get(man['blocks'][s]['master'], 0.3)
        out['switches'][s] = dict(mA=round(float(-V[tot+k]/r_*1e3), 1) if np.isfinite(V[tot+k]) else 0.0, joined=bool(len(sw_cells[s])) and bool(np.isfinite(V[tot+k])))
    for n, L in loads.items():
        if n not in land or not np.isfinite(V[land[n]]).any(): out['loads'][n] = dict(mA=round(L['mA']*scale, 1), drop_mV=float('inf'), note='not connected'); continue
        out['loads'][n] = dict(mA=round(L['mA']*scale, 1), drop_mV=round(float((vref-np.nanmin(V[land[n]]))*1e3), 2))
    neck = np.zeros((nx, ny), dtype=bool)
    for n, L in loads.items(): neck |= ras((L['tgt']['Metal5'] + L['tgt']['Metal4']).sized(um(20)))
    for s, L in src_land.items(): neck |= ras((L['same']['Metal5'] + L['same']['Metal4']).sized(um(20)))
    for ln in LAYERS:
        Vg = np.full((nx, ny), np.nan); c = cells[ln]; Vg[c[:, 0], c[:, 1]] = V[idx[ln][c[:, 0], c[:, 1]]]
        jx = np.zeros((nx, ny)); jy = np.zeros((nx, ny))
        jx[:-1] = np.nan_to_num(np.abs(np.diff(Vg, axis=0))/g/RS[ln]*1e3); jy[:, :-1] = np.nan_to_num(np.abs(np.diff(Vg, axis=1))/g/RS[ln]*1e3)
        J = np.hypot(jx, jy); body = J[m[ln] & ~neck]; nk = J[m[ln] & neck]
        out[f'J_{ln}'] = dict(body_max=round(float(body.max()), 2) if body.size else 0, body_p99=round(float(np.percentile(body, 99)), 2) if body.size else 0,
                              neck_max=round(float(nk.max()), 2) if nk.size else 0)
    out.update(cells=int(tot), floating_cells=int(tot-keep[:tot].sum()))
    return out


# ---------------------------------------------------------------------------------------- grid plates (PDS-25 finding 2)
# Heavy supply pins get a drawn plate from the pad-fed grid (kl_place 'live' metal of the same net) instead of a 0.56 um router
# hook: same router as the trunks, width 1 um per 2 mA (>= 3 um), Via4 arrays where the plate changes layer or lands on the
# other grid layer; drawn into pt_pdn. kl_place skips the router hook of every plated pin (place.json 'grid_plates').
# Currents (mA): switch VDD = island design current (PDS-19 / PDS-20, two isw_wired share), load VDD/VSS = worst (README rail
# plan, hook_em.py tables); every block supply pin above 2 mA.
HEAVY = {
 'rf': {('isw_lod', 'VDD'): 74.1, ('isw_rf_rx', 'VDD'): 43.6, ('isw_debug', 'VDD'): 40.0, ('isw_pll', 'VDD'): 30.7, ('isw_rf_tx', 'VDD'): 45.8,
        ('isw_rf_tx_b', 'VDD'): 45.8, ('isw_lo', 'VDD'): 28.1, ('isw_conv', 'VDD'): 18.7,
        ('lo_txbuf', 'VSS'): 59.3, ('lo_mmd', 'VSS'): 34.8, ('lo_vreg', 'VSS'): 27.5, ('rfdriver', 'VSS'): 24.3, ('lna', 'VSS'): 21.4,
        ('pll_vreg2', 'VSS'): 20.9, ('lo_ext', 'VSS'): 13.7, ('vco_replica', 'VSS'): 11.8, ('lo_mmd_qdum', 'VSS'): 10.0, ('lo_obs', 'VSS'): 8.0,
        ('lo_obs_q', 'VSS'): 8.0, ('adc_i', 'VSS'): 6.3, ('adc_q', 'VSS'): 6.3, ('bbfilter_i', 'VSS'): 5.3, ('bbfilter_q', 'VSS'): 5.3,
        ('clk_obs', 'VSS'): 5.1, ('rx_aux_clk', 'VSS'): 5.1, ('rx_ref_in', 'VDD'): 4.6, ('rx_ref_in', 'VSS'): 4.6, ('rxmix_i', 'VSS'): 3.1,
        ('rxmix_q', 'VSS'): 3.1, ('prescale', 'VSS'): 2.4, ('prescale_hf', 'VSS'): 2.4, ('prescale_conv', 'VSS'): 2.4, ('dac_i', 'VSS'): 2.3, ('dac_q', 'VSS'): 2.3},
 'wired': {('isw_wired_cap', 'VDD'): 72.9, ('isw_wired_tx_a', 'VDD'): 65.7, ('isw_wired_tx_b', 'VDD'): 65.7, ('isw_wired_rx', 'VDD'): 30.9,
           ('isw_pll', 'VDD'): 29.4, ('isw_debug', 'VDD'): 40.0, ('wrx_cap', 'VSS'): 46.6, ('wiredtx', 'VSS'): 60.0, ('ptrim', 'VSS'): 21.0,
           ('usb_txdrv', 'VSS'): 20.0, ('pll_vreg2', 'VSS'): 20.9, ('vco_replica', 'VSS'): 11.8, ('slicer', 'VSS'): 9.8, ('ctle', 'VSS'): 5.3,
           ('clk_obs', 'VSS'): 5.1, ('rx_aux_clk', 'VSS'): 5.1, ('rx_wtx_ext', 'VSS'): 5.1, ('rx_ref_in', 'VDD'): 4.6, ('rx_ref_in', 'VSS'): 4.6,
           ('detect', 'VSS'): 2.4, ('prescale', 'VSS'): 2.4, ('prescale_hf', 'VSS'): 2.4, ('wordclk_rx', 'VSS'): 2.4}}
PIN_TABLE = '/repo/projects/programmable_transceiver_platform/integration/chips/{chip}/pin_currents.json'
PIN_SEL = {}                # (inst, net) -> the supply pin the table names (heaviest of the net on that block)


def heavy(chip, PADS=None):
    """(inst, net) -> mA for every block supply pin above PLATE_MIN_MA: the power owner's per-pin table (chips/<chip>/
    pin_currents.json: worst DC at 85 C; isw_* VSS at their turn-off peak) when present, else the HEAVY table above.
    Pad supply pins (provider ring) and the digital macro (its own straps) are not plated."""
    import os as _os
    f = PIN_TABLE.format(chip=chip)
    if not _os.path.exists(f): return dict(HEAVY.get(chip, {}))
    out = {}
    for r in json.load(open(f))['rows']:
        if r['kind'] != 'supply' or r['net'] not in ('VDD', 'VSS') or r['inst'] in ('digital', 'host') or (PADS and r['inst'] in PADS['pads']): continue
        ma = max(r['avg_ma'], r.get('peak_ma') or 0) if r['master'].startswith('isw') and r['net'] == 'VSS' else r['avg_ma']
        k = (r['inst'], r['net'])
        if ma > out.get(k, 0): out[k] = ma; PIN_SEL[k] = r['pin']
    return out


PLATE_DROP_MV = 10.0
PLATE_MIN_MA = 0.5       # every supply pin above 0.5 mA at 85 C on a plate or a drawn landing (coordinator ruling 2026-11-28)


def _plates(g, h):
    db = h['db']; um = h['um']; fu = h['fu']; man = h['man']; pdn = h['pdn']; LI = h['LI']; avoid = h['avoid']
    rep = h['rep']; cur_net = h['cur_net']; landing = h['landing']; raster = h['raster']; route = h['route']; path_rects = h['path_rects']
    placed = h['placed']; core = h['core']; G_ = G; metal = g['metal']; live = g['live']; via_cells = h['via_cells']
    done = set()
    def one(n, net, mA):
        if placed(n) is None or net not in live: return
        if mA < PLATE_MIN_MA: rep[f'{n}.{net}'] = dict(mA=mA, error=f'below {PLATE_MIN_MA} mA: router hook'); return
        cur_net[0] = net
        L = landing(n, net)
        if L is None: rep[f'{n}.{net}'] = dict(mA=mA, error='no pin'); return
        other = 'VSS' if net == 'VDD' else 'VDD'
        obs = {ln: (avoid[ln] + metal[(other, ln)].sized(um(2.5)) + h['ringr'].sized(um(3)) + h['outside'] + h['digr'] + (h['mim'] if ln == 'Metal4' else db.Region())).merged() for ln in LAYERS}
        win = L['bbox'].enlarged(um(1000), um(1000))
        allowed = {ln: (db.Region(win) & db.Region(core)) - obs[ln] for ln in LAYERS}
        if _RES[0] is not None:       # reserved landing corridors are in avoid (the grid gave way): free for the plate
            for ln in LAYERS: allowed[ln] = (allowed[ln] + ((_RES[0] & db.Region(win)) - h['other_obstacles'](n, L['bbox'], ln) - metal[(other, ln)].sized(um(2.5)))).merged()
        src = {ln: live[net][ln] & db.Region(win) for ln in LAYERS}
        og = {ln: metal[(other, ln)].sized(um(2.5)) for ln in LAYERS}
        for ln in LAYERS: L['carve'][ln] = L['carve'][ln] - og[ln]; L['tgt'][ln] = L['tgt'][ln] - og[ln]
        A = {ln: (allowed[ln] + L['carve'][ln] + src[ln]).merged() for ln in LAYERS}
        if g['os'].environ.get('PLATE_DEBUG') == f'{n}.{net}':
            dl = db.Layout(); dl.dbu = 0.001; dc = dl.create_cell('dbg')
            for k_, r_ in ((1, allowed['Metal5']), (2, allowed['Metal4']), (3, L['carve']['Metal5'] + L['carve']['Metal4']), (4, L['tgt']['Metal5'] + L['tgt']['Metal4']), (5, src['Metal5'])):
                dc.shapes(dl.layer(k_, 0)).insert(r_)
            dl.write('/run/plate_debug.gds')
        W0 = max(3.0, mA/2.0); P = None
        tgt = {ln: raster(L['tgt'][ln]) for ln in LAYERS}
        srcm = {ln: raster(src[ln]) & ~tgt[ln] for ln in LAYERS}
        # last rung: the drawn hook (coordinator ruling 2026-11-28 option 2), as narrow as EM allows (mA / 2 um, >= 1 um)
        for W in (W0, max(3.0, W0/2), 3.0, max(1.0, mA/2.0)):
            near = {ln: ((L['carve'][ln] + L['tgt'][ln]).sized(um(W/2+8)) & A[ln]) for ln in LAYERS}
            free = {ln: raster((allowed[ln].sized(-um(W/2)) + near[ln] + src[ln]).merged()) for ln in LAYERS}
            P = route(free, srcm, tgt)
            if P is not None: break
        if P is None: rep[f'{n}.{net}'] = dict(mA=mA, error='no path'); return
        rr = path_rects(P, W)
        sv = max(W, 2.0+math.sqrt(2.0*mA/2.6)); hv = um(sv/2)//10*10; cen = lambda q: (core.left+int((q[1]+0.5)*um(G_)), core.bottom+int((q[2]+0.5)*um(G_)))
        for a_, b_ in zip(P, P[1:]+[None]):
            if b_ is not None and a_[0] != b_[0] or b_ is None or a_ is P[0]:
                x_, y_ = cen(a_)
                for ln in LAYERS: rr[ln].insert(db.Box(x_-hv, y_-hv, x_+hv, y_+hv))
        pl = {ln: (rr[ln].merged() & A[ln]).merged().sized(-um(0.6)).sized(um(0.6)) for ln in LAYERS}
        for ln in LAYERS:       # no corner-to-corner touch with the grid (MT.1 / MT.2a at the lo_mmd VSS plate, 2026-11-26): overlap instead
            nb_ = (metal[(net, ln)] + L['pinreg'][ln] + L['same'][ln]).merged()      # all drawn grid metal of the net, floating pieces too
            fill_ = ((pl[ln].sized(um(0.4)) & nb_.sized(um(0.4))) & A[ln]).sized(-um(0.25)).sized(um(0.25))
            pl[ln] = (pl[ln] + fill_).merged().sized(-um(0.3)).sized(um(0.3)).merged()
            # point contacts of plate + neighbouring same-net metal (MT.1 / MT.2a at lo_mmd VSS, 2026-11-26): a 1 um square on each
            u_ = (pl[ln] + (nb_ & db.Region(pl[ln].bbox().enlarged(um(2), um(2))))).merged()
            for ep in u_.width_check(um(0.46 if ln == 'Metal5' else 0.32)).each():
                c_ = ep.bbox().center(); pl[ln] += db.Region(db.Box(c_.x-um(0.5), c_.y-um(0.5), c_.x+um(0.5), c_.y+um(0.5))) & A[ln]
            # self-touching corners inside the plate (via pad meets path corner, lo_mmd VSS 2026-11-26): closing by 0.25 um, unclipped
            # (the legal area keeps >= 2.5 um from other metal, so the closing never comes nearer than 2.25 um)
            pl[ln] = pl[ln].merged().sized(um(0.25)).sized(-um(0.25)).merged()
        # keep only the plate pieces joined to the pad-fed grid (same layer overlap, or Via4 between plate layers / onto the grid)
        k5 = pl['Metal5'].interacting(live[net]['Metal5']) + pl['Metal5'].interacting((pl['Metal5'] & live[net]['Metal4']).sized(-um(0.5)))
        k4 = pl['Metal4'].interacting(live[net]['Metal4']) + pl['Metal4'].interacting((pl['Metal4'] & live[net]['Metal5']).sized(-um(0.5)))
        for _ in range(10):
            ov = (pl['Metal4'] & pl['Metal5']).sized(-um(0.5))
            n5 = (k5 + pl['Metal5'].interacting(ov.interacting(k4))).merged(); n4 = (k4 + pl['Metal4'].interacting(ov.interacting(k5))).merged()
            if n5.area() == k5.area() and n4.area() == k4.area(): break
            k5, k4 = n5, n4
        pl = {'Metal5': k5.merged(), 'Metal4': k4.merged()}
        touch = sum(((pl[ln] & L['pinreg'][ln]).sized(-um(0.3))).area() for ln in LAYERS)
        if touch < um(1)*um(1):
            rep[f'{n}.{net}'] = dict(mA=mA, error='landing clipped'); return
        own_v = g['ly'].cell(placed(n)[0]); vown = h['cell_m'](n, 'Via4')
        vr = ((pl['Metal4'] & (pl['Metal5'] + live[net]['Metal5'])) + (pl['Metal5'] & live[net]['Metal4']) + (pl['Metal5'] & L['vialand'])) - vown.sized(um(1.0))
        for ln in LAYERS: pdn.shapes(LI[ln]).insert(pl[ln])
        nv = via_cells(vr, pdn)
        v3 = L['via3land'] & pl['Metal4']
        nv3 = via_cells(v3 - h['cell_m'](n, 'Via3').sized(um(1.0)), pdn, g['ly'].layer(40, 0)) if not v3.is_empty() else 0
        if not (pl['Metal5'] & L['vialand']).is_empty(): pdn.shapes(LI['Metal4']).insert(L['vialand'] & pl['Metal5'])
        for ln in LAYERS:
            avoid[ln] = (avoid[ln] + pl[ln].sized(um(2.5))).merged()
            live[net][ln] = (live[net][ln] + pl[ln]).merged(); metal[(net, ln)] = (metal[(net, ln)] + pl[ln]).merged()
        L5 = G_*sum(1 for q in P if q[0] == 'Metal5'); L4 = G_*sum(1 for q in P if q[0] == 'Metal4'); nvc = max(1, int((vr.area()/1e6)*2.6))
        nch = sum(1 for a_, b_ in zip(P, P[1:]) if a_[0] != b_[0]) + (1 if not (pl['Metal5'] & L['vialand']).is_empty() else 0)
        # Via4 only matters where the current changes layer (a Metal4-to-Metal4 plate carries none: isw_wired_tx 2026-11-28)
        drop = mA*(RS['Metal5']*L5/W + RS['Metal4']*L4/W) + (mA*4.5/max(1, nv/max(1, nch)) if nch else 0.0) + (mA*4.5/nv3 if nv3 else 0.0)
        em_ok = (nch == 0 or nv >= 2*mA*nch) and (nv3 == 0 or nv3 >= 2*mA) and mA/W <= 2.09
        if em_ok: done.add((n, L['pin'], net))      # an EM-short plate keeps its router hook in parallel
        rep[f'{n}.{net}'] = dict(mA=mA, pin=L['pin'], width_um=round(W, 1), len_m5_um=L5, len_m4_um=L4, via4=nv, via3=nv3, mA_per_um=round(mA/W, 2),
                                 mA_per_cut=round(mA/max(1, nv), 3), drop_mV=round(drop, 2), layer_changes=nch, em_ok=em_ok, hook_kept=not em_ok, ok=drop <= PLATE_DROP_MV and em_ok)
    for (n, net), mA in sorted(heavy(h['CHIP'], g['PADS']).items(), key=lambda kv: -kv[1]):
        one(n, net, mA)
        r_ = rep.get(f'{n}.{net}', {})
        if 'error' in r_ and not r_['error'].startswith('below'):      # never a hook where the earlier landing rules gave a plate
            first = r_['error']; saved = dict(LP); LP.update(LEGACY_LP)
            try: one(n, net, mA)
            finally: LP.clear(); LP.update(saved)
            r2 = rep.get(f'{n}.{net}', {})
            if 'error' not in r2: r2['landing'] = f'legacy rules (first try: {first})'
    return done


def face_inward(n, m, tr, MJ, C, db, um, bb):
    """Island switches whose VISL output faces the nearest core edge (the VDD side inward, so the island rail is boxed in
    against the core ring: pt_rf isw_lod / isw_lo / isw_debug, 2026-11-25) are mirrored about their own centre, perpendicular
    to that edge: VDD then faces the ring (G4) and VISL the island. Returns the (possibly mirrored) transformation."""
    if not m.startswith('isw') or 'VISL' not in MJ.get(m, {}).get('pins', {}): return tr
    info = MJ[m]; o = info.get('origin', [0, 0])
    vs = [tr*db.Box(um(r[0]+o[0]), um(r[1]+o[1]), um(r[2]+o[0]), um(r[3]+o[1])) for ln, r in info['pins']['VISL']]
    vx = sum(b.center().x for b in vs)/len(vs); vy = sum(b.center().y for b in vs)/len(vs)
    cx, cy = bb.center().x, bb.center().y; core = [um(v) for v in C.CORE]
    de = {'W': bb.left-core[0], 'E': core[2]-bb.right, 'S': bb.bottom-core[1], 'N': core[3]-bb.top}; e = min(de, key=de.get)
    if de[e] > um(150): return tr
    off = {'W': cx-vx, 'E': vx-cx, 'S': cy-vy, 'N': vy-cy}[e]
    if off < um(10): return tr
    if e in 'WE': return db.Trans(db.Trans.M90, db.Vector(bb.left+bb.right, 0))*tr
    return db.Trans(db.Trans.M0, db.Vector(0, bb.bottom+bb.top))*tr


def reserve(g):
    """Before the grid is cut (kl_place, ahead of the straps): the landing corridor of every plated supply pin (nearest block
    edge, pin length wide, 20 um out) + 2.5 um joins `avoid` on Metal4 and Metal5, so neither grid net's strap runs across it
    (pt_rf lo_mmd VSS: the VDD Metal5 row lay along the pin and no plate could reach it, 2026-11-28). Only the first pin of the
    net per block is reserved (the one _plates lands on: landing() also takes the first). place.json 'plate_reserve'."""
    db = g['db']; um = g['um']; man = g['man']; MJ = g['MJ']; C = g['C']; avoid = g['avoid']; nets = g['nets']
    res = db.Region(); out = []
    for (n, net), mA in heavy(g['CHIP'], g['PADS']).items():
        if mA < PLATE_MIN_MA or n not in man['blocks'] or man['blocks'][n]['master'] not in C.NO_OVER: continue      # RF blocks only: elsewhere the grid stays (small cells lost their source)
        b_ = man['blocks'][n]; t = db.Trans.from_s(b_['trans']); bb = db.Box(*[um(v) for v in b_['bbox']])
        info = MJ.get(b_['master'], {}); o = info.get('origin', [0, 0])
        ps = [PIN_SEL[(n, net)]] if (n, net) in PIN_SEL else [p for (i, p) in nets.get(net, []) if i == n and p.upper().startswith(net)]
        for p in ps[:1]:
            for ln, r in info.get('pins', {}).get(p, []):
                b = t*db.Box(um(r[0]+o[0]), um(r[1]+o[1]), um(r[2]+o[0]), um(r[3]+o[1]))
                d = {'W': b.left-bb.left, 'E': bb.right-b.right, 'S': b.bottom-bb.bottom, 'N': bb.top-b.top}; e = min(d, key=d.get)
                if d[e] > um(30): continue          # pin not at an edge: nothing to reserve outside the block
                ext = um(20)
                cor = {'W': db.Box(bb.left-ext, b.bottom, b.right, b.top), 'E': db.Box(b.left, b.bottom, bb.right+ext, b.top),
                       'S': db.Box(b.left, bb.bottom-ext, b.right, b.top), 'N': db.Box(b.left, b.bottom, b.right, bb.top+ext)}[e]
                cor = db.Region(cor) - (db.Region(bb) - db.Region(b.enlarged(um(1), um(1))))      # outside the block, plus the pin itself
                res += cor; out.append(dict(pin=f'{n}.{p}', net=net, edge=e))
    res = res.merged().sized(um(2.5))
    for ln in ('Metal4', 'Metal5'): avoid[ln] = (avoid[ln] + res).merged()
    man['plate_reserve'] = dict(pins=out, mm2=round(res.area()/1e12, 4))
    _RES[0] = res
