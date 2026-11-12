"""Row/channel layout generator, DRC, extraction and LVS for analog/rf_tx.

Placement and routing are deliberately simple and inspectable (same idea as
``analog/pads/layout.py``):

* every device is one Magic gf180mcu PCell (multi-finger MOS with this
  generator's own gate bar and source/drain straps, or a poly resistor);
* devices sit in rows; below each row is a routing channel with one Metal4
  lane per net used by that row;
* every device terminal escapes on Metal2 to its own Metal3 vertical, which
  drops to its net's lane in the channel;
* every net has one Metal5 trunk in a bank on the left; lanes join their
  trunk with a via stack. Port labels sit on the trunks at the top edge.

Wide nets (supplies and high-current RF nodes) get wider straps, escapes,
lanes, trunks and via areas (Magic fills via areas with cut arrays).
Extraction captures capacitance only; wire/via resistance is not extracted.
"""
import hashlib
import json
import math
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # analog/antenna_diodes.py
import antenna_diodes as ad  # noqa: E402

DIGITAL_IMAGE = 'svalbard/librelane-gf180-canary:2026.08'
PDK = '/pdk/gf180mcuD'
GRID = 0.005


def snap(v):
    return round(round(v / GRID) * GRID, 4)


def docker_magic(work, script, timeout=1800):
    work = Path(work).resolve()
    cmd = ['docker', 'run', '--rm', '--network', 'none', '--cpus', '3', '--memory', '6g',
           '--entrypoint', '/bin/sh', '-v', f'{work}:/work', '-w', '/work', DIGITAL_IMAGE,
           '-c', f'magic -dnull -noconsole -rcfile {PDK}/libs.tech/magic/gf180mcuD.magicrc /work/{script}']
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    (Path(work) / (script + '.log')).write_text(r.stdout + r.stderr)
    r.check_returncode()
    return r


def docker_netgen(work, layout_spice, layout_cell, source_spice, source_cell, report, timeout=1800):
    work = Path(work).resolve()
    cmd = ['docker', 'run', '--rm', '--network', 'none', '--cpus', '3', '--memory', '6g',
           '--entrypoint', '/bin/sh', '-v', f'{work}:/work', '-w', '/work', DIGITAL_IMAGE,
           '-c', f'netgen -batch lvs "{layout_spice} {layout_cell}" "{source_spice} {source_cell}" '
                 f'{PDK}/libs.tech/netgen/gf180mcuD_setup.tcl {report}']
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    (Path(work) / (report + '.log')).write_text(r.stdout + r.stderr)
    return r


def image_id(name):
    r = subprocess.run(['docker', 'image', 'inspect', name, '--format', '{{.Id}}'], capture_output=True, text=True)
    return r.stdout.strip()


def mag_rects(path):
    layer, out = None, {}
    for line in Path(path).read_text().splitlines():
        if line.startswith('<< '):
            layer = line[3:-3]
        elif line.startswith('rect ') and layer:
            out.setdefault(layer, []).append([int(v) * GRID for v in line.split()[1:5]])
    return out


# ---------------------------------------------------------------------------
# Primitive cells
# ---------------------------------------------------------------------------
def prim_key(d):
    if hasattr(d, 'nf'):
        k = ('mos', d.model, d.w, d.l, d.nf)
        return k + ('iso',) if getattr(d, 'iso', False) else k
    return ('res', d.model, d.w, d.l)


def prim_command(key, cell):
    if key[0] == 'mos':
        _, model, w, l, nf = key[:5]
        return (f'set c [magic::gencell_makecell gf180mcu::{model} w {w} l {l} nf {nf} guard 1 '
                f'topc 1 botc 0 full_metal 1 gate_to_polycont 0.6 diff_gate_space 0.3]\n'
                f'load $c\nsave {cell}\nload ws\n')
    _, model, w, l = key
    guard = 0 if model in UNGUARDED_RES else 1
    return (f'set c [magic::gencell_makecell gf180mcu::{model} w {w} l {l} guard {guard} full_metal 1]\n'
            f'load $c\nsave {cell}\nload ws\n')


