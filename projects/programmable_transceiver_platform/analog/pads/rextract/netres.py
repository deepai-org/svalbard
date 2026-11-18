#!/usr/bin/env python3
"""netres.py: net resistance from a GDS (GF180MCU, Metal1..Metal5 + Via1..Via4), for nets Magic's C-only extraction hides.

For each net of the spec: trace the connected Metal1..Metal5 / via shapes from a label (or a seed point), mesh the metal
(finite-volume resistor mesh on a rectilinear grid built from the polygon edges, refined to `max_step`), put one resistor
per via cut, and solve.  Output per net: the resistance between terminals (pairs), the narrowest metal cross-section and
the single-cut vias that carry at least `path_fraction` of the current, the largest per-cut current, and the exact
reduced terminal network (for insertion into a simulation model).

    python3 netres.py --gds X.gds --top CELL --spec spec.json --out result.json [--corner typ,high] [--tech gf180mcuD.tech]

spec.json: {"nets": [ {
    "name": "TERM_VCM",                         # result key
    "label": "TERM_VCM" | "seed": ["M4", x, y], # where the trace starts (label text on any metal layer/datatype)
    "clip": [x1, y1, x2, y2],                   # optional window (um): only metal inside is traced / meshed
    "max_step": 0.5,                            # mesh step limit (um)
    "path_fraction": 0.5,                       # a cross-section / via group is "on the path" if it carries >= this
    "min_width": 0.0, "min_cuts": 2,            # flags: narrowest on-path width below min_width, via group below min_cuts
    "terminals": [
        {"name": "pin", "layer": "M5", "box": [x1, y1, x2, y2]},         # all net metal of that layer in the box(es)
        {"name": "a", "layer": "M3", "boxes": [[...], [...]]},
        {"name": "lbl", "at_label": "TERM_VCM", "half": 0.25},          # small box at a label
        {"auto_contacts": "src", "window": [x1, y1, x2, y2]}             # one terminal per device terminal: the contact
    ],                                                                    # cuts (33/0) under net Metal1, grouped by the
                                                                          # diffusion-minus-poly / poly polygon they land on
    "survey": "pin",                           # optional: R from this terminal to every device terminal, summarised per kind
                                               # (nmos/pmos/ndiode/pdiode/ptap/ntap/gate/res), plus a pair to each kind shorted
    "groups": {"srcP": {"prefix": "src", "window": [...], "ballast_ohm": 1300}},   # several terminals used together (or "members": [names]):
                                                                          # shorted, or each through ballast_ohm to a common node
    "pairs": [["pin", "srcP"], ...]            # default: all pairs of the explicitly named terminals
} ] }

Resistances (Magic tech gf180mcuD.tech of the pinned iic-osic-tools image, section `extract`, style ngspice):
  typ  = `variants ()`            : resist allm1..allm4 90 mohm/sq (lines 3341-3345), allm5 40 (3347); contact m2c (Via1),
                                    m3c (Via2), via3, via4 4500 mohm per cut (3355-3358)
  high = `variants (hrhc),(hrlc)`: allm1..allm4 104 (3390-3394), allm5 49 (3396); m2c, m3c, via3, via4 15000 (3404-3407)
`--tech` re-reads the file and fails if it disagrees with these constants.
Not modelled: contact (diffusion / poly) resistance, the devices, current crowding inside a via cut, Via4 inside a MIM
top plate (75/0: those cuts connect Metal5 to the MIM top plate, not to Metal4, and are excluded from the trace).
"""
import argparse, json, re, sys, time
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spl
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree
import klayout.db as k

METAL = {'M1': 34, 'M2': 36, 'M3': 42, 'M4': 46, 'M5': 81}
VIA = {'V1': (35, 'M1', 'M2'), 'V2': (38, 'M2', 'M3'), 'V3': (40, 'M3', 'M4'), 'V4': (41, 'M4', 'M5')}
CONT, COMP, POLY, MIM, NWELL, NPLUS, PPLUS = 33, 22, 30, 75, 21, 32, 31
R = {'typ': dict(M1=.090, M2=.090, M3=.090, M4=.090, M5=.040, V1=4.5, V2=4.5, V3=4.5, V4=4.5),
     'high': dict(M1=.104, M2=.104, M3=.104, M4=.104, M5=.049, V1=15., V2=15., V3=15., V4=15.)}
