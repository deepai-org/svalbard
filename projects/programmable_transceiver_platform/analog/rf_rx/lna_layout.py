"""Compact flat layout of pt_lna (fork F; same-net DRC fixups + flow entry point: fork J).

Same PCells / escape style as rfrx_flow, different routing stack so the MIM capacitors can sit on
top of the active area:
  * all device routing on M1-M3: M3 vertical escapes, M2 horizontal channel tracks (one channel
    under each device row), M3 vertical trunks for nets that span several channels;
  * M4/M5 are used only by the MIM capacitors (bottom plate M4, top plate via M5 tab).  Caps are
    tiled over the device rows / channels; both cap pins are brought down (M5 tab / M4 tab) to a
    spot in the gap between a channel and the row above it, outside every FuseTop (MIMTM.10), and
    dropped on M3 into that channel.
Flow entry: build_compact(spice, top, work, row_width) (rfrx_flow.generate('lna')).
Standalone: python3 lna_layout.py <src.spice> <workdir> [row_width] [--dry]
"""
import sys, math, json, re, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import rfrx_flow as F
import antenna_diodes as ad
from rfrx_flow import Device, Painter, _snap, prim_key, POWER

GAP = 1.0
TP = 0.7            # M2 track pitch
TW = 0.3            # M2 track width
VX = 0.95           # min centre distance between two foreign M3 verticals
PWR_W = 0.8
CAP_SEP = 1.4       # cap footprint to cap footprint
PIN_DY = 0.55       # cap pin y above channel top
ORDER = 'net'
# Round 3 (R+C extraction): every net was drawn with 0.3 um Metal2 tracks / 0.4 um Metal3 trunks, so the 18.6 mA tail current
# crossed ~89 ohm of Metal2 (DC point 4.95 instead of 18.3 mA) and ran at ~60 mA/um against the 2.09 mA/um DRM 14.2 limit
# (85 C).  Nets that carry DC current get k track slots (width k*TP - 0.4) and a trunk of the same width, joined by via arrays.
# Sized for the worst-corner current: 18.6 mA (tail, supply, tank feed) -> 9.4 um; 9.3 mA per side -> 4.5 um.
WIDE_LNA = {'VDD': 14, 'VSS': 14, 'tailx': 14, 'tail': 14, 'vtk': 14,
        'src_p': 7, 'src_n': 7, 'x_p': 7, 'x_n': 7, 'tank_p': 7, 'tank_n': 7}
WIDE = {}            # set per cell in build_compact (pt_lna only; rxmix keeps the plain router)
VP = 0.66           # via-array pitch (0.52-0.6 um arrays fail KLayout V2.2b; integration fixed its arrays at 0.62)


def heavy(d):
    """MOS that carries the stage's DC current: different S/D nets, one of them a non-supply WIDE net, >= 20 um."""
    return (d.kind == 'mos' and d.nodes[0] != d.nodes[2] and d.w * d.nf >= 20.
            and bool({d.nodes[0], d.nodes[2]} & (set(WIDE) - set(POWER))))


def heavy_geom(work, d, g):
    """Round 3: per-strip escapes for a heavy multi-finger MOS.  The PCell escape (one 0.4 um Metal2 strap per terminal, one via
    at the device end) carried the whole device current (R+C: 21 ohm VDD -> feed PMOS, 89 ohm tail).  Every S/D strip gets a
    Metal2 stub toward the device centre with two Via1 and two Via2 cuts and its own 0.4 um Metal3 drop to the channel track
    (strips within 1.0 um of the gate / body escapes keep only the strap).  Returns a copy of g with 'taps' [(x, y_low, term)]."""
    r = F._rects(work / (prim_key(d) + '.mag'))
    diff = next(k for k in ('ndiffc', 'pdiffc', 'mvndiffc', 'mvpdiffc') if k in r)
    strips = sorted(r[diff], key=lambda a: a[0])
    ylo, yhi = min(a[1] for a in strips), max(a[3] for a in strips)
    if yhi - ylo < 2.0:
        return g
    yd, ys = yhi - .24, ylo + .24
    xs = [(a[0] + a[2]) / 2 for a in strips]
    gx, bx = g['esc'][1], g['esc'][3]
    extra, taps = list(g['extra']), []
    for i, x in enumerate(xs):
        if abs(x - gx) < 1.0 or abs(x - bx) < 1.0:
            continue
        y = ys if i % 2 == 0 else yd
        y2 = y + .66 if i % 2 == 0 else y - .66
        lo, hi = min(y, y2), max(y, y2)
        extra += [('rect', 'metal1', x - .19, lo - .19, x + .19, hi + .19),
                  ('rect', 'via1', x - .13, y2 - .13, x + .13, y2 + .13),
                  ('rect', 'metal2', x - .2, lo - .2, x + .2, hi + .2),
                  ('rect', 'via2', x - .14, y - .14, x + .14, y + .14), ('rect', 'via2', x - .14, y2 - .14, x + .14, y2 + .14),
                  ('rect', 'metal3', x - .2, lo - .2, x + .2, hi + .2)]
        taps.append((x, lo, 2 if i % 2 == 0 else 0))
    return dict(g, extra=extra, taps=taps)


