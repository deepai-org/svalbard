"""Floorplan planning library (FLOORPLAN_PLAN.md): place a hand plan, check it, assign macro pins, global-route on a gcell grid, report."""
import json, glob, math, heapq, collections, itertools
import numpy as np

DIE = (0.0, 0.0, 3932.0, 5122.0); CORE = (452.0, 452.0, 3480.0, 4670.0)
PITCH = 0.56            # Metal1-4 track pitch (tech LEF); Metal5 0.9
G = 20.0                # gcell (um)
import os as _os
KNEE = float(_os.environ.get("KNEE", "0.55"))

def read_lef(run):
    lef = {}
    for f in glob.glob(run + '/lef/*.lef'):
        cur = pin = None
        for l in (q for L_ in open(f) for q in L_.split(';')):
            t = l.split()
            if not t: continue
            if t[0] == 'MACRO': cur = t[1]; lef[cur] = dict(pins={}, w=0, h=0)
            elif t[0] == 'SIZE': lef[cur]['w'] = float(t[1]); lef[cur]['h'] = float(t[3])
            elif t[0] == 'PIN': pin = t[1]
            elif t[0] == 'LAYER' and pin: lay = t[1]
            elif t[0] == 'RECT' and pin and pin not in lef[cur]['pins']:
                x0, y0, x1, y1 = map(float, t[1:5]); lef[cur]['pins'][pin] = ((x0 + x1) / 2, (y0 + y1) / 2, lay)
            elif t[0] == 'END' and len(t) > 1 and t[1] == pin: pin = None
    return lef

ROT = ('W', 'E', 'FW', 'FE')
def dims(o, w, h): return (h, w) if o in ROT else (w, h)
def tr(o, x, y, w, h):
    return {'N': (x, y), 'S': (w - x, h - y), 'W': (h - y, x), 'E': (y, w - x), 'FN': (w - x, y), 'FS': (x, h - y),
            'FW': (y, x), 'FE': (h - y, w - x)}[o]
def ov(a, b, g=0.0): return min(a[2], b[2]) - max(a[0], b[0]) > -g + 1e-6 and min(a[3], b[3]) - max(a[1], b[1]) > -g + 1e-6
def egap(a, b): return math.hypot(max(b[0] - a[2], a[0] - b[2], 0.0), max(b[1] - a[3], a[1] - b[3], 0.0))
def mgap(a, b): return max(b[0] - a[2], a[0] - b[2], 0.0) + max(b[1] - a[3], a[1] - b[3], 0.0)