# Isolated p-well (DNWELL) NMOS: the PCell's own p-well and p-tap ring become the isolated body; around it an
# N+ tap ring (the DNWELL contact, net VDD) and the DNWELL. gf180mcuD rules (Magic deck): DN.1 w>=1.7,
# DN.2a s>=2.5, pwell-in-dnwell enclosure 2.5, N+ tap enclosure by dnwell 0.62, dnwell-nwell 3.1, pwell-dnwell 1.5.
ISO_GAP = 1.0        # p-well edge -> N+ ring inner edge
ISO_RING = 1.0       # N+ tap ring width (its N-well image must meet NW.1a 0.86)
ISO_DNW = 2.7        # dnwell enclosure of the p-well (>= 2.5, and >= gap + ring + DF.4b 0.62)
ISO_PG_SPACE = 2.6   # dnwell -> P+ substrate guard ring (DN.3 ring required; DF.18 >= 2.5)
ISO_PG = 0.8         # P+ guard ring width
ISO_HALO = 0.4       # keep-out beyond the P+ ring (DF.19 NCOMP 3.2 and dnwell-nwell 3.1 are inside the ring)


def _ring(x0, y0, x1, y1, a, b):
    return [(x0 - b, y0 - b, x1 + b, y0 - a), (x0 - b, y1 + a, x1 + b, y1 + b),
            (x0 - b, y0 - b, x0 - a, y1 + b), (x1 + a, y0 - b, x1 + b, y1 + b)]


def iso_command(cell, path):
    r = mag_rects(path)
    x0, y0, x1, y1 = (min(rc[0] for rc in r['pwell']), min(rc[1] for rc in r['pwell']),
                      max(rc[2] for rc in r['pwell']), max(rc[3] for rc in r['pwell']))
    cmds = [f'load {cell}', 'units microns']
    e = 0.08   # contact inset: diffusion (CO.4 0.065) and metal1 (CO.6 0.055) surround
    pg_a = ISO_DNW + ISO_PG_SPACE
    for (a, b, diff, cont) in ((ISO_GAP, ISO_GAP + ISO_RING, 'nsubdiff', 'nsubdiffcont'),
                               (pg_a, pg_a + ISO_PG, 'psubdiff', 'psubdiffcont')):
        ring = _ring(x0, y0, x1, y1, a, b)
        for rc in ring:
            cmds += ['box values ' + ' '.join(str(snap(v)) for v in rc), f'paint {diff}', 'paint metal1']
        for rc in ring:
            cmds += ['box values ' + ' '.join(str(snap(v)) for v in (rc[0] + e, rc[1] + e, rc[2] - e, rc[3] - e)),
                     f'paint {cont}']
    cmds += ['box values ' + ' '.join(str(snap(v)) for v in (x0 - ISO_DNW, y0 - ISO_DNW, x1 + ISO_DNW, y1 + ISO_DNW)),
             'paint dnwell', 'units internal', 'save', 'load ws']
    return '\n'.join(cmds) + '\n'