MAX_CELLS = 60_000_000
KEYS = ['M1', 'M2', 'M3', 'M4', 'M5', 'V1', 'V2', 'V3', 'V4']


def check_tech(path):
    """Cross-check the built-in constants against the Magic tech file (extract section)."""
    txt = open(path).read().splitlines()
    got = {}; var = None
    for line in txt:
        s = line.split('#')[0].split()
        if not s: continue
        if s[0] == 'variants': var = {'()': 'typ', '(hrhc),(hrlc)': 'high'}.get(''.join(s[1:]))
        if var and s[0] == 'resist' and (m := re.match(r'\(allm(\d)\)', s[1])):
            got.setdefault(var, {})[f'M{m[1]}'] = float(s[2]) / 1000
        if var and s[0] == 'contact' and s[1] in ('m2c', 'm3c', 'via3', 'via4') and len(s) == 3:
            got.setdefault(var, {})[{'m2c': 'V1', 'm3c': 'V2', 'via3': 'V3', 'via4': 'V4'}[s[1]]] = float(s[2]) / 1000
    for c in R:
        if got.get(c) != R[c]: raise SystemExit(f'tech file disagrees for {c}: {got.get(c)} vs {R[c]}')
    return True


class Geo:
    def __init__(self, gds, top):
        self.l = k.Layout(); self.l.read(gds)
        self.top = self.l.cell(top) if top else self.l.top_cell()
        if self.top is None: raise SystemExit(f'no cell {top}')
        self.dbu = self.l.dbu; self._cache = {}

    def region(self, layer, clip=None):
        key = (layer, tuple(clip) if clip else None)
        if key not in self._cache:
            li = self.l.find_layer(layer, 0); r = k.Region()
            if li is not None:
                if clip:
                    b = self.box(clip); r = k.Region(self.top.begin_shapes_rec_touching(li, b)); r.merge(); r &= k.Region(b)
                else:
                    r = k.Region(self.top.begin_shapes_rec(li)); r.merge()
            self._cache[key] = r
        return self._cache[key]

    def box(self, b):
        d = self.dbu; return k.Box(round(b[0] / d), round(b[1] / d), round(b[2] / d), round(b[3] / d))

    def labels(self, name):
        out = []
        for li in self.l.layer_indexes():
            info = self.l.get_info(li)
            m = [n for n, v in METAL.items() if v == info.layer]
            if not m: continue
            it = k.RecursiveShapeIterator(self.l, self.top, li); it.shape_flags = k.Shapes.STexts
            while not it.at_end():
                s = it.shape()
                if s.text_string == name:
                    p = it.trans() * k.Point(s.text.x, s.text.y)
                    out.append((m[0], p.x * self.dbu, p.y * self.dbu))
                it.next()
        return out


def trace(g, seeds, clip):
    """seeds: [(metal, x, y)] -> {metal: Region}, {via: Region of cuts on the net}"""
    allm = {m: g.region(n, clip) for m, n in METAL.items()}
    cuts = {v: g.region(t[0], clip) for v, t in VIA.items()}
    mim = g.region(MIM, clip)
    if not mim.is_empty(): cuts['V4'] = cuts['V4'].not_interacting(mim)
    net = {m: k.Region() for m in METAL}
    for m, x, y in seeds:
        h = 0.01
        net[m] += allm[m].interacting(k.Region(g.box([x - h, y - h, x + h, y + h])))
    if all(net[m].is_empty() for m in net): raise SystemExit(f'no metal at the seed(s) {seeds}')
    changed = True
    while changed:
        changed = False
        for v, (_, lo, hi) in VIA.items():
            for a, b in ((lo, hi), (hi, lo)):
                if net[a].is_empty(): continue
                c = cuts[v].interacting(net[a])
                if c.is_empty(): continue
                new = allm[b].interacting(c)
                tot = net[b] + new; tot.merge()
                if tot.area() != net[b].area():
                    net[b] = tot; changed = True
    for m in net: net[m].merge()
    ncuts = {v: cuts[v].interacting(net[lo]).interacting(net[hi]) for v, (_, lo, hi) in VIA.items()}
    return net, ncuts