def wwidth(n):
    k = WIDE.get(n, 1)
    return TW if k == 1 else k * TP - .4


def flatten(subs, top):
    out = []

    def rec(name, nmap, pre):
        for d in subs[name].devices:
            nodes = tuple(nmap.get(n, pre + n) for n in d.nodes)
            if d.kind == 'macro':
                sub = subs[d.model]
                m = {p: nodes[i] for i, p in enumerate(sub.ports)}
                for pw in POWER:
                    m.setdefault(pw, pw)
                rec(d.model, m, pre + d.name + '_')
            else:
                nd = Device(pre + d.name, d.model, nodes, d.w, d.l, d.nf)
                prev = out[-1] if out else None
                if (prev is not None and nd.kind == 'mos' and prev.model == nd.model and prev.w == nd.w
                        and prev.l == nd.l and prev.nodes == nd.nodes):
                    prev.nf += nd.nf
                else:
                    out.append(nd)
    ports = subs[top].ports
    rec(top, {p: p for p in ports} | {p: p for p in POWER}, '')
    return out, ports


def cap_geom(g):
    """cap pins: top (x_top, y_tab) via M5 tab (flow), bottom: own M4 tab down to y_tab."""
    m4, mim = g['m4'], g['mim']
    x_top, y_tab = g['pins'][0]
    x_b = m4[2] - .5
    assert x_b - .3 > mim[2] + .05 and x_b - x_top > 2.0
    extra = list(g['extra']) + [('rect', 'metal4', x_b - .3, y_tab - .2, x_b + .3, m4[1] + .05)]
    return dict(pins=[(x_top, y_tab), (x_b, y_tab)], extra=extra,
                fp=(m4[0] - .3, y_tab - .5, m4[2] + .3, m4[3]), y_tab=y_tab)


def lefted(ivs, gap=1.2, wide=()):
    """Left-edge track assignment; a net in `wide` takes WIDE[n] consecutive slots (first fit)."""
    tracks, tidx = [], {}
    for lo_, hi_, n in sorted(ivs):
        k = WIDE[n] if n in wide else 1; ti = 0
        while not all(j >= len(tracks) or tracks[j] + gap < lo_ for j in range(ti, ti + k)):
            ti += 1
        for j in range(ti, ti + k):
            if j >= len(tracks): tracks.append(hi_)
            else: tracks[j] = hi_
        tidx[n] = ti
    return tidx, len(tracks)


def via_array(p, x, y, wx, wy, low, high):
    """Via cuts on a VP grid inside a wx x wy overlap centred on (x, y) (at least one)."""
    nx, ny = max(1, int((wx - .4) / VP) + 1), max(1, int((wy - .4) / VP) + 1)
    for i in range(nx):
        for j in range(ny):
            p.via(_snap(x + (i - (nx - 1) / 2) * VP), _snap(y + (j - (ny - 1) / 2) * VP), low, high)