def prim_geometry(key, path):
    """Terminal anchor points (um, cell coordinates) for routing."""
    r = mag_rects(path)
    allx = [v for rects in r.values() for rc in rects for v in (rc[0], rc[2])]
    ally = [v for rects in r.values() for rc in rects for v in (rc[1], rc[3])]
    # The checkpaint layer is a large halo; use well/diffusion extents for the body.
    iso = 'deepnwell' in r
    body_layers = (['deepnwell'] if iso else [k for k in r if k in ('pwell', 'nwell')]) or [k for k in r if k != 'checkpaint']
    bb = [min(rc[0] for k in body_layers for rc in r[k]), min(rc[1] for k in body_layers for rc in r[k]),
          max(rc[2] for k in body_layers for rc in r[k]), max(rc[3] for k in body_layers for rc in r[k])]
    if iso:
        bb = [bb[0] - ISO_HALO, bb[1] - ISO_HALO, bb[2] + ISO_HALO, bb[3] + ISO_HALO]
    ring = (r.get('psubdiffcont', []) + ([] if iso else r.get('nsubdiffcont', [])) + r.get('mvpsubdiffcont', [])
            + r.get('mvnsubdiffcont', []))
    if iso:   # body tap = the PCell's p-ring inside the p-well (the outer P+ ring is the substrate guard)
        pw = r['pwell']
        px0, py0, px1, py1 = (min(rc[0] for rc in pw), min(rc[1] for rc in pw), max(rc[2] for rc in pw), max(rc[3] for rc in pw))
        inside = lambda rc: rc[0] >= px0 and rc[2] <= px1 and rc[1] >= py0 and rc[3] <= py1
        pg = [rc for rc in r['psubdiffcont'] if not inside(rc)]
        ring = [rc for rc in ring if inside(rc)]
    ring_right_x = max((rc[0] + rc[2]) / 2 for rc in ring) if ring else None
    m1 = r.get('metal1') or r['polycontact']
    if iso:   # the p-tap ring's metal1 only (inside the p-well); the N+ and P+ rings sit outside it
        m1 = [rc for rc in m1 if inside(rc)]
    ring_bottom_y = min(rc[1] for rc in m1) + 0.115
    geo = dict(bbox=bb, ring_right_x=ring_right_x, ring_bottom_y=ring_bottom_y)
    if iso:
        nr = r['nsubdiffcont']
        geo['nw'] = (max((rc[0] + rc[2]) / 2 for rc in nr), max((rc[1] + rc[3]) / 2 for rc in nr))
        geo['pg'] = (max((rc[0] + rc[2]) / 2 for rc in pg), min((rc[1] + rc[3]) / 2 for rc in pg))
    if key[0] == 'mos':
        diffc = sorted(r.get('ndiffc', []) + r.get('pdiffc', []) + r.get('mvndiffc', []) + r.get('mvpdiffc', []),
                       key=lambda a: a[0])   # mv*: 6 V devices (nfet_06v0 cascode)
        cols = [((a[0] + a[2]) / 2, a[1], a[3]) for a in diffc]
        pc = r['polycontact']
        geo.update(cols=cols, gate=[min(a[0] for a in pc), min(a[1] for a in pc),
                                    max(a[2] for a in pc), max(a[3] for a in pc)])
    else:
        pc = sorted(r['polycontact'], key=lambda a: a[1])
        geo.update(bottom=pc[0], top=pc[-1])
    return geo