class Plan:
    def __init__(self, chipjson, run, place, keepouts, channels, grow=0.0):
        self.D = json.load(open(chipjson)); self.C = self.D['comp']; self.lef = read_lef(run)
        self.keep = keepouts; self.chan = channels; self.rect = {}; self.orient = {}; self.msgs = []
        for i, (x, y, o) in place.items():
            m = self.C[i]['master']; w, h = dims(o, self.lef[m]['w'], self.lef[m]['h'])
            self.rect[i] = (x, y, round(x + w, 2), round(y + h, 2)); self.orient[i] = o
        self.ring = {i: v['rect'] for i, v in self.C.items() if i.startswith('io_') or v['master'].startswith(('gf180mcu_fd_io', 'pad_'))}

    def movable(self):
        return [i for i, v in self.C.items() if i not in self.rect and i not in self.ring and not i.startswith(('antd', 'pdn'))]

    def partner(self, i):
        c = collections.Counter()
        for n, v in self.D['nets'].items():
            if v['cls'] == 'hook': continue
            g = {e[0] for e in v['ends']}
            if i in g:
                for j in g:
                    if j != i and j in self.rect: c[j] += 1
        return c.most_common(1)[0][0] if c else None

    def free(self, r, halo=2.0, chan_ok=False):
        if r[0] < CORE[0] or r[1] < CORE[1] or r[2] > CORE[2] or r[3] > CORE[3]: return False
        for k in self.keep:
            if ov(r, k): return False
        for n_, k in self.chan.items():
            if chan_ok and (chan_ok is True or n_ in chan_ok): continue
            if ov(r, k): return False
        for q in self.rect.values():
            if ov(r, q, halo): return False
        return True

    def autoplace(self, names, near=None, step=10.0, halo=2.0, chan_ok=False):
        """small cells / decap tiles: nearest free spot to the partner (spiral over a 10 um lattice)"""
        out = []
        for i in names:
            m = self.C[i]['master']; w, h = self.lef[m]['w'], self.lef[m]['h']
            p = near.get(i) if near else None
            p = p or self.partner(i)
            if p in self.rect: cx, cy = (self.rect[p][0] + self.rect[p][2]) / 2, (self.rect[p][1] + self.rect[p][3]) / 2
            else: cx, cy = (CORE[0] + CORE[2]) / 2, (CORE[1] + CORE[3]) / 2
            best = None
            for rad in range(0, 4000, int(step)):
                for k in range(max(1, int(8 * rad / step))):
                    a = 2 * math.pi * k / max(1, int(8 * rad / step))
                    for o in ('N', 'W'):
                        ww, hh = dims(o, w, h)
                        x = round((cx + rad * math.cos(a) - ww / 2) / 2) * 2; y = round((cy + rad * math.sin(a) - hh / 2) / 2) * 2
                        r = (x, y, x + ww, y + hh)
                        if self.free(r, halo, chan_ok): best = (r, o); break
                    if best: break
                if best: break
            if best: self.rect[i] = best[0]; self.orient[i] = best[1]
            else: out.append(i)
        return out

    def check(self, rules, adj, pad_adj=()):
        bad = []
        R = dict(self.rect)
        for a, b in itertools.combinations(R, 2):
            if ov(R[a], R[b]): bad.append(('OVERLAP', a, b))
        for i, r in R.items():
            if r[0] < CORE[0] - 1e-6 or r[1] < CORE[1] - 1e-6 or r[2] > CORE[2] + 1e-6 or r[3] > CORE[3] + 1e-6: bad.append(('OUTSIDE CORE', i, r))
            for k in self.keep:
                if ov(r, k): bad.append(('IN PAD KEEPOUT', i, k))
            for cn, k in self.chan.items():
                if ov(r, k): bad.append(('IN CHANNEL', i, cn))
        ka = []
        for a, v, d in rules:
            if a in R and v in R:
                g = egap(R[a], R[v]); ka.append((a, v, d, round(g), g >= d))
        ad = []
        for a, b, d in adj:
            ra = R.get(a) or self.ring.get(a); rb = R.get(b) or self.ring.get(b)
            if ra and rb:
                g = mgap(ra, rb); ad.append((a, b, d, round(g), g <= d))
        return bad, ka, ad

    # ---- pins ----
    def pin_xy(self, i, p):
        if i in self.rect:
            m = self.C[i]['master']; L = self.lef[m]; pp = L['pins'].get(p)
            r = self.rect[i]
            if pp is None: return ((r[0] + r[2]) / 2, (r[1] + r[3]) / 2)
            x, y = tr(self.orient[i], pp[0], pp[1], L['w'], L['h'])
            return (r[0] + x, r[1] + y)
        c = self.C[i]; e = [e for n, v in self.D['nets'].items() for e in v['ends'] if e[0] == i and e[1] == p]
        return (e[0][2], e[0][3]) if e else ((c['rect'][0] + c['rect'][2]) / 2, (c['rect'][1] + c['rect'][3]) / 2)

    def assign_macro(self, mac='digital', pitch=2.24, sides='NSEW', fixed_side=None, forbid=None):
        """every macro net gets one pin on the macro edge nearest the centroid of its other ends, legalised per side
        at `pitch`; fixed_side: {net: side} overrides. Returns {net: (side, x, y)}."""
        r = self.rect[mac]; want = {}; out = {}
        # host-link cluster (coordinator 2026-11-26): h2d_*, d2h_*, host_word_clk keep their hardened macro position
        # (matched skew); their pins move with the macro, relative to its lower-left corner, and are routed as a bundle
        import re as _re
        c0 = self.C[mac]['rect']
        for n, v in self.D['nets'].items():
            if v['cls'] == 'hook' or not _re.match(HOSTLINK, n): continue
            e = [e for e in v['ends'] if e[0] == mac]
            if not e: continue
            x, y = e[0][2] - c0[0] + r[0], e[0][3] - c0[1] + r[1]
            d = {'W': abs(x - r[0]), 'E': abs(r[2] - x), 'S': abs(y - r[1]), 'N': abs(r[3] - y)}
            out[n] = (min(d, key=d.get), round(x, 2), round(y, 2))
        fixedpos = {s_: sorted((x if s_ in 'SN' else y) for s2, x, y in out.values() if s2 == s_) for s_ in 'NSEW'}
        for n, v in self.D['nets'].items():
            if n in out: continue
            if v['cls'] == 'hook' or not any(e[0] == mac for e in v['ends']): continue
            oth = [self.pin_xy(e[0], e[1]) for e in v['ends'] if e[0] != mac and not e[0].startswith(('antd', 'pdn'))]
            if not oth: continue
            cx = sum(p[0] for p in oth) / len(oth); cy = sum(p[1] for p in oth) / len(oth)
            # side: the side whose outward half-plane holds the centroid, weighted by distance beyond the edge
            d = {'S': r[1] - cy, 'N': cy - r[3], 'W': r[0] - cx, 'E': cx - r[2]}
            s = (fixed_side or {}).get(n) or max((k for k in d if k in sides), key=lambda k: d[k])
            if forbid and s in forbid:      # side stretch facing a pad keep-out: move the pin out of it
                for lo_, hi_ in forbid[s]:
                    c_ = cx if s in 'SN' else cy
                    if lo_ <= c_ <= hi_:
                        if s in 'SN': cx = lo_ - 1 if c_ - lo_ < hi_ - c_ else hi_ + 1
                        else: cy = lo_ - 1 if c_ - lo_ < hi_ - c_ else hi_ + 1
                if s in 'WE' and any(lo_ <= cy <= hi_ for lo_, hi_ in forbid[s]): s = 'S'
            pos = min(max(cx, r[0] + 1), r[2] - 1) if s in 'SN' else min(max(cy, r[1] + 1), r[3] - 1)
            want.setdefault(s, []).append((pos, n))
        for s, L in want.items():
            L.sort(); lo, hi = (r[0], r[2]) if s in 'SN' else (r[1], r[3])
            n_ = len(L); cap = int((hi - lo) / pitch)
            if n_ > cap: self.msgs.append(f'macro side {s}: {n_} pins > {cap} slots at {pitch} um')
            # legalise: forward pass with min pitch, then backward to fit
            pos = []
            fx = fixedpos.get(s, [])
            for p, n in L:
                p = max(p, (pos[-1] + pitch) if pos else lo + pitch)
                while any(abs(p - f) < pitch for f in fx): p += pitch
                pos.append(p)
            over = pos[-1] - (hi - pitch) if pos else 0
            if over > 0:
                for k in range(len(pos) - 1, -1, -1):
                    lim = (hi - pitch) if k == len(pos) - 1 else pos[k + 1] - pitch
                    pos[k] = min(pos[k], lim)
            for (p0, n), p in zip(L, pos):
                xy = (p, r[1]) if s == 'S' else (p, r[3]) if s == 'N' else (r[0], p) if s == 'W' else (r[2], p)
                out[n] = (s, round(xy[0], 2), round(xy[1], 2))
        self.mpins = out
        return out

    # ---- global route ----
    def grid(self, sig_m1=False, over_block_m45=0.0):
        nx = int(math.ceil((DIE[2]) / G)); ny = int(math.ceil((DIE[3]) / G))
        freeH = np.ones((nx, ny)); freeV = np.ones((nx, ny))   # free fraction of each gcell for M2/M3
        freeV4 = np.ones((nx, ny))                              # Metal4 (swapped grid): decap does not block it
        def blk(r, val=0.0):
            x0, y0, x1, y1 = r
            for ix in range(max(0, int(x0 // G)), min(nx, int(math.ceil(x1 / G)))):
                fx = (min(x1, (ix + 1) * G) - max(x0, ix * G)) / G
                for iy in range(max(0, int(y0 // G)), min(ny, int(math.ceil(y1 / G)))):
                    fy = (min(y1, (iy + 1) * G) - max(y0, iy * G)) / G
                    freeH[ix, iy] = max(0.0, freeH[ix, iy] - fx * fy); freeV[ix, iy] = max(0.0, freeV[ix, iy] - fx * fy); freeV4[ix, iy] = max(0.0, freeV4[ix, iy] - fx * fy)
        # outside core: the core ring (Metal4/5) and provider cells; signal routing stays inside the core
        for r in [(0, 0, DIE[2], CORE[1]), (0, CORE[3], DIE[2], DIE[3]), (0, 0, CORE[0], DIE[3]), (CORE[2], 0, DIE[2], DIE[3])]: blk(r)
        for k in self.keep: blk(k)
        for i, r in self.rect.items():
            if self.C[i]['master'] == 'decap':      # decap obstructs Metal1-2 only: horizontal Metal3 passes over it
                sv = freeH.copy(); sv4 = freeV4.copy(); blk(r); freeH[:] = sv; freeV4[:] = sv4
            else: blk(r)
        trk = G / PITCH
        layersH = (2 if sig_m1 else 1)
        import os
        swap = os.environ.get('GRID_SWAP', '1') == '1'      # coordinator 2026-11-26: grid Metal4 vertical, Metal5 horizontal (with the LEF)
        # with the swap, signal Metal4 (vertical, 0.56 pitch) and Metal5 (horizontal, 0.9 pitch) run between the straps: 70 % of
        # their tracks in channels (2 x 10.5 um straps per 70 um pitch); over blocks nothing (conservative)
        self.capH = freeH * (trk * layersH + (0.7 * G / 0.9 if swap else 0)) + (1 - freeH) * trk * over_block_m45   # M3 [+M1] [+M5]
        self.capV = freeV * trk + (freeV4 * trk * 0.7 if swap else 0) + (1 - freeV) * trk * over_block_m45          # M2 [+M4]
        self.nx, self.ny = nx, ny

    def cell(self, xy): return (min(self.nx - 1, max(0, int(xy[0] // G))), min(self.ny - 1, max(0, int(xy[1] // G))))

    def escape(self, xy, inst):
        """pin -> first gcell outside the owner's outline in the direction of the nearest edge"""
        r = self.rect.get(inst) or self.ring.get(inst)
        if not r: return self.cell(xy)
        x, y = xy; d = {'W': x - r[0], 'E': r[2] - x, 'S': y - r[1], 'N': r[3] - y}; s = min(d, key=d.get)
        p = {'W': (r[0] - G / 2, y), 'E': (r[2] + G / 2, y), 'S': (x, r[1] - G / 2), 'N': (x, r[3] + G / 2)}[s]
        return self.cell(p)

    def route(self, weights, iters=6, skip=lambda n, v: v['cls'] == 'hook'):
        nx, ny = self.nx, self.ny
        useH = np.zeros((nx, ny)); useV = np.zeros((nx, ny)); hist = np.ones((2, nx, ny))
        conns = []
        for n, v in self.D['nets'].items():
            if skip(n, v): continue
            pts = []
            for e in v['ends']:
                if e[0].startswith(('antd', 'pdn')): continue
                if e[0] == 'digital' and n in getattr(self, 'mpins', {}):
                    s, x, y = self.mpins[n]; c = self.escape((x, y), 'digital')
                else: c = self.escape(self.pin_xy(e[0], e[1]), e[0])
                pts.append(c)
            pts = list(dict.fromkeys(pts))
            if len(pts) < 2: continue
            # MST (Manhattan) decomposition
            inn = [pts[0]]; rest = pts[1:]
            while rest:
                b = min(((a, q) for a in inn for q in rest), key=lambda t: abs(t[0][0] - t[1][0]) + abs(t[0][1] - t[1][1]))
                conns.append((n, b[0], b[1], weights(n, v))); inn.append(b[1]); rest.remove(b[1])
        self.conns = conns
        paths = [None] * len(conns)
        capH = np.maximum(self.capH, 1e-3); capV = np.maximum(self.capV, 1e-3)
        for it in range(iters):
            for k, (n, a, b, w) in enumerate(conns):
                if paths[k]:
                    for (ix, iy, d) in paths[k]:
                        (useH if d == 0 else useV)[ix, iy] -= w
                costH = hist[0] * (1 + np.maximum(0, (useH + w) / capH - KNEE) * 20) + 1e3 * (self.capH < 0.5)
                costV = hist[1] * (1 + np.maximum(0, (useV + w) / capV - KNEE) * 20) + 1e3 * (self.capV < 0.5)
                p = self._astar(a, b, costH, costV)
                paths[k] = p
                for (ix, iy, d) in p: (useH if d == 0 else useV)[ix, iy] += w
            hist[0] += 0.3 * np.maximum(0, useH / capH - KNEE); hist[1] += 0.3 * np.maximum(0, useV / capV - KNEE)
        self.useH, self.useV, self.paths = useH, useV, paths
        return useH, useV

    def _astar(self, a, b, costH, costV):
        # window: bbox of a, b grown by 40 gcells
        x0 = max(0, min(a[0], b[0]) - 40); x1 = min(self.nx - 1, max(a[0], b[0]) + 40)
        y0 = max(0, min(a[1], b[1]) - 40); y1 = min(self.ny - 1, max(a[1], b[1]) + 40)
        dist = {a: 0.0}; prev = {}; pq = [(0.0, a)]
        while pq:
            f, u = heapq.heappop(pq)
            if u == b: break
            du = dist[u]
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                v = (u[0] + dx, u[1] + dy)
                if not (x0 <= v[0] <= x1 and y0 <= v[1] <= y1): continue
                c = (costH if dy == 0 else costV)[v] + (0.3 if (u in prev and ((prev[u][0] - u[0] != 0) != (dx != 0))) else 0)
                nd = du + c
                if nd < dist.get(v, 1e18):
                    dist[v] = nd; prev[v] = u
                    heapq.heappush(pq, (nd + abs(v[0] - b[0]) + abs(v[1] - b[1]), v))
        path = []; u = b
        while u != a and u in prev:
            p = prev[u]; path.append((u[0], u[1], 0 if p[1] == u[1] else 1)); u = p
        return path

HOSTLINK = r'^(h2d_|d2h_|host_word_clk)'

def cut_table(U, cuts, G, free_min=0.5):
    """cuts: {name: ('H'|'V', fixed coord, lo, hi)}; 'H' = horizontal cut line (vertical wires cross it: M2 usage/capacity
    of the gcell row just below the line), 'V' = vertical cut line (horizontal wires, M3). Returns {name: (nets, tracks, util)}"""
    uH, uV, cH, cV = U; out = {}
    for n, (d, c, lo, hi) in cuts.items():
        if d == 'H':
            iy = int(c // G); xs = range(int(lo // G), int(hi // G))
            dem = sum(uV[ix, iy] for ix in xs); cap = sum(cV[ix, iy] for ix in xs)
        else:
            ix = int(c // G); ys = range(int(lo // G), int(hi // G))
            dem = sum(uH[ix, iy] for iy in ys); cap = sum(cH[ix, iy] for iy in ys)
        out[n] = (round(float(dem)), round(float(cap)), round(float(dem / max(cap, 1e-3)), 2))
    return out

def chan_util(U, rects, G):
    """per channel rectangle: peak and mean utilisation of its gcells (V and H), cells fully inside"""
    import numpy as np
    uH, uV, cH, cV = U; out = {}
    for n, (x0, y0, x1, y1) in rects.items():
        xs = slice(int(math.ceil(x0 / G)), int(x1 // G)); ys = slice(int(math.ceil(y0 / G)), int(y1 // G))
        rv = uV[xs, ys] / np.maximum(cV[xs, ys], 1e-3); rh = uH[xs, ys] / np.maximum(cH[xs, ys], 1e-3)
        if rv.size == 0: out[n] = None; continue
        out[n] = dict(V_peak=round(float(rv.max()), 2), H_peak=round(float(rh.max()), 2))
    return out
