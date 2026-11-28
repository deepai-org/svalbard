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
PORT_DIODE = 12.0      # um^2 antenna diode on every gate-only control port (ASM-16: sized for >= 3 mm of chip-top Metal4,
                       # antenna_diodes.need_area({'metal4': 6000}, 0) = 11.45)
PORT_DIODE_SKIP = {'lo_p', 'lo_n'}   # txmix LO pins: driven ~0.1 mm from pt_lo_txbuf (LO-ASM-4); keep the GHz node light
ANALOG_PREFIX = ('lo', 'in', 'out', 'pad', 'bb', 'dac', 'rf', 'atb', 'ib', 'sum', 'i_', 'q_')   # analog signal ports: no diode

import os
# RFTX_IMAGE: the pinned canary image is not on every machine; the project KLayout image carries Magic 8.3.678 / netgen
# with the same PDK (open_pdks f6eeac7) under /foss/pdks (coordinator 2026-11-28: accepted, version recorded in the report)
DIGITAL_IMAGE = os.environ.get('RFTX_IMAGE', 'svalbard/librelane-gf180-canary:2026.08')
PDK = '/foss/pdks/gf180mcuD' if 'RFTX_IMAGE' in os.environ else '/pdk/gf180mcuD'
_SH = 'export PATH=$PATH:/foss/tools/bin PDK_ROOT=/foss/pdks; ' if 'RFTX_IMAGE' in os.environ else ''
GRID = 0.005


def snap(v):
    return round(round(v / GRID) * GRID, 4)


def docker_magic(work, script, timeout=1800):
    work = Path(work).resolve()
    cmd = ['docker', 'run', '--rm', '--network', 'none', '--cpus', '3', '--memory', '6g',
           '--entrypoint', '/bin/sh', '-v', f'{work}:/work', '-w', '/work', DIGITAL_IMAGE,
           '-c', _SH + f'magic -dnull -noconsole -rcfile {PDK}/libs.tech/magic/gf180mcuD.magicrc /work/{script}']
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    (Path(work) / (script + '.log')).write_text(r.stdout + r.stderr)
    r.check_returncode()
    return r