# ---------------------------------------------------------------------------
# Painter
# ---------------------------------------------------------------------------
class Painter:
    def __init__(self):
        self.cmds = []
        self.net = None       # net of the shapes being drawn (antenna-diode planning)
        self.shapes = []      # (layer, x1, y1, x2, y2, net)

    def rect(self, layer, x1, y1, x2, y2):
        x1, x2 = sorted((x1, x2)); y1, y2 = sorted((y1, y2))
        self.cmds.append(f'box values {snap(x1)} {snap(y1)} {snap(x2)} {snap(y2)}')
        self.cmds.append(f'paint {layer}')
        self.shapes.append((layer, snap(x1), snap(y1), snap(x2), snap(y2), self.net))

    def via(self, x, y, low, high, w=0.4, h=None):
        """Via stack from metal<low> to metal<high> centred at (x, y); w x h landing.
        Magic fills large via areas with arrays of cuts on GDS output."""
        h = w if h is None else h
        dims = {}
        for m in range(low, high + 1):
            mw = max(w, 0.38 if m == 1 else 0.44 if m == 5 else 0.4)
            mh = max(h, 0.38 if m == 1 else 0.44 if m == 5 else 0.4)
            dims[m] = (mw, mh)
            self.rect(f'metal{m}', x - mw / 2, y - mh / 2, x + mw / 2, y + mh / 2)
        for m in range(low, high):
            cw = max(0.26, min(dims[m][0], dims[m + 1][0]) - 0.12)
            ch = max(0.26, min(dims[m][1], dims[m + 1][1]) - 0.12)
            if m > 1:
                cw, ch = max(cw, 0.28), max(ch, 0.28)
            self.rect(f'via{m}', x - cw / 2, y - ch / 2, x + cw / 2, y + ch / 2)

    def hwire(self, layer, x1, x2, y, w):
        self.rect(layer, min(x1, x2) - w / 2, y - w / 2, max(x1, x2) + w / 2, y + w / 2)

    def vwire(self, layer, x, y1, y2, w):
        self.rect(layer, x - w / 2, min(y1, y2) - w / 2, x + w / 2, max(y1, y2) + w / 2)


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------
# The gf180mcu ppolyf_s / ppolyf_u PCells with a guard ring place the ring PPLUS 0.08-0.2 um from the
# resistor PPLUS, which the KLayout GF180 deck flags (PP.2). These resistors are drawn without a ring;
# their third (substrate) terminal is the p-substrate, tied to VSS by the neighbouring NMOS taps.
UNGUARDED_RES = {'ppolyf_s', 'ppolyf_u'}


def pin_list(d):
    """(terminal, net, side) with side 'L' or 'R' escape."""
    if hasattr(d, 'nf'):
        pl = [('S', d.s, 'L'), ('D', d.d, 'R'), ('G', d.g, 'R'), ('B', d.b, 'R')]
        return pl + [('NW', getattr(d, 'iso_net', 'VDD'), 'R'), ('PG', 'VSS', 'R')] if getattr(d, 'iso', False) else pl
    if d.model in UNGUARDED_RES:
        return [('B', d.b, 'L'), ('A', d.a, 'R')]
    return [('B', d.b, 'L'), ('A', d.a, 'R'), ('BODY', d.body, 'R')]