def refine(c, step):
    c = np.unique(np.round(np.asarray(c, float), 5))        # 0.01 nm snap: no zero-width cells from float noise
    if len(c) < 2: return c
    d = np.diff(c); n = np.maximum(1, np.ceil(d / step - 1e-9)).astype(int)
    out = [c[:1]]
    for a, dd, nn in zip(c[:-1], d, n):
        out.append(a + dd * np.arange(1, nn + 1) / nn)
    return np.concatenate(out)


class Mesh:
    """Resistor mesh of one net. Nodes = grid cells per metal layer; `geom` = conductance in units of 1/Rsheet (metal)
    or cuts (via)."""
    def __init__(self, g, net, ncuts, step, extra_edges):
        d = g.dbu; self.lay = {}; base = 0; self.g = g
        ea, eb, ek, ew, ela, elb = [], [], [], [], [], []
        code = {key: i for i, key in enumerate(KEYS)}
        for m in METAL:
            reg = net[m]
            if reg.is_empty(): continue
            traps = [p for p in reg.decompose_trapezoids_to_region().each()]
            xs, ys = [], []
            for p in traps:
                bb = p.bbox(); xs += [bb.left * d, bb.right * d]; ys += [bb.bottom * d, bb.top * d]
            for b in extra_edges.get(m, []):
                xs += [b[0], b[2]]; ys += [b[1], b[3]]
            bb = reg.bbox()
            xs = refine(np.clip(xs, bb.left * d, bb.right * d), step); ys = refine(np.clip(ys, bb.bottom * d, bb.top * d), step)
            nx, ny = len(xs) - 1, len(ys) - 1
            if nx * ny > MAX_CELLS: raise SystemExit(f'{m}: grid {nx} x {ny} too large; raise max_step or clip')
            pres = np.zeros((nx, ny), bool); xc = (xs[:-1] + xs[1:]) / 2; yc = (ys[:-1] + ys[1:]) / 2
            for p in traps:
                bb = p.bbox()
                j0, j1 = np.searchsorted(ys, [bb.bottom * d - 1e-9, bb.top * d - 1e-9])
                if p.is_box():
                    i0, i1 = np.searchsorted(xs, [bb.left * d - 1e-9, bb.right * d - 1e-9])
                    pres[i0:i1, j0:j1] = True
                else:                      # non-Manhattan trapezoid: cells whose centre is inside
                    pd = k.DPolygon([k.DPoint(q.x * d, q.y * d) for q in p.each_point_hull()])
                    i0, i1 = np.searchsorted(xs, [bb.left * d - 1e-9, bb.right * d - 1e-9])
                    for i in range(i0, i1):
                        for j in range(j0, j1):
                            if pd.inside(k.DPoint(xc[i], yc[j])): pres[i, j] = True
            idx = np.full((nx, ny), -1, np.int64); n = int(pres.sum()); idx[pres] = base + np.arange(n)
            dx = np.diff(xs); dy = np.diff(ys)
            # edge = (node a, node b, width, half length on a's side, half length on b's side): g = w / (la + lb) / Rsheet;
            # a half length is dropped later where that cell belongs to a terminal (the terminal is an equipotential up to its edge)
            mk = pres[:-1, :] & pres[1:, :]                    # x-directed conductances
            o = np.ones(mk.shape)
            ea.append(idx[:-1, :][mk]); eb.append(idx[1:, :][mk]); ew.append((dy[None, :] * o)[mk]); ela.append((dx[:-1, None] / 2 * o)[mk]); elb.append((dx[1:, None] / 2 * o)[mk])
            ek.append(np.full(int(mk.sum()), code[m]))
            mk2 = pres[:, :-1] & pres[:, 1:]
            o = np.ones(mk2.shape)
            ea.append(idx[:, :-1][mk2]); eb.append(idx[:, 1:][mk2]); ew.append((dx[:, None] * o)[mk2]); ela.append((dy[None, :-1] / 2 * o)[mk2]); elb.append((dy[None, 1:] / 2 * o)[mk2])
            ek.append(np.full(int(mk2.sum()), code[m]))
            self.lay[m] = dict(xs=xs, ys=ys, idx=idx, pres=pres, dx=dx, dy=dy, base=base, n=n,
                               area=reg.area() * d * d)
            base += n
        self.N = base; self.vias = {}
        for v, (_, lo, hi) in VIA.items():
            cs = [((b.left + b.right) / 2 * d, (b.bottom + b.top) / 2 * d) for b in (p.bbox() for p in ncuts[v].each())]
            if not cs or lo not in self.lay or hi not in self.lay: continue
            cs = np.array(cs); na = self.cell(lo, cs); nb = self.cell(hi, cs); ok = (na >= 0) & (nb >= 0)
            ea.append(na[ok]); eb.append(nb[ok]); ew.append(np.ones(int(ok.sum()))); ela.append(np.full(int(ok.sum()), .5)); elb.append(np.full(int(ok.sum()), .5)); ek.append(np.full(int(ok.sum()), code[v]))
            self.vias[v] = dict(xy=cs[ok], a=na[ok], b=nb[ok], dropped=int((~ok).sum()))
        self.ea = np.concatenate(ea); self.eb = np.concatenate(eb); self.ew = np.concatenate(ew); self.ela = np.concatenate(ela); self.elb = np.concatenate(elb); self.ek = np.concatenate(ek)

    def cell(self, m, pts):
        L = self.lay[m]; pts = np.atleast_2d(pts)
        i = np.searchsorted(L['xs'], pts[:, 0], 'right') - 1; j = np.searchsorted(L['ys'], pts[:, 1], 'right') - 1
        ok = (i >= 0) & (i < L['idx'].shape[0]) & (j >= 0) & (j < L['idx'].shape[1])
        out = np.full(len(pts), -1, np.int64); out[ok] = L['idx'][i[ok], j[ok]]
        return out

    def box_nodes(self, m, b):
        if m not in self.lay: return np.array([], np.int64)
        L = self.lay[m]
        i0 = max(0, np.searchsorted(L['xs'], b[0] + 1e-9, 'right') - 1); i1 = np.searchsorted(L['xs'], b[2] - 1e-9, 'left')
        j0 = max(0, np.searchsorted(L['ys'], b[1] + 1e-9, 'right') - 1); j1 = np.searchsorted(L['ys'], b[3] - 1e-9, 'left')
        s = L['idx'][i0:i1, j0:j1]
        return s[s >= 0]


