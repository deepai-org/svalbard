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


def lefted(ivs, gap=1.2):
    tracks, tidx = [], {}
    for lo_, hi_, n in sorted(ivs):
        for ti, last in enumerate(tracks):
            if last + gap < lo_:
                tracks[ti] = hi_; tidx[n] = ti; break
        else:
            tracks.append(hi_); tidx[n] = len(tracks) - 1
    return tidx, len(tracks)


class Lay:
    def __init__(self, devs, geoms, ports, rw):
        self.devs, self.geoms, self.ports, self.rw = devs, geoms, ports, rw
        hclass = lambda it: round(math.log((it[1]['fp'][3] - it[1]['fp'][1]) + 1.) / math.log(1.6))
        act = [(d, geoms[prim_key(d)]) for d in devs if d.kind != 'cap']
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
                cx += g['fp'][2] - g['fp'][0] + GAP
            self.rows.append(dict(items=items, pos=pos, esc=esc, used=cx,
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
            for n, (tx, _, lo, hi) in trunk.items():
                if lo <= ri <= hi and n in ext:
                    ext[n] = (min(ext[n][0], tx), max(ext[n][1], tx))
            tidx, ntr = lefted([(a, b, n) for n, (a, b) in ext.items()])
            r['band0'] = y
            r['track'] = {n: y + .6 + tidx[n] * TP for n in tidx}
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
            w = PWR_W if n in POWER else .4
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
                    p.via(tx, ty, 2, 3)
                if xe > xa:
                    p.wire('metal2', xa, ty, xe, ty, width=TW)
        port_y = 1.0
        for n, (tx, tw, lo, hi) in self.trunk.items():
            ylo = port_y if lo < 0 else self.rows[lo]['track'][n]
            yhi = self.rows[hi]['track'][n]
            p.net = n
            p.wire('metal3', xo + tx, ylo, xo + tx, max(yhi, ylo + 1.), width=tw)
        p.net = None
        req = ad.requests_from_shapes(p.shapes, terminals)
        dcmds, diodes = ad.plan(req, [s[:5] for s in p.shapes], keepouts, taps=taps)
        p.cmds += dcmds
        for i, n in enumerate(self.ports, 1):
            xx = xo + self.trunk[n][0]
            p.cmds += [f'box values {xx - .2:.3f} {port_y - .2:.3f} {xx + .2:.3f} {port_y + .2:.3f}',
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


LNA_ROW_WIDTH = 190.   # RC-16j/k LNTA core (two tank spirals are separate cells)


def build_compact(spice, top, work, row_width=None, dry=False):
    """Lay out `top` (flat) from `spice` into `work`; DRC + extraction + LVS. Returns a build_block()-style dict."""
    src = Path(spice).resolve(); work = Path(work).resolve()
    subs = F.parse_spice(src)
    devs, ports = flatten(subs, top)
    work.mkdir(parents=True, exist_ok=True)
    (work / src.name).write_text(src.read_text())
    geoms = F.build_primitives(work, devs)
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