class Lay:
    def __init__(self, devs, geoms, ports, rw):
        self.devs, self.geoms, self.ports, self.rw = devs, geoms, ports, rw
        hclass = lambda it: round(math.log((it[1]['fp'][3] - it[1]['fp'][1]) + 1.) / math.log(1.6))
        act = [(d, geoms.get((prim_key(d), d.name), geoms[prim_key(d)])) for d in devs if d.kind != 'cap']
        self.caps = [(d, cap_geom(geoms[prim_key(d)])) for d in devs if d.kind == 'cap']
        if ORDER == 'height':
            act_o = [t[1] for t in sorted(enumerate(act), key=lambda t: (hclass(t[1]), t[0]))]
        elif ORDER == 'net':
            act_o = list(act)
        else:
            act_o = ORDER(act)
        rows, cur, cw = [], [], 0.
        for d, g in act_o:
            w = g['fp'][2] - g['fp'][0] + GAP
            if cur and cw + w > rw:
                rows.append(cur); cur, cw = [], 0.
            cur.append((d, g)); cw += w
        rows.append(cur)
        self.rows = []
        for items in rows:
            cx, pos, esc = 0., [], []
            for d, g in items:
                ox = cx - g['fp'][0]
                pos.append(ox)
                for ex, n in zip(g['esc'], d.nodes):
                    esc.append((ox + ex, n))
                for tx_, _, ti in g.get('taps', ()):
                    esc.append((ox + tx_, d.nodes[ti]))
                cx += g['fp'][2] - g['fp'][0] + GAP
            # nets whose channel track carries DC current in this row: S/D of a MOS with different S/D nets and >= 20 um total width
            # (switches, MOS capacitors and bias devices do not qualify: at least one S/D net must be a non-supply WIDE net)
            wide = {n for d, _ in items if d.kind == 'mos' and d.nodes[0] != d.nodes[2] and d.w * d.nf >= 20.
                    and {d.nodes[0], d.nodes[2]} & (set(WIDE) - set(POWER)) for n in (d.nodes[0], d.nodes[2]) if n in WIDE}
            self.rows.append(dict(items=items, pos=pos, esc=esc, used=cx, wide=wide,
                                  row_h=max(g['fp'][3] - g['fp'][1] for _, g in items)))
        self.width = max(r['used'] for r in self.rows)
        self.cap_pins = {}      # channel -> [(x, net)]
        self.cap_place = []     # (d, g, channel, ox)

    # ---------------------------------------------------------------- vertical geometry
    def channel_terms(self, ri):
        t = list(self.rows[ri]['esc']) + list(self.cap_pins.get(ri, []))
        return t

    def solve(self, trunk=None):
        trunk = trunk or {}
        y = 3.5
        for ri, r in enumerate(self.rows):
            ext = {}
            for x, n in self.channel_terms(ri):
                lo, hi = ext.get(n, (math.inf, -math.inf))
                ext[n] = (min(lo, x), max(hi, x))
            for n, (tx, tw_, lo, hi) in trunk.items():
                if lo <= ri <= hi and n in ext:
                    pad = tw_ / 2 if n in WIDE else 0.
                    ext[n] = (min(ext[n][0], tx - pad), max(ext[n][1], tx + pad))
            tidx, ntr = lefted([(a, b, n) for n, (a, b) in ext.items()], wide=r['wide'])
            r['band0'] = y
            r['track'] = {n: y + .6 + (tidx[n] + ((WIDE[n] if n in r['wide'] else 1) - 1) / 2) * TP for n in tidx}
            r['tw'] = {n: (wwidth(n) if n in r['wide'] else TW) for n in tidx}
            r['ext'] = ext
            r['band_top'] = y + .6 + ntr * TP + .2
            r['pin_y'] = r['band_top'] + PIN_DY
            r['y_dev'] = r['band_top'] + 1.6
            y = r['y_dev'] + r['row_h'] + .6
        self.height = y + 1.

    # ---------------------------------------------------------------- caps
    def place_caps(self):
        self.solve()
        placed = []   # rects
        vert = {}     # channel -> list of x used by cap drops
        for d, g in sorted(self.caps, key=lambda it: -(it[1]['fp'][3] - it[1]['fp'][1]) * (it[1]['fp'][2] - it[1]['fp'][0])):
            fp = g['fp']
            done = None
            for ri in range(len(self.rows)):
                r = self.rows[ri]
                oy = r['pin_y'] - g['y_tab']
                if oy + fp[3] > self.height - 1.:
                    continue
                escx = [x for x, _ in r['esc']] + vert.get(ri, [])
                x = -fp[0] + .5
                while x + fp[2] <= self.width:
                    rect = (x + fp[0], oy + fp[1], x + fp[2], oy + fp[3])
                    if any(not (rect[2] + CAP_SEP <= q[0] or q[2] + CAP_SEP <= rect[0] or
                                rect[3] + CAP_SEP <= q[1] or q[3] + CAP_SEP <= rect[1]) for q in placed):
                        x += .5; continue
                    px = [x + p[0] for p in g['pins']]
                    if any(abs(a - b) < VX for a in px for b in escx):
                        x += .25; continue
                    done = (ri, x, rect, px); break
                if done:
                    break
            if done is None:
                raise RuntimeError(f'cap {d.name} does not fit')
            ri, x, rect, px = done
            placed.append(rect)
            vert.setdefault(ri, []).extend(px)
            self.cap_pins.setdefault(ri, []).extend(zip(px, d.nodes))
            self.cap_place.append((d, g, ri, x))

    # ---------------------------------------------------------------- trunks
    def trunks(self):
        chans = {}
        for ri in range(len(self.rows)):
            for _, n in self.channel_terms(ri):
                chans.setdefault(n, set()).add(ri)
        nets = [n for n in chans if n in self.ports or len(chans[n]) > 1]
        span = {n: (-1 if n in self.ports else min(chans[n]), max(chans[n])) for n in nets}
        blocks = {ri: [x for x, _ in self.channel_terms(ri)] for ri in range(len(self.rows))}
        trunk = {}
        for n in sorted(nets, key=lambda n: (n not in POWER, -(span[n][1] - span[n][0]))):
            lo, hi = span[n]
            w = wwidth(n) if n in WIDE else (PWR_W if n in POWER else .4)
            own = sorted({round(x, 2) for ri in chans[n] for x, m in self.channel_terms(ri) if m == n})
            med = own[len(own) // 2]
            cands = sorted(own, key=lambda x: abs(x - med)) + \
                sorted((med + k * .25 for k in range(-1200, 1201)), key=lambda x: abs(x - med))
            for x in cands:
                if x < 1.0:
                    continue
                ok = True
                for ri in range(max(lo, 0), hi + 1):
                    for bx, bn in self.channel_terms(ri):
                        if bn != n and abs(bx - x) < VX + (w - .4) / 2:
                            ok = False; break
                    if not ok:
                        break
                    # own escapes at the same x in a row the trunk passes through (not its end channel)
                if ok:
                    for m, (tx, tw, a, b) in trunk.items():
                        if not (b < lo or hi < a) and abs(tx - x) < (w + tw) / 2 + .5:
                            ok = False; break
                if ok:
                    trunk[n] = (x, w, lo, hi); break
            else:
                raise RuntimeError('no trunk for ' + n)
        self.trunk = trunk
        self.solve(trunk)
        xs = [t[0] for t in trunk.values()]
        self.x0 = 1.0 - min(0., min(xs) - 1.)
        self.W = max(self.width, max(xs) + 1.) + self.x0 + 1.

    def verify_caps(self):
        rects = []
        for d, g, ri, x in self.cap_place:
            oy = self.rows[ri]['pin_y'] - g['y_tab']
            fp = g['fp']
            rects.append((x + fp[0], oy + fp[1], x + fp[2], oy + fp[3]))
        for i, a in enumerate(rects):
            for b in rects[i + 1:]:
                if not (a[2] + 1.2 <= b[0] or b[2] + 1.2 <= a[0] or a[3] + 1.2 <= b[1] or b[3] + 1.2 <= a[1]):
                    raise RuntimeError('cap overlap after solve')
        top = max(r[3] for r in rects)
        self.height = max(self.height, top + 1.)

    # ---------------------------------------------------------------- paint
    def paint(self, name):
        p = Painter()
        keepouts, taps, terminals, placed = [], [], [], []
        xo = self.x0
        vias_m3 = []
        for ri, r in enumerate(self.rows):
            reach = {}
            for (d, g), ox0 in zip(r['items'], r['pos']):
                ox = _snap(xo + ox0)
                oy = _snap(r['y_dev'] - g['fp'][1])
                k = prim_key(d)
                p.cmds += [f'getcell {k} child 0 0 parent {ox:.3f} {oy:.3f}', f'identify {d.name}']
                placed.append(d.name)
                fp = g['fp']
                keepouts.append((ox + fp[0], oy + fp[1], ox + fp[2], oy + fp[3]))
                if not d.model.startswith('pfet'):
                    taps.append(keepouts[-1])
                for e in g['extra']:
                    _, layer, x1, y1, x2, y2 = e
                    p.rect(layer, ox + x1, oy + y1, ox + x2, oy + y2)
                for t, ((px, py), ex, net, lev) in enumerate(zip(g['pins'], g['esc'], d.nodes, g['level'])):
                    X, Y, E = ox + px, oy + py, ox + ex
                    ty = r['track'][net]
                    p.net = net
                    if g['kind'] == 'mos':
                        terminals.append((X, Y, net, 'g' if t == 1 else 'sd' if t in (0, 2) else 'x',
                                          d.w * d.l * d.nf if t == 1 else 0.))
                    if lev == 2:
                        p.via(E, Y, 2, 3)
                    elif abs(E - X) < 1e-6:
                        p.via(X, Y, 1, 3)
                    else:
                        p.via(X, Y, 1, 2); p.wire('metal2', X, Y, E, Y); p.via(E, Y, 2, 3)
                    p.wire('metal3', E, Y, E, ty)
                    p.via(E, ty, 2, 3)
                    lo_, hi_ = reach.get(net, (math.inf, -math.inf))
                    reach[net] = (min(lo_, E), max(hi_, E))
                for tx_, ty_, ti in g.get('taps', ()):
                    net = d.nodes[ti]; X, Y = ox + tx_, oy + ty_; ty = r['track'][net]
                    p.net = net
                    p.wire('metal3', X, Y, X, ty)
                    via_array(p, X, ty, .4, r['tw'][net], 2, 3)
                    lo_, hi_ = reach.get(net, (math.inf, -math.inf))
                    reach[net] = (min(lo_, X), max(hi_, X))
            r['reach'] = reach
        for d, g, ri, x in self.cap_place:
            r = self.rows[ri]
            ox = _snap(xo + x)
            oy = _snap(r['pin_y'] - g['y_tab'])
            k = prim_key(d)
            p.cmds += [f'getcell {k} child 0 0 parent {ox:.3f} {oy:.3f}', f'identify {d.name}']
            placed.append(d.name)
            for e in g['extra']:
                _, layer, x1, y1, x2, y2 = e
                p.net = None
                p.rect(layer, ox + x1, oy + y1, ox + x2, oy + y2)
            for t, ((px, py), net) in enumerate(zip(g['pins'], d.nodes)):
                X, Y = ox + px, oy + py
                p.net = net
                p.via(X, Y, 3, 5 if t == 0 else 4)
                ty = r['track'][net]
                p.wire('metal3', X, Y, X, ty)
                p.via(X, ty, 2, 3)
                lo_, hi_ = r['reach'].get(net, (math.inf, -math.inf))
                r['reach'][net] = (min(lo_, X), max(hi_, X))
        for ri, r in enumerate(self.rows):
            for net, (xa, xe) in r['reach'].items():
                ty = r['track'][net]
                p.net = net
                if net in self.trunk and self.trunk[net][2] <= ri <= self.trunk[net][3]:
                    tx = xo + self.trunk[net][0]
                    xa, xe = min(xa, tx), max(xe, tx)
                    if net in WIDE:
                        via_array(p, tx, ty, self.trunk[net][1], r['tw'][net], 2, 3)
                        xa, xe = min(xa, tx - self.trunk[net][1] / 2 + .2), max(xe, tx + self.trunk[net][1] / 2 - .2)
                    else:
                        p.via(tx, ty, 2, 3)
                if xe > xa or net in WIDE:
                    hw = max(r['tw'][net], .4) / 2 if net in WIDE else TW / 2   # wide: full width in y, 0.2 um end extension in x
                    p.rect('metal2', xa - .2, ty - hw, xe + .2, ty + hw)
        port_y = 1.0
        for n, (tx, tw, lo, hi) in self.trunk.items():
            ylo = port_y if lo < 0 else self.rows[lo]['track'][n]
            yhi = self.rows[hi]['track'][n]
            p.net = n
            if n in WIDE:      # wide trunk: extend only over its own end tracks, not tw/2 into the device rows
                ea = self.rows[lo]['tw'][n] / 2 if lo >= 0 else .2
                eb = self.rows[hi]['tw'][n] / 2
                p.rect('metal3', xo + tx - tw / 2, ylo - max(ea, .2), xo + tx + tw / 2, max(yhi, ylo + 1.) + max(eb, .2))
            else:
                p.wire('metal3', xo + tx, ylo, xo + tx, max(yhi, ylo + 1.), width=tw)
        p.net = None
        req = ad.requests_from_shapes(p.shapes, terminals)
        F.port_diode_requests(req, self.ports, terminals, p.shapes)
        dcmds, diodes = ad.plan(req, [s[:5] for s in p.shapes], keepouts, taps=taps)
        p.cmds += dcmds
        # Top-cell pins (assembly 2026-11-24, same rule as rfrx_flow): >= 2 um pitch, >= 0.8 um wide, on the bottom edge.
        # Wide trunks (WIDE: supplies / stage-current nets) run straight down to the edge at full width (no added R).
        # Narrow ports: M3 trunk down to its own M4 row (rows rise with trunk x), M4 to a free pin column, M3 drop.
        # A pin column keeps >= PIN_SPACE from every wide column and from the trunk extension of every port left of it.
        order = sorted(self.ports, key=lambda n: self.trunk[n][0])
        narrow = [n for n in order if n not in WIDE and n not in POWER]
        rows_y, yy = {}, 3.0
        for n in narrow:
            yy += .22; rows_y[n] = yy; yy += .22 + .5
        band = _snap(yy + 1.0)
        cols = [(xo + self.trunk[n][0], self.trunk[n][1]) for n in order if n in WIDE or n in POWER]
        px, pinned = {}, []
        for n in narrow:
            t_ = xo + self.trunk[n][0]
            x_ = t_
            left = [(xo + self.trunk[m][0], max(self.trunk[m][1], .4)) for m in narrow if self.trunk[m][0] < self.trunk[n][0]]
            for _ in range(2000):
                bad = [c for c in cols + left + pinned if abs(c[0] - x_) < c[1] / 2 + F.PIN_W / 2 + F.PIN_SPACE - 1e-6
                       and not (c in left and abs(c[0] - t_) < 1e-6 and x_ == t_)]
                if not bad:
                    break
                x_ = _snap(max(c[0] + c[1] / 2 for c in bad) + F.PIN_W / 2 + F.PIN_SPACE)
            px[n] = x_
            pinned.append((x_, F.PIN_W))
        for i, n in enumerate(self.ports, 1):
            tx, tw = xo + self.trunk[n][0], self.trunk[n][1]
            p.net = n
            if n in WIDE or n in POWER:
                p.rect('metal3', tx - tw / 2, -band, tx + tw / 2, port_y + .2)
                p.net = None
                p.cmds += [f'box values {tx - tw / 2:.3f} {-band:.3f} {tx + tw / 2:.3f} {-band + 2.0:.3f}',
                           f'label {n} FreeSans 0.25 0 0 0 c metal3', f'port make {i}']
                continue
            yr = rows_y[n] - band
            p.wire('metal3', tx, yr, tx, port_y, width=tw)
            p.via(tx, yr, 3, 4)
            p.wire('metal4', tx, yr, px[n], yr, width=.44)
            p.via(px[n], yr, 3, 4)
            p.wire('metal3', px[n], yr, px[n], -band + F.PIN_W / 2, width=F.PIN_W)
            p.net = None
            p.cmds += [f'box values {px[n] - F.PIN_W / 2:.3f} {-band:.3f} {px[n] + F.PIN_W / 2:.3f} {-band + 2.0:.3f}',
                       f'label {n} FreeSans 0.25 0 0 0 c metal3', f'port make {i}']
        # internal net names (readable extraction / probing): one M2 label per net on its first track
        done = set(self.ports) | set(POWER)
        for ri, r in enumerate(self.rows):
            for net, (xa, xe) in r['reach'].items():
                if net in done:
                    continue
                done.add(net)
                ty = r['track'][net]
                xx = (xa + xe) / 2 if xe > xa else xa
                if net in self.trunk and self.trunk[net][2] <= ri <= self.trunk[net][3]:
                    xx = xo + self.trunk[net][0]
                p.cmds += [f'box values {xx - .1:.3f} {ty - .1:.3f} {xx + .1:.3f} {ty + .1:.3f}',
                           f'label {net} FreeSans 0.2 0 0 0 c metal2']
        p.cmds += same_net_fixups(p.shapes)
        flat = [f'select cell {nm}\nflatten -doinplace' for nm in placed]
        script = ['crashbackups stop', 'drc off', f'load {name}', 'units microns', 'snap internal'] + p.cmds + \
            flat + ['select top cell', 'save', 'quit -noprompt']
        return script, diodes


SPACE = {'metal1': .23, 'metal2': .28, 'metal3': .28, 'metal4': .28, 'metal5': .28}
VSPACE = {'via1': .26, 'via2': .26, 'via3': .26, 'via4': .26}


def same_net_fixups(shapes):
    """Fork J: Magic DRC is not net-aware.  Two same-net shapes on one layer closer than the
    spacing rule (but not touching) are flagged; bridge such metal gaps, and erase the second of two
    same-net vias closer than the via spacing (their metal pads overlap, so connectivity stays)."""
    cmds = []
    by = {}
    for s in shapes:
        if s[5] is not None:
            by.setdefault((s[0], s[5]), []).append(s)
    dropped = set()
    for (layer, net), ss in by.items():
        ss = sorted(set(ss), key=lambda s: (s[1], s[2]))
        if layer in VSPACE:
            for i, a in enumerate(ss):
                if a in dropped:
                    continue
                for b in ss[i + 1:]:
                    if b[1] - a[3] > VSPACE[layer]:
                        break
                    if b in dropped or b[1:5] == a[1:5]:
                        continue
                    gx = max(b[1] - a[3], a[1] - b[3]); gy = max(b[2] - a[4], a[2] - b[4])
                    if (gx > 1e-6 or gy > 1e-6) and max(gx, gy) < VSPACE[layer]:
                        dropped.add(b)
                        cmds += [f'box values {b[1]:.3f} {b[2]:.3f} {b[3]:.3f} {b[4]:.3f}', f'erase {layer}']
                        lo_m = int(layer[3:]); cx, cy = (b[1] + b[3]) / 2, (b[2] + b[4]) / 2
                        ux1, uy1 = min(cx, (a[1] + a[3]) / 2) - .2, min(cy, (a[2] + a[4]) / 2) - .2
                        ux2, uy2 = max(cx, (a[1] + a[3]) / 2) + .2, max(cy, (a[2] + a[4]) / 2) + .2
                        cmds += [f'box values {ux1:.3f} {uy1:.3f} {ux2:.3f} {uy2:.3f}',
                                 f'paint metal{lo_m}', f'paint metal{lo_m + 1}']
            continue
        if layer not in SPACE:
            continue
        sp = SPACE[layer]
        for i, a in enumerate(ss):
            for b in ss[i + 1:]:
                if b[1] - a[3] > sp:
                    break
                gx = max(b[1] - a[3], a[1] - b[3]); gy = max(b[2] - a[4], a[2] - b[4])
                if gx > 1e-6 and gx < sp and gy < 0:          # side-by-side, overlapping in y
                    x1, x2 = min(a[3], b[3]), max(a[1], b[1])
                    if x1 > x2: x1, x2 = x2, x1
                    y1, y2 = max(a[2], b[2]), min(a[4], b[4])
                    cmds += [f'box values {x1:.3f} {y1:.3f} {x2:.3f} {y2:.3f}', f'paint {layer}']
                elif gy > 1e-6 and gy < sp and gx < 0:        # stacked, overlapping in x
                    y1, y2 = min(a[4], b[4]), max(a[2], b[2])
                    if y1 > y2: y1, y2 = y2, y1
                    x1, x2 = max(a[1], b[1]), min(a[3], b[3])
                    cmds += [f'box values {x1:.3f} {y1:.3f} {x2:.3f} {y2:.3f}', f'paint {layer}']
    return cmds


def build(devs, geoms, ports, rw):
    L = Lay(devs, geoms, ports, rw)
    L.place_caps()
    L.trunks()
    L.verify_caps()
    return L


LNA_ROW_WIDTH = 190.   # LNA core (round 3: wide current-carrying tracks and per-strip taps; 190 gives the smallest area) (tank and degeneration spirals are separate cells)


def build_compact(spice, top, work, row_width=None, dry=False):
    """Lay out `top` (flat) from `spice` into `work`; DRC + extraction + LVS. Returns a build_block()-style dict."""
    global WIDE
    WIDE = WIDE_LNA if top == 'pt_lna' else {}
    src = Path(spice).resolve(); work = Path(work).resolve()
    subs = F.parse_spice(src)
    devs, ports = flatten(subs, top)
    work.mkdir(parents=True, exist_ok=True)
    (work / src.name).write_text(src.read_text())
    geoms = F.build_primitives(work, devs)
    for d in devs:
        if heavy(d) and d.nf > 1:
            geoms[(prim_key(d), d.name)] = heavy_geom(work, d, geoms[prim_key(d)])
    if row_width:
        rws = [float(row_width)]
    else:
        widest = max(geoms[prim_key(d)]['fp'][2] - geoms[prim_key(d)]['fp'][0] for d in devs) + GAP
        rws = [widest * 1.04 ** k for k in range(50)]
    best = None
    for rw in rws:
        try:
            L = build(devs, geoms, ports, rw)
        except RuntimeError:
            if len(rws) == 1:
                raise
            continue
        a = L.W * L.height
        if max(L.W / L.height, L.height / L.W) > 2.0:
            continue
        if best is None or a < best[0]:
            best = (a, rw, L)
    a, rw, L = best
    info = dict(rw=round(rw, 1), width=round(L.W, 1), height=round(L.height, 1), area_est=round(a),
                rows=[(len(r['items']), len(r['track']), round(r['row_h'], 1), round(r['used'], 1)) for r in L.rows],
                ncaps=len(L.cap_place), ntrunks=len(L.trunk))
    if dry:
        return info
    for f in (f'{top}.mag', f'{top}.ext', f'{top}.gds'):
        if (work / f).exists():
            (work / f).unlink()
    script, diodes = L.paint(top)
    (work / f'{top}.tcl').write_text('\n'.join(script) + '\n')
    F.magic(work, f'{top}.tcl')
    cmds = ['crashbackups stop', f'load {top}', 'select top cell', 'expand', 'extract all',
            'ext2spice lvs', f'ext2spice -o {top}.lvs.spice', 'ext2spice lvs', 'ext2spice cthresh 0',
            f'ext2spice -o {top}.ext.spice', 'select top cell', 'set f [open bbox.txt w]', 'puts $f [box values]',
            'close $f', 'drc euclidean on', 'drc style drc(full)', 'drc check', 'drc catchup',
            'set f [open drc-count.txt w]', 'puts $f [drc list count total]', 'close $f', 'drc count total',
            'set f [open drc-details.txt w]', 'puts $f [drc listall why]', 'close $f',
            'cif ostyle gdsii', f'gds write {top}.gds', 'quit -noprompt']
    (work / 'check.tcl').write_text('\n'.join(cmds) + '\n')
    F.magic(work, 'check.tcl')
    tot = re.findall(r'Total DRC errors found: (\d+)', (work / 'check.tcl.log').read_text())
    bb = [float(v) * .005 for v in (work / 'bbox.txt').read_text().split()]
    ref = src.read_text()
    lines = ad.spice_lines(diodes, prefix='DANT_')
    if lines:
        k = re.search(rf'(?mi)^\.subckt\s+{top}\s', ref).start(); e = ref.lower().index('.ends', k)
        ref = ref[:e] + '\n'.join(lines) + '\n' + ref[e:]
    (work / 'lvs_reference.spice').write_text(ref)
    lv = F.lvs(work, f'{top}.lvs.spice', top, 'lvs_reference.spice', top)
    info.update(antenna_diodes_placed=sum(1 for q in diodes if q.get('placed')),
                antenna_diodes_failed=sum(1 for q in diodes if not q.get('placed')))
    return dict(drc_count=int(tot[-1]) if tot else None, drc_raw=(work / 'drc-count.txt').read_text().strip(),
                bbox_um=[round(v, 2) for v in bb], area_um2=round((bb[2] - bb[0]) * (bb[3] - bb[1]), 0), lvs=lv,
                layout_generator='lna_layout.py (compact flat, MIMs over active)', compact=info, cells={})


def main():
    dry = '--dry' in sys.argv
    args = [a for a in sys.argv[3:] if not a.startswith('--')]
    r = build_compact(sys.argv[1], 'pt_lna', sys.argv[2], float(args[0]) if args else None, dry=dry)
    print(json.dumps(r if dry else {k: v for k, v in r.items() if k != 'compact'}, default=str), flush=True)


if __name__ == '__main__':
    main()