def auto_contacts(g, net, window, clip):
    """Device terminals of the net: contact cuts under net Metal1, grouped by the (diffusion minus poly) or poly polygon.
    kind: nmos / pmos (source or drain: the diffusion touches a gate), ndiode / pdiode (n+ outside / p+ inside a well, no gate),
    ptap / ntap (substrate / well tie), gate (poly that crosses diffusion), res (poly that does not: resistor head)."""
    cont = g.region(CONT, clip)
    if window: cont = cont & k.Region(g.box(window))
    cont = cont.inside(net['M1'])
    comp = g.region(COMP, clip); poly = g.region(POLY, clip); nw = g.region(NWELL, clip); pp = g.region(PPLUS, clip)
    out = []
    for base, dev in (('sd', comp - poly), ('poly', poly - comp)):
        dev = dev.interacting(cont)
        if dev.is_empty(): continue
        if base == 'sd':
            mos = dev.interacting(poly); p_ = dev.interacting(pp); w_ = dev.interacting(nw)
            cls = [('pmos', mos & p_), ('nmos', mos - p_), ('pdiode', (dev - mos) & p_ & w_), ('ptap', ((dev - mos) & p_) - w_), ('ntap', ((dev - mos) - p_) & w_), ('ndiode', ((dev - mos) - p_) - w_)]
        else:
            gate = poly.interacting(comp)
            cls = [('gate', dev & gate), ('res', dev - gate)]
        for kind, reg in cls:
            for p in reg.each():
                c = cont.interacting(k.Region(p))
                if c.is_empty(): continue
                d = g.dbu; boxes = [[b.left * d, b.bottom * d, b.right * d, b.top * d] for b in (q.bbox() for q in c.each())]
                out.append((kind, boxes))
    out.sort(key=lambda t: (round(min(b[1] for b in t[1]), 1), min(b[0] for b in t[1])))
    return out