def docker_netgen(work, layout_spice, layout_cell, source_spice, source_cell, report, timeout=1800):
    work = Path(work).resolve()
    cmd = ['docker', 'run', '--rm', '--network', 'none', '--cpus', '3', '--memory', '6g',
           '--entrypoint', '/bin/sh', '-v', f'{work}:/work', '-w', '/work', DIGITAL_IMAGE,
           '-c', _SH + f'netgen -batch lvs "{layout_spice} {layout_cell}" "{source_spice} {source_cell}" '
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
          lane_width=None, gap=1.2, lane_order=None, trunk_order=None, inline_trunks=False, supply=None):
    """Generate layout for ``circuit`` in ``work`` (must be empty). Returns report dict.

    supply (inline mode only; rfdriver power rework 2026-11-28): {'nets': {net: dict(straps=[x fractions], w=strap width,
    bar=(layer, width), pin=(layer, x0, x1))}, 'gap': um}. Each supply net gets vertical Metal5 straps at the given fractions
    of the row width (instead of one trunk), a Via4 onto every row lane it crosses, and a full-width bar along the bottom
    edge: the first listed net's bar is the bottom-most (Metal5, edge-flush), the next sits above it (Metal4); a net on a
    Metal4 bar gets an edge pin of Metal4 down through the band below it. Ports of supply nets are labelled on their pins."""
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
    SUP = (supply or {}).get('nets', {})
    trunked = [n for n in nets if (n in ports or len(row_of[n]) > 1) and n not in SUP]
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
    strap_x = {}
    if SUP:
        assert inline_trunks, 'supply straps need inline_trunks'
        x_lo = bank_right; x_hi = max(cx for _, cx in xposs)
        for net, o in SUP.items():
            strap_x[net] = [snap(x_lo + f * (x_hi - x_lo)) for f in o['straps']]
    if inline_trunks:
        tx = {}
        placed_tr = [(x, SUP[n]['w'], 0, len(rows) - 1) for n, xs in strap_x.items() for x in xs]   # (x, w, rmin, rmax)
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
                xs = esc_xs(ri, net) + ([tx[net]] if net in tx else []) + strap_x.get(net, [])
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
    bars = {}
    if SUP:
        g = supply.get('gap', 1.0)
        if supply.get('stack', False):
            # stacked mode: every bar starts at the bottom edge (different layers); the Metal4 bar is the tallest so a
            # Metal5 strap of its net can land on it above the Metal5 bars of the other nets
            hb = max(o['bar'][1] for o in SUP.values()); yb = cursor_y - g - hb
            for net, o in SUP.items():
                bars[net] = (o['bar'][0], yb, yb + o['bar'][1])
            cursor_y = yb
        else:
            yb = cursor_y - g
            for net in reversed(list(SUP)):           # last listed net sits highest
                layer, bw = SUP[net]['bar']
                bars[net] = (layer, yb - bw, yb); yb -= bw + g
            cursor_y = yb + g
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
            if net in strap_x:
                sx = strap_x[net]
                P.hwire('metal4', min(xs + sx), max(xs + sx), ly, lw[net])
                for x_ in sx:
                    P.via(x_, ly, 4, 5, w=SUP[net]['w'], h=lw[net])
            elif net in tx:
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
    x_l = min(R['xpos'][n] + local[n]['bbox'][0] for R in rowinfo for n in R['names'])
    pin_rect = {}
    for net, o in SUP.items():
        P.net = net
        layer, b0, b1 = bars[net]
        P.rect(layer, x_l, b0, width - 1.0, b1)
        ys = [y for (ri, n), y in lanes.items() if n == net]
        m5top = max([bb[2] for nn, bb in bars.items() if nn != net and bb[0] == 'metal5'] + [b0])
        for x_ in strap_x[net]:
            # straps as plain rectangles (vwire adds w/2 end caps, which reached the other net's bar)
            top_ = max(ys) + lw[net] / 2
            if layer == 'metal5':
                P.rect('metal5', x_ - o['w'] / 2, b0, x_ + o['w'] / 2, top_)
            else:
                lo_ = m5top + 1.0 if supply.get('stack', False) else b0
                P.rect('metal5', x_ - o['w'] / 2, lo_, x_ + o['w'] / 2, top_)
                P.via(x_, (lo_ + b1) / 2, 4, 5, w=o['w'], h=b1 - lo_)
        pl, p0, p1 = o['pin']
        if pl != layer:
            raise ValueError('pin layer must be the bar layer')
        if layer == 'metal4' and not supply.get('stack', False):
            P.rect('metal4', x_l + p0, height_bottom, x_l + p1, b1)      # edge pin down through the bands below
        pin_rect[net] = (x_l + p0, height_bottom, x_l + p1, height_bottom + 3.0)
    P.net = None
    # antenna diodes (KLayout ANT.16): gate-only partial nets with long M2-M5 get an N+/Psub diode
    # (with its own substrate tap) under their own M3-M5 wire; returned as 'antenna_diodes'.
    req = ad.requests_from_shapes(P.shapes, terminals)
    # gate-only PORTS get a diode regardless of the block-local estimate: at chip top they sit on long routed nets
    # (pt_rf precheck ASM-10: txmix 3 + 3 ANT.16).  Routed pt_rf: c_txmix_i_en 1.31 mm Metal3 on 3.92 um^2 of gate,
    # ratio ~360 without a diode; PORT_DIODE keeps metal/(gate + 2 diode) < 200 (MARGIN) at twice that route.
    kinds = {}
    for t in terminals:
        kinds.setdefault(t[2], set()).add(t[3])
    have = {r['net'] for r in req}
    for port in ports:
        if port in PORT_DIODE_SKIP or port.lower().startswith(ANALOG_PREFIX) or kinds.get(port, set()) != {'g'}:
            continue
        if port in have:
            for r_ in req:
                if r_['net'] == port:
                    r_['area'] = max(r_['area'], PORT_DIODE)
            continue
        segs = [('metal5', (s[1] + s[3]) / 2, s[2], (s[1] + s[3]) / 2, s[4]) for s in P.shapes
                if s[0] == 'metal5' and s[5] == port and s[4] - s[2] >= s[3] - s[1]]
        segs += [('metal4', s[1], (s[2] + s[4]) / 2, s[3], (s[2] + s[4]) / 2) for s in P.shapes
                 if s[0] == 'metal4' and s[5] == port and s[3] - s[1] > s[4] - s[2]]
        if segs:
            req.append(dict(net=port, level=5, area=PORT_DIODE, segs=segs))
    dcmds, diodes = ad.plan(req, [s[:5] for s in P.shapes], keepouts)
    P.cmds += dcmds
    cmds += P.cmds
    for i, port in enumerate(ports, 1):
        if port in pin_rect:
            a0, a1, a2, a3 = pin_rect[port]; xm = (a0 + a2) / 2
            cmds += [f'box values {snap(xm - 0.2)} {snap(a1)} {snap(xm + 0.2)} {snap(a1 + 0.6)}',
                     f"label {port} FreeSans 0.3 0 0 0 c {SUP[port]['pin'][0]}", f'port make {i}']
            continue
        x = tx[port]
        cmds += [f'box values {snap(x - 0.2)} {snap(top_edge - 0.6)} {snap(x + 0.2)} {snap(top_edge)}',
                 f'label {port} FreeSans 0.3 0 0 0 c metal5', f'port make {i}']
    for net in nets:
        if net in ports or net in SUP:
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
                trunk_x_um=tx, trunked_nets=len(tx), supply_straps_um=strap_x, supply_bars_um=bars, supply_pins_um=pin_rect, primitives={cells[k]: list(k) for k in keys},
                antenna_diodes=diodes)