def build(circuit, work, *, wide=None, row_width=160.0, rows=None, trunk_width=None,
          lane_width=None, gap=1.2, lane_order=None, trunk_order=None, inline_trunks=False):
    """Generate layout for ``circuit`` in ``work`` (must be empty). Returns report dict."""
    work = Path(work).resolve()
    work.mkdir(parents=True, exist_ok=True)
    if list(work.glob('*.mag')):
        raise FileExistsError('use an empty output directory')
    wide = wide or {}
    trunk_width = trunk_width or {}
    lane_width = lane_width or {}

    def rw(net):  # route width for straps/escapes
        return wide.get(net, 0.4)

    devices = list(circuit.devices)
    keys = sorted({prim_key(d) for d in devices}, key=str)
    cells = {k: f'prim{i}' for i, k in enumerate(keys)}
    script = 'crashbackups stop\nload ws\nunits internal\n' + ''.join(prim_command(k, cells[k]) for k in keys) + 'quit -noprompt\n'
    (work / 'prims.tcl').write_text(script)
    docker_magic(work, 'prims.tcl')
    iso_keys = [k for k in keys if k[-1] == 'iso']
    if iso_keys:
        (work / 'iso.tcl').write_text('crashbackups stop\n' + ''.join(iso_command(cells[k], work / f'{cells[k]}.mag')
                                                                    for k in iso_keys) + 'quit -noprompt\n')
        docker_magic(work, 'iso.tcl')
    geo = {k: prim_geometry(k, work / f'{cells[k]}.mag') for k in keys}

    # --- per-device local routing plan (relative coordinates) ------------
    P = Painter()
    local = {}
    for d in devices:
        k = prim_key(d); g = geo[k]
        x0, y0, x1, y1 = g['bbox']
        pins = {}
        if k[0] == 'mos':
            cols = g['cols']
            W = d.w
            s_net, d_net = d.s, d.d
            small = W < 2.0 or d.nf == 1
            ws = 0.4 if small else min(rw(s_net), 1.2)
            wd = 0.4 if small else min(rw(d_net), 1.2)
            if small:
                ys = yd = (cols[0][1] + cols[0][2]) / 2
            else:
                ys = cols[0][1] + 0.1 + ws / 2
                yd = cols[0][2] - 0.1 - wd / 2
                if len(cols) > 2 and yd - ys < (ws + wd) / 2 + 0.3:
                    raise ValueError(f'{d.name}: finger too short for straps')
            gx0, gy0, gx1, gy1 = g['gate']
            yg = (gy0 + gy1) / 2
            pins['S'] = dict(cols=[c for i, c in enumerate(cols) if i % 2 == 0], y=ys, w=ws)
            pins['D'] = dict(cols=[c for i, c in enumerate(cols) if i % 2 == 1], y=yd, w=wd)
            pins['G'] = dict(x0=gx0, x1=gx1, y=yg)
            pins['B'] = dict(x=g['ring_right_x'], y=g['ring_bottom_y'])
            if 'nw' in g:
                pins['NW'] = dict(x=g['nw'][0], y=g['nw'][1])
                pins['PG'] = dict(x=g['pg'][0], y=g['pg'][1])
        else:
            bot, top = g['bottom'], g['top']
            pins['B'] = dict(x0=bot[0], x1=bot[2], y=(bot[1] + bot[3]) / 2)
            pins['A'] = dict(x0=top[0], x1=top[2], y=(top[1] + top[3]) / 2)
            if g['ring_right_x'] is not None:
                pins['BODY'] = dict(x=g['ring_right_x'], y=g['ring_bottom_y'])
        # escape x offsets
        esc = {}
        xr = x1 + 0.5
        xl = x0 - 0.5
        for term, net, side in pin_list(d):
            w = rw(net)
            if side == 'R':
                esc[term] = xr + w / 2; xr += w + 0.45
            else:
                esc[term] = xl - w / 2; xl -= w + 0.45
        local[d.name] = dict(key=k, bbox=(x0, y0, x1, y1), pins=pins, esc=esc, left=xl, right=xr)

    # --- placement ------------------------------------------------------
    if rows is None:
        rows, cur, cw = [], [], 0.0
        for d in devices:
            L = local[d.name]; wdt = L['right'] - L['left'] + gap
            if cur and cw + wdt > row_width:
                rows.append(cur); cur, cw = [], 0.0
            cur.append(d.name); cw += wdt
        if cur:
            rows.append(cur)
    byname = {d.name: d for d in devices}
    placed = set(n for r in rows for n in r)
    if placed != set(byname) or sum(len(r) for r in rows) != len(byname):
        raise ValueError('rows must place every device exactly once')

    nets = circuit.nets()
    ports = circuit.ports
    tw = {n: trunk_width.get(n, max(0.44, rw(n))) for n in nets}
    lw = {n: lane_width.get(n, rw(n)) for n in nets}
    row_of = {}
    for ri, row in enumerate(rows):
        for name in row:
            for _, net, _ in pin_list(byname[name]):
                row_of.setdefault(net, set()).add(ri)
    trunked = [n for n in nets if n in ports or len(row_of[n]) > 1]
    # trunk bank on the left (ports first, in port order)
    tx, x = {}, 0.0
    torder = list(trunk_order or [])
    def tkey(n):
        if n in torder:
            return (0, torder.index(n), n) if torder.index(n) < torder.index('*') else (2, torder.index(n), n)
        return (1, n not in ports, ports.index(n) if n in ports else 0, n)
    if torder and '*' not in torder:
        torder.append('*')
    for n in sorted(trunked, key=tkey):
        x += tw[n] / 2 + 0.3; tx[n] = x; x += tw[n] / 2 + 0.3
    bank_right = x + 1.5
    if inline_trunks:
        # inline mode (rfdriver area pass, 2026-11-12): no trunk bank. Each multi-row net's Metal5 trunk runs over
        # the device rows at an x inside its own escape span, and each row's channel tracks are shared between
        # nets with disjoint x-spans (left-edge algorithm), instead of one dedicated lane per net.
        bank_right = 1.5
    # rows: x placement first
    y_top = 0.0
    lanes = {}  # (row, net) -> y
    rowinfo = []
    xposs = []
    for ri, row in enumerate(rows):
        xpos, cx = {}, bank_right
        for name in row:
            L = local[name]
            ox = cx - L['left']
            xpos[name] = ox
            cx = ox + L['right'] + gap
        xposs.append((xpos, cx))
    def esc_xs(ri, net):
        xpos = xposs[ri][0]
        return [xpos[n] + local[n]['esc'][t] for n in rows[ri] for t, nn, _ in pin_list(byname[n]) if nn == net]
    if inline_trunks:
        tx = {}
        placed_tr = []   # (x, w, rmin, rmax)
        def span(net):
            rs = sorted(row_of[net]); return (0 if net in ports else rs[0]), rs[-1]
        for net in sorted(trunked, key=lambda n: (-(span(n)[1] - span(n)[0]), n)):
            r0, r1 = span(net)
            xs = sorted(x for ri in row_of[net] for x in esc_xs(ri, net))
            lo, hi = xs[0], xs[-1]
            want = xs[len(xs) // 2]
            w = tw[net]
            def ok(x):
                return all(abs(x - px) >= (w + pw) / 2 + 0.6 for px, pw, a, b in placed_tr if not (b < r0 or a > r1))
            cand = None
            for k in range(0, 4000):
                for x in (want + 0.5 * k, want - 0.5 * k):
                    if lo - 3 <= x <= hi + 3 and x >= bank_right and ok(x):
                        cand = x; break
                if cand is not None:
                    break
            if cand is None:
                raise ValueError(f'no trunk x for {net}')
            tx[net] = cand; placed_tr.append((cand, w, r0, r1))
    cursor_y = y_top
    for ri, row in enumerate(rows):
        xpos, cx = xposs[ri]
        top_extent = max(local[n]['bbox'][3] for n in row)
        bot_extent = min(min(local[n]['bbox'][1], local[n]['pins'].get('B', {}).get('y', 0) - 0.5,
                             local[n]['pins'].get('BODY', {}).get('y', 0) - 0.5) for n in row)
        oy = cursor_y - 0.6 - top_extent
        lorder = list(lane_order or [])
        row_nets = sorted({net for n in row for _, net, _ in pin_list(byname[n])},
                          key=lambda n: (lorder.index(n) if n in lorder else len(lorder), n))
        ly = oy + bot_extent - 1.0
        if inline_trunks:
            iv = {}
            for net in row_nets:
                xs = esc_xs(ri, net) + ([tx[net]] if net in tx else [])
                iv[net] = (min(xs), max(xs))
            tracks = []   # [nets, right_end, width]
            for net in sorted(row_nets, key=lambda n: (iv[n][0], n)):
                a, b = iv[net]
                for tr in tracks:
                    last = tr[0][-1]
                    if tr[1] + (lw[last] + lw[net]) / 2 + 1.0 < a:
                        tr[0].append(net); tr[1] = b; tr[2] = max(tr[2], lw[net]); break
                else:
                    tracks.append([[net], b, lw[net]])
            for nets_, _, w in tracks:
                ly -= w / 2
                for net in nets_:
                    lanes[(ri, net)] = ly
                ly -= w / 2 + 0.5
        else:
            for net in row_nets:
                ly -= lw[net] / 2
                lanes[(ri, net)] = ly
                ly -= lw[net] / 2 + 0.5
        rowinfo.append(dict(names=row, xpos=xpos, oy=oy, right=cx, bottom=ly))
        cursor_y = ly - 0.4

    width = max(r['right'] for r in rowinfo) + 1.0
    height_bottom = cursor_y
    # --- paint ----------------------------------------------------------
    cmds = ['crashbackups stop', f'load {circuit.name}_hier', 'units microns']
    keepouts, terminals = [], []
    for ri, R in enumerate(rowinfo):
        for name in R['names']:
            d = byname[name]; L = local[name]; ox, oy = R['xpos'][name], R['oy']
            cmds.append(f'getcell {cells[L["key"]]} child 0 0 parent {snap(ox)} {snap(oy)}')
            cmds.append(f'identify X{name}')
            pins, esc = L['pins'], L['esc']
            bb = L['bbox']
            keepouts.append((ox + bb[0], oy + bb[1], ox + bb[2], oy + bb[3]))
            for term, net, side in pin_list(d):
                w = rw(net)
                pin = pins[term]
                ex = ox + esc[term]
                P.net = net
                if hasattr(d, 'nf'):
                    terminals.append((ex, oy + pin['y'], net, 'g' if term == 'G' else 'sd' if term in ('S', 'D') else 'x',
                                      d.w * d.nf * d.l if term == 'G' else 0.))
                if term in ('S', 'D'):
                    w = pin['w']
                    y = oy + pin['y']
                    xs = [ox + c[0] for c in pin['cols']]
                    h1 = max(0.38, w)
                    for xc in xs:
                        P.rect('metal1', xc - 0.19, y - h1 / 2, xc + 0.19, y + h1 / 2)
                        P.rect('via1', xc - 0.13, y - (h1 - 0.12) / 2, xc + 0.13, y + (h1 - 0.12) / 2)
                    P.hwire('metal2', min(xs + [ex]), max(xs + [ex]), y, w)
                elif term == 'G':
                    y = oy + pin['y']
                    gx0, gx1 = ox + pin['x0'], ox + pin['x1']
                    xm = (gx0 + gx1) / 2
                    P.rect('metal1', min(gx0, xm - 0.35), y - 0.19, max(gx1, xm + 0.35), y + 0.19)
                    P.via(xm, y, 1, 2)
                    P.hwire('metal2', xm, ex, y, 0.4)
                elif term in ('A', 'B') and 'x0' in pin:  # resistor heads
                    y = oy + pin['y']
                    hx0, hx1 = ox + pin['x0'], ox + pin['x1']
                    xm = (hx0 + hx1) / 2
                    span = max(0.0, hx1 - hx0 - 0.5)
                    P.rect('metal1', hx0, y - 0.19, hx1, y + 0.19)
                    w = min(max(0.4, w), 1.0)
                    P.rect('metal2', hx0, y - w / 2, hx1, y + w / 2)
                    P.rect('via1', xm - max(0.13, span / 2), y - 0.13, xm + max(0.13, span / 2), y + 0.13)
                    P.hwire('metal2', xm, ex, y, w)
                else:  # body ring (B of MOS, BODY of resistor)
                    y = oy + pin['y']
                    bx = ox + pin['x']
                    P.via(bx, y, 1, 2)
                    P.hwire('metal2', bx, ex, y, 0.4)
                # escape: via2 at pin row, metal3 down to lane, via3 + via4 up to lane/trunk
                ly = lanes[(ri, net)]
                w = rw(net)
                P.via(ex, y, 2, 3, w=w, h=pin.get('w', 0.4) if term in ('S', 'D') else (min(w, 1.0) if term in ('A', 'B') and 'x0' in pin else 0.4))
                P.vwire('metal3', ex, y, ly, w)
                P.via(ex, ly, 3, 4, w=w, h=lw[net])
        # lanes for this row
        for (rj, net), ly in lanes.items():
            P.net = net
            if rj != ri:
                continue
            xs = [R['xpos'][n] + local[n]['esc'][t] for n in R['names']
                  for t, nn, _ in pin_list(byname[n]) if nn == net]
            if net in tx:
                P.hwire('metal4', min(xs + [tx[net]]), max(xs + [tx[net]]), ly, lw[net])
                P.via(tx[net], ly, 4, 5, w=min(tw[net], 2.0) if tw[net] > 0.44 else 0.4, h=lw[net])
            elif max(xs) > min(xs):
                P.hwire('metal4', min(xs), max(xs), ly, lw[net])
    # trunks: from lowest lane to the top edge for ports, highest lane otherwise
    top_edge = y_top + 1.0
    for net in tx:
        ys = [y for (ri, n), y in lanes.items() if n == net]
        y_hi = top_edge if net in ports else max(ys)
        y_lo = min(ys)
        if y_hi - y_lo < 1.5:
            y_hi = y_lo + 1.5
        P.net = net
        P.vwire('metal5', tx[net], y_lo, y_hi, tw[net])
    P.net = None
    # antenna diodes (KLayout ANT.16): gate-only partial nets with long M2-M5 get an N+/Psub diode
    # (with its own substrate tap) under their own M3-M5 wire; returned as 'antenna_diodes'.
    req = ad.requests_from_shapes(P.shapes, terminals)
    dcmds, diodes = ad.plan(req, [s[:5] for s in P.shapes], keepouts)
    P.cmds += dcmds
    cmds += P.cmds
    for i, port in enumerate(ports, 1):
        x = tx[port]
        cmds += [f'box values {snap(x - 0.2)} {snap(top_edge - 0.6)} {snap(x + 0.2)} {snap(top_edge)}',
                 f'label {port} FreeSans 0.3 0 0 0 c metal5', f'port make {i}']
    for net in nets:
        if net in ports:
            continue
        (ri, y), = [min(((r, yy) for (r, n), yy in lanes.items() if n == net), key=lambda t: t[0])]
        if net in tx:
            x, layer = tx[net], 'metal5'
        else:
            R = rowinfo[ri]
            x = min(R['xpos'][n] + local[n]['esc'][t] for n in R['names']
                    for t, nn, _ in pin_list(byname[n]) if nn == net)
            layer = 'metal4'
        cmds += [f'box values {snap(x - 0.1)} {snap(y - 0.1)} {snap(x + 0.1)} {snap(y + 0.1)}',
                 f'label {net} FreeSans 0.2 0 0 0 c {layer}']
    flat = circuit.name
    cmds += ['save', 'select top cell', f'flatten {flat}', f'load {flat}', 'select top cell', 'save',
             'drc on', 'drc check', 'drc catchup',
             'set f [open drc-count.txt w]', 'puts $f [drc list count total]', 'close $f',
             'set f [open drc-details.txt w]', 'puts $f [drc listall why]', 'close $f',
             'extract all',
             'ext2spice lvs', f'ext2spice -o {flat}.lvs.spice',
             'ext2spice cthresh 0', 'ext2spice rthresh 0', f'ext2spice -o {flat}.ext.spice',
             f'gds write {flat}.gds', 'quit -noprompt']
    (work / 'layout.tcl').write_text('\n'.join(cmds) + '\n')
    docker_magic(work, 'layout.tcl')
    bbox = dict(x0=0.0, y0=height_bottom, x1=width, y1=top_edge)
    area = (bbox['x1'] - bbox['x0']) * (bbox['y1'] - bbox['y0'])
    drc = (work / 'drc-count.txt').read_text().strip()
    placements = {n: dict(origin=[R['xpos'][n], R['oy']], bbox=list(local[n]['bbox']), esc=local[n]['esc'],
                          pins={k: v for k, v in local[n]['pins'].items()})
                  for R in rowinfo for n in R['names']}
    (work / 'placements.json').write_text(json.dumps(placements, indent=1))
    return dict(cell=flat, rows=rows, bbox_um=bbox, area_um2=round(area, 1), drc_count=drc,
                trunk_x_um=tx, trunked_nets=len(tx), primitives={cells[k]: list(k) for k in keys},
                antenna_diodes=diodes)