def solve_net(g, spec, corners):
    t0 = time.time()
    clip = spec.get('clip'); step = spec.get('max_step', 0.5); frac = spec.get('path_fraction', 0.5)
    seeds = [tuple(spec['seed'])] if 'seed' in spec else g.labels(spec.get('label', spec['name']))
    if not seeds: raise SystemExit(f"{spec['name']}: label not found")
    if clip: seeds = [s for s in seeds if clip[0] <= s[1] <= clip[2] and clip[1] <= s[2] <= clip[3]] or seeds
    net, ncuts = trace(g, seeds, clip)
    # terminals
    terms = []    # (name, layer, boxes, explicit)
    for t in spec.get('terminals', []):
        if 'auto_contacts' in t:
            for i, (kind, boxes) in enumerate(auto_contacts(g, net, t.get('window'), clip)):
                terms.append((f"{t['auto_contacts']}{i}", 'M1', boxes, False, kind))
        elif 'at_label' in t:
            h = t.get('half', 0.25)
            for i, (m, x, y) in enumerate(g.labels(t['at_label'])):
                terms.append((t['name'] if i == 0 else f"{t['name']}_{i}", m, [[x - h, y - h, x + h, y + h]], True, None))
        else:
            terms.append((t['name'], t['layer'], t.get('boxes') or [t['box']], t.get('explicit', True), None))
    extra = {}
    for _, m, boxes, _, _ in terms: extra.setdefault(m, []).extend(boxes)
    mesh = Mesh(g, net, ncuts, step, extra)
    tn = []
    for name, m, boxes, _, _ in terms:
        nodes = np.unique(np.concatenate([mesh.box_nodes(m, b) for b in boxes])) if boxes else np.array([], np.int64)
        if len(nodes) == 0: raise SystemExit(f"{spec['name']}: terminal {name} has no net metal on {m} in {boxes}")
        tn.append(nodes)
    T = len(terms); N = mesh.N
    owner = np.full(N, -1, np.int64)
    for i, nodes in enumerate(tn):
        if (owner[nodes] >= 0).any(): raise SystemExit(f"{spec['name']}: terminal {terms[i][0]} overlaps {terms[owner[nodes].max()][0]}")
        owner[nodes] = i
    # keep the part connected to a terminal
    A = sp.coo_matrix((np.ones(len(mesh.ea)), (mesh.ea, mesh.eb)), shape=(N, N))
    _, comp = connected_components(A, directed=False)
    tc = [int(comp[n[0]]) for n in tn]
    keep = np.isin(comp, np.unique(tc))
    free = keep & (owner < 0); F = int(free.sum())
    mp = np.full(N, -1, np.int64); mp[free] = np.arange(F); mp[owner >= 0] = F + owner[owner >= 0]
    a = mp[mesh.ea]; b = mp[mesh.eb]; ok = (a >= 0) & (b >= 0) & (a != b)
    ismetal = mesh.ek < 5
    la = np.where(ismetal & (owner[mesh.ea] >= 0), 0.0, mesh.ela); lb = np.where(ismetal & (owner[mesh.eb] >= 0), 0.0, mesh.elb)
    eg = mesh.ew / np.maximum(la + lb, 1e-12)        # edges inside a terminal are dropped by `ok`
    egrid = {}                                        # per layer: conductance geometry on the grid, for the flow maps
    for m, L in mesh.lay.items():
        own = np.zeros(L['idx'].shape, bool); own[L['pres']] = owner[L['idx'][L['pres']]] >= 0
        hx = np.where(own, 0.0, L['dx'][:, None] / 2 * np.ones(own.shape)); hy = np.where(own, 0.0, L['dy'][None, :] / 2 * np.ones(own.shape))
        egrid[m] = (L['dy'][None, :] / np.maximum(hx[:-1, :] + hx[1:, :], 1e-12), L['dx'][:, None] / np.maximum(hy[:, :-1] + hy[:, 1:], 1e-12))
    res = dict(name=spec['name'], seeds=[list(s) for s in seeds], clip=clip, max_step_um=step, path_fraction=frac,
               metal_area_um2={m: round(L['area'], 3) for m, L in mesh.lay.items()},
               via_cuts={v: len(d['xy']) for v, d in mesh.vias.items()},
               mesh_nodes=N, floating_nodes_dropped=int((~keep).sum()),
               terminals={name: dict(layer=m, cells=int(len(tn[i])), x=round(float(np.mean([(q[0] + q[2]) / 2 for q in boxes])), 3),
                                     y=round(float(np.mean([(q[1] + q[3]) / 2 for q in boxes])), 3), **(dict(kind=kd, contacts=len(boxes)) if kd else {}))
                          for i, (name, m, boxes, _, kd) in enumerate(terms)},
               corners={})
    groups = {}
    for gn, gd in spec.get('groups', {}).items():
        w = gd.get('window')
        if 'members' in gd: mem = [i for i, t in enumerate(terms) if t[0] in gd['members']]
        else: mem = [i for i, (name, m, boxes, _, kd) in enumerate(terms) if name.startswith(gd['prefix']) and (not gd.get('kind') or kd == gd['kind']) and
                     (not w or all(w[0] <= (q[0] + q[2]) / 2 <= w[2] and w[1] <= (q[1] + q[3]) / 2 <= w[3] for q in boxes))]
        if not mem: raise SystemExit(f"{spec['name']}: group {gn} is empty")
        groups[gn] = (mem, gd.get('ballast_ohm'))
    survey = spec.get('survey')          # name of the reference terminal: R from it to every device terminal, per kind
    if survey:
        for kd in sorted({t[4] for t in terms if t[4]}):
            groups[f'all_{kd}'] = ([i for i, t in enumerate(terms) if t[4] == kd], None)
    res['groups'] = {gn: dict(members=[terms[i][0] for i in mem], ballast_ohm=bal) for gn, (mem, bal) in groups.items()}
    names = [t[0] for t in terms]
    pairs = spec.get('pairs') or [[x, y] for i, x in enumerate(names) for y in names[i + 1:] if terms[names.index(x)][3] and terms[names.index(y)][3]]
    if survey: pairs = list(pairs) + [[survey, gn] for gn in groups if gn.startswith('all_')]
    for corner in corners:
        rv = R[corner]
        gval = eg / np.array([rv[key] for key in KEYS])[mesh.ek]
        n2 = F + T
        Lm = sp.coo_matrix((np.concatenate([-gval[ok], -gval[ok], gval[ok], gval[ok]]),
                            (np.concatenate([a[ok], b[ok], a[ok], b[ok]]), np.concatenate([b[ok], a[ok], a[ok], b[ok]]))), shape=(n2, n2)).tocsc()
        Lff = Lm[:F, :F]; Lft = Lm[:F, F:]; Ltt = Lm[F:, F:].toarray()
        lu = spl.splu(Lff, permc_spec='MMD_AT_PLUS_A', diag_pivot_thresh=0.0, options=dict(SymmetricMode=True)) if F else None
        S = Ltt.copy()
        if F:
            Ltf = Lft.T.tocsr()
            for t in range(T):
                x = lu.solve(-Lft[:, t].toarray().ravel()); S[:, t] += Ltf @ x
        S = (S + S.T) / 2
        out = dict(resistance_ohm={}, paths={}, reduced_network=[])
        for i in range(T):
            for j in range(i + 1, T):
                if -S[i, j] > 1e-9: out['reduced_network'].append([names[i], names[j], float(-1 / S[i, j])])

        if survey:
            Sp = np.linalg.pinv(S); r0 = names.index(survey); sv = {}
            for j, t in enumerate(terms):
                if t[4] and tc[j] == tc[r0]: sv.setdefault(t[4], []).append((float(Sp[r0, r0] + Sp[j, j] - 2 * Sp[r0, j]), t[0]))
            out['survey'] = {}
            for kd, lst in sv.items():
                lst.sort(); w = res['terminals'][lst[-1][1]]
                out['survey'][kd] = dict(terminals=len(lst), min_ohm=round(lst[0][0], 3), median_ohm=round(lst[len(lst) // 2][0], 3), max_ohm=round(lst[-1][0], 3),
                                         worst=dict(name=lst[-1][1], x=w['x'], y=w['y'], contacts=w.get('contacts')))

        def endpoint(e):
            if e in groups: return groups[e]
            return ([names.index(e)], None)

        for pa, pb in pairs:
            (ma, ba), (mb, bb_) = endpoint(pa), endpoint(pb)
            if set(ma) & set(mb): raise SystemExit(f'pair {pa}/{pb}: shared terminals')
            # extended matrix: terminals + one node per endpoint
            n3 = T + 2; E = np.zeros((n3, n3)); E[:T, :T] = S
            big = []
            for node, (mem, bal) in ((T, (ma, ba)), (T + 1, (mb, bb_))):
                for i in mem:
                    gb = 1.0 / bal if bal else None
                    if gb is None: big.append((i, node))
                    else:
                        E[i, i] += gb; E[node, node] += gb; E[i, node] -= gb; E[node, i] -= gb
            # merge the ideally shorted ones
            rep = np.arange(n3)
            for i, node in big: rep[i] = node
            u = np.unique(rep); pos = {v: q for q, v in enumerate(u)}; P = np.zeros((n3, len(u)))
            for i in range(n3): P[i, pos[rep[i]]] = 1
            Em = P.T @ E @ P; ia, ib = pos[T], pos[T + 1]
            sel = [q for q in range(len(u)) if q != ib]
            # drop nodes not connected (other components)
            try:
                rhs = np.zeros(len(sel)); rhs[sel.index(ia)] = 1.0
                Mx = Em[np.ix_(sel, sel)]
                live = [q for q in range(len(sel)) if Mx[q, q] > 1e-12]
                v = np.zeros(len(sel)); v[live] = np.linalg.solve(Mx[np.ix_(live, live)], rhs[live])
                if tc[ma[0]] != tc[mb[0]]: raise np.linalg.LinAlgError
            except np.linalg.LinAlgError:
                out['resistance_ohm'][f'{pa}|{pb}'] = None; continue
            vm = np.zeros(len(u)); vm[sel] = v; vext = P @ vm; rtot = float(vm[ia])
            key = f'{pa}|{pb}'
            bal_par = sum((bal / len(mem)) for mem, bal in ((ma, ba), (mb, bb_)) if bal)
            out['resistance_ohm'][key] = round(rtot - bal_par, 5)
            # field
            vt = vext[:T]; vf = lu.solve(-(Lft @ vt)) if F else np.zeros(0)
            vall = np.full(N, np.nan); vall[free] = vf; vall[owner >= 0] = vt[owner[owner >= 0]]
            info = dict(total_ohm_incl_ballast=round(rtot, 5)) if bal_par else {}
            # metal cross-sections
            narrow = None; jmax = 0.0
            for m, L in mesh.lay.items():
                V = np.full(L['idx'].shape, np.nan); V[L['pres']] = vall[L['idx'][L['pres']]]
                rs = rv[m]
                for axis in (0, 1):
                    if axis == 0:   # flow in y through horizontal interfaces; runs along x
                        mk = L['pres'][:, :-1] & L['pres'][:, 1:]; Fl = np.where(mk, egrid[m][1] / rs * (V[:, :-1] - V[:, 1:]), 0.0)
                        wd = np.broadcast_to(L['dx'][:, None], mk.shape); mkT, FlT, wdT = mk.T, Fl.T, wd.T
                    else:
                        mk = L['pres'][:-1, :] & L['pres'][1:, :]; Fl = np.where(mk, egrid[m][0] / rs * (V[:-1, :] - V[1:, :]), 0.0)
                        wd = np.broadcast_to(L['dy'][None, :], mk.shape); mkT, FlT, wdT = mk, Fl, wd
                    if not mkT.any(): continue
                    Fl2 = np.nan_to_num(FlT)
                    st = mkT.copy(); st[:, 1:] &= ~mkT[:, :-1]
                    ids = np.cumsum(st.ravel()).reshape(st.shape) - 1
                    cnt = int(ids.max()) + 1
                    fsum = np.bincount(ids[mkT], weights=Fl2[mkT], minlength=cnt); wsum = np.bincount(ids[mkT], weights=wdT[mkT], minlength=cnt)
                    on = np.abs(fsum) >= frac - 1e-9
                    if on.any():
                        q = np.where(on)[0]; kmin = q[np.argmin(wsum[q])]
                        jmax = max(jmax, float(np.max(np.abs(fsum[q]) / wsum[q])))
                        if narrow is None or wsum[kmin] < narrow['width_um'] - 1e-9:
                            r_, c_ = np.argwhere((ids == kmin) & mkT)[0]
                            x_, y_ = (L['xs'][c_], L['ys'][r_ + 1]) if axis == 0 else (L['xs'][r_ + 1], L['ys'][c_])
                            narrow = dict(width_um=round(float(wsum[kmin]), 4), layer=m, x=round(float(x_), 3), y=round(float(y_), 3),
                                          current_fraction=round(float(abs(fsum[kmin])), 4))
            # vias
            singles = []; mincuts = None; cutmax = dict(fraction=0.0)
            for vname, d in mesh.vias.items():
                ic = (vall[d['a']] - vall[d['b']]) / rv[vname]; ic = np.nan_to_num(ic)
                if len(ic) == 0: continue
                tree = cKDTree(d['xy']); pr = tree.query_pairs(0.9, output_type='ndarray')
                gph = sp.coo_matrix((np.ones(len(pr)), (pr[:, 0], pr[:, 1])), shape=(len(ic), len(ic))) if len(pr) else sp.coo_matrix((len(ic), len(ic)))
                ng, lab = connected_components(gph, directed=False)
                gsum = np.bincount(lab, weights=ic, minlength=ng); gcnt = np.bincount(lab, minlength=ng)
                for q in np.where(np.abs(gsum) >= frac - 1e-9)[0]:
                    c0 = d['xy'][lab == q].mean(axis=0)
                    ent = dict(via=vname, cuts=int(gcnt[q]), x=round(float(c0[0]), 3), y=round(float(c0[1]), 3), current_fraction=round(float(abs(gsum[q])), 4))
                    if gcnt[q] == 1: singles.append(ent)
                    if mincuts is None or gcnt[q] < mincuts['cuts']: mincuts = ent
                kx = int(np.argmax(np.abs(ic)))
                if abs(ic[kx]) > cutmax['fraction']:
                    cutmax = dict(fraction=round(float(abs(ic[kx])), 4), via=vname, x=round(float(d['xy'][kx][0]), 3), y=round(float(d['xy'][kx][1]), 3))
            flags = []
            if narrow and narrow['width_um'] < spec.get('min_width', 0.0): flags.append(f"narrow metal {narrow['width_um']} um on {narrow['layer']}")
            if mincuts and mincuts['cuts'] < spec.get('min_cuts', 2): flags.append(f"{len(singles)} single-cut via(s) on the path")
            info.update(narrowest_on_path=narrow, max_run_current_density_per_um=round(jmax, 4), single_cut_vias_on_path=len(singles),
                        single_cut_vias=singles[:20], fewest_cuts_on_path=mincuts, max_current_fraction_per_cut=cutmax, flags=flags)
            out['paths'][key] = info
        res['corners'][corner] = out
    res['seconds'] = round(time.time() - t0, 1)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--gds', required=True); ap.add_argument('--top'); ap.add_argument('--spec', required=True)
    ap.add_argument('--out', required=True); ap.add_argument('--corner', default='typ,high'); ap.add_argument('--tech')
    ap.add_argument('--only', help='comma list of net names of the spec to run')
    a = ap.parse_args()
    if a.tech: check_tech(a.tech)
    import hashlib
    spec = json.load(open(a.spec)); g = Geo(a.gds, a.top)
    out = dict(gds=a.gds, gds_sha256=hashlib.sha256(open(a.gds, 'rb').read()).hexdigest(), top=g.top.name, resistances=R,
               tech_checked=bool(a.tech), nets={})
    for n in spec['nets']:
        if a.only and n['name'] not in a.only.split(','): continue
        r = solve_net(g, n, a.corner.split(','))
        out['nets'][n['name']] = r
        for c, d in r['corners'].items():
            for key, v in d['resistance_ohm'].items():
                p = d['paths'].get(key, {})
                nw = p.get('narrowest_on_path') or {}
                print(f"{n['name']:12s} {c:4s} {key:28s} {v if v is None else round(v, 3)!s:>9} ohm  narrowest {nw.get('width_um')} um {nw.get('layer')}"
                      f"  single-cut vias {p.get('single_cut_vias_on_path')}  max/cut {p.get('max_current_fraction_per_cut', {}).get('fraction')}  {'; '.join(p.get('flags', []))}", flush=True)
            for kd, v in d.get('survey', {}).items():
                print(f"{n['name']:12s} {c:4s} survey {r['terminals'] and n.get('survey')} -> each {kd:7s} x{v['terminals']:<4d} min {v['min_ohm']:8.2f} median {v['median_ohm']:8.2f} max {v['max_ohm']:8.2f} ohm  worst at ({v['worst']['x']}, {v['worst']['y']})", flush=True)
        json.dump(out, open(a.out, 'w'), indent=1)
    json.dump(out, open(a.out, 'w'), indent=1)


if __name__ == '__main__':
    main()
