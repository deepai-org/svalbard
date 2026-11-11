"""Correct-by-construction row/channel layout generator for the timing family.

Each schematic device becomes one Magic PCell instance (guard-ringed, so every
device carries its own body tie).  Devices sit in rows.  Every terminal leaves
its device on a private Metal2 jog to a private Metal3 escape column inside the
device's slot, rises on Metal3 into the routing channel directly above its row
and lands on its net's private Metal4 track in that channel.  Nets that appear
in more than one channel, and all ports, also get a private vertical Metal5
trunk in a trunk bank at the left edge.  Because columns are private per
terminal, tracks private per net per channel and trunks private per net, the
routing cannot short by construction; Magic DRC and Netgen LVS still check it.

Metal usage: M1 inside PCells and pin landing pads only, M2 jogs only inside
the device slot, M3 vertical escapes only, M4 horizontal tracks only inside
channels, M5 vertical trunks only inside the trunk bank.

Coordinates are microns.  The generator emits one Magic Tcl script; the flat
cell is saved as .mag and .gds.
"""
from dataclasses import dataclass
from pathlib import Path
import json
import math
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import antenna_diodes as ad  # noqa: E402

DIGITAL_IMAGE = 'svalbard/librelane-gf180-canary:2026.08'
PDK = '/pdk/gf180mcuD'
GRID = 0.005

PITCH_COL = 0.8      # M3 escape column pitch
COL_INNER = 0.5      # inner escape column distance from the device bbox
SLOT_GAP = 0.9       # minimum spacing between escape-column regions of neighbours
TRACK_SIG_W = 0.4
TRACK_PWR_W = 1.0
TRACK_SPACE = 0.32
TRUNK_PITCH = 1.2
STRAP_W = 2.0
STRAP_PITCH = 40.0
TRUNK_SIG_W = 0.44
TRUNK_PWR_W = 3.0
TRUNK_SPACE = 0.6
POWER_NETS = ('VDD', 'VSS')


ANTENNA_IGNORE_SD = {'pt_pll_ring'}   # cells whose antenna planning ignores driver diffusion (see generate())


def snap(v):
    return round(round(v / GRID) * GRID, 4)


def docker_magic(work, script, image=DIGITAL_IMAGE, timeout=3600):
    cmd = ['docker', 'run', '--rm', '--network', 'none', '--cpus', '3', '--memory', '8g',
           '--entrypoint', '/bin/sh', '--mount', f'type=bind,src={work},dst=/work', '-w', '/work', image,
           '-c', f'magic -dnull -noconsole -rcfile {PDK}/libs.tech/magic/gf180mcuD.magicrc /work/{script}']
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    (Path(work) / (script + '.log')).write_text(r.stdout + r.stderr)
    return r


def rects(path):
    layer = None
    out = {}
    for line in Path(path).read_text().splitlines():
        if line.startswith('<< '):
            layer = line[3:-3]
        elif line.startswith('rect ') and layer not in ('checkpaint', 'properties'):
            out.setdefault(layer, []).append([float(v) * GRID for v in line.split()[1:5]])
    return out


def primitive_name(key):
    model, w, l = key
    return f'p_{model}_w{w:g}_l{l:g}'.replace('.', 'p')


@dataclass
class Prim:
    key: tuple
    name: str
    bbox: tuple       # xmin ymin xmax ymax
    pins: dict        # terminal -> (x, y)
    left: list        # terminals escaping left, innermost first
    right: list       # terminals escaping right, innermost first


def analyse_primitive(path, key):
    r = rects(path)
    every = [rc for layer, v in r.items() for rc in v]
    bbox = (min(a[0] for a in every), min(a[1] for a in every), max(a[2] for a in every), max(a[3] for a in every))
    top_m1 = max(r['metal1'], key=lambda a: a[3])
    body = (snap((top_m1[0] + top_m1[2]) / 2 + 0.2), snap((top_m1[1] + top_m1[3]) / 2))
    centre = lambda a: (snap((a[0] + a[2]) / 2), snap((a[1] + a[3]) / 2))
    model = key[0]
    if model.startswith('ppolyf'):
        pc = sorted(r['polycontact'], key=lambda a: a[1])
        pins = {'n': centre(pc[0]), 'p': centre(pc[-1]), 'b': body}
        return Prim(key, primitive_name(key), bbox, pins, ['n', 'p'], ['b'])
    diffc = next(k for k in ('ndiffc', 'pdiffc', 'mvndiffc', 'mvpdiffc') if k in r)
    sd = sorted(r[diffc], key=lambda a: a[0])
    gate = min(r['polycontact'], key=lambda a: a[1])
    pins = {'s': centre(sd[0]), 'd': centre(sd[-1]), 'g': centre(gate), 'b': body}
    return Prim(key, primitive_name(key), bbox, pins, ['g', 's'], ['d', 'b'])


FAST = Path(__file__).resolve().parent / 'generated' / 'fast'


def macro_prim(work, key):
    import shutil as _sh
    name = key[0]
    meta = json.loads((FAST / f'{name}.pins.json').read_text())
    _sh.copy(FAST / f'{name}.mag', Path(work) / f'{name}.mag')
    pins = {n: tuple(v) for n, v in meta['pins'].items()}
    pins.update({n: tuple(v) for n, v in meta['rails'].items()})
    right = sorted(meta['pins'], key=lambda n: meta['pins'][n][0])
    left = sorted(meta['rails'], key=lambda n: meta['rails'][n][1])
    return Prim(key, name, tuple(meta['bbox']), pins, left, right)


# ---- capacitor primitives (2026-11-11, LO owner): PDK Magic pcells wrapped so that both terminals
# land on Metal1 pads like the transistor primitives.
#   cap_mim_2f0_m4m5_noshield -> gf180mcu::cap_mim_2p0fF (MIM between Metal4 and the MIM top plate,
#     contacted by Metal5).  Wrapper: top plate taken up on a Metal5 tongue past the Metal4 ring (>= 1.2 um
#     from the cap, MIM rule), then via4..via1 to an M1 pad (pin 't'); the bottom Metal4 ring is extended
#     downward and taken through via3..via1 to an M1 pad (pin 'b').  The engine keeps its Metal5 straps and
#     trunk columns off the MIM x-range (see generate), because the top plate is Metal5.
#   cap_nmos_03v3_b -> gf180mcu::nvaractor_3p3 nf 1 (the multi-finger generator in this PDK build gives
#     M1.2a errors and unconnected gate fingers, checked 2026-11-11): gate pin 'g' at the top poly contact;
#     both n+ well-contact strips strapped together on Metal2 (two-sided well contact, pin 'w').  The PCell's
#     P+ guard ring is a substrate tap (no pin; it is the substrate node).
CAP_PCELL = {'cap_mim_2f0_m4m5_noshield': 'cap_mim_2p0fF', 'cap_nmos_03v3_b': 'nvaractor_3p3'}


def _cap_wrapper(work, key):
    """Return (tcl commands drawing the wrapper around <name>_c, Prim) from the core PCell geometry."""
    model = key[0]
    name = primitive_name(key)
    r = rects(Path(work) / f'{name}_c.mag')
    bb = lambda rs: (min(a[0] for a in rs), min(a[1] for a in rs), max(a[2] for a in rs), max(a[3] for a in rs))
    cmds = [f'load {name}', 'units internal', f'getcell {name}_c child 0 0 parent 0 0', 'units microns', 'snap internal']
    L = Layout()
    if model == 'cap_mim_2f0_m4m5_noshield':
        ring = bb(r['metal4'])
        cap = bb(r['mimcap'] + r.get('mimcapcontact', []))
        cc = bb(r['mimcapcontact'])
        cx = snap((cc[0] + cc[2]) / 2)
        # Magic MIMTM.2 (via4 surround 0.4) flags the PCell's own bottom-plate via4 strip (0.31 / 0.335 um
        # surround, also on the bare PCell; the KLayout deck passes it): widen the ring around the strip.
        v4 = bb(r['via4'])
        L.rect('metal4', v4[0] - 0.4, v4[1] - 0.4, v4[2] + 0.4, v4[3] + 0.4)
        ring = (ring[0], min(ring[1], v4[1] - 0.4), max(ring[2], v4[2] + 0.4), max(ring[3], v4[3] + 0.4))
        yt = snap(max(ring[3] + 1.25, cap[3] + 1.25) + 0.45)   # MIMTM.1: island >= 1.2 um from the bottom plate
        yb = snap(ring[1] - 0.65)
        L.rect('metal5', cx - 1.0, cc[3] - 1.0, cx + 1.0, yt + 0.45)
        L.rect('metal4', cx - 0.45, yt - 0.45, cx + 0.45, yt + 0.45)
        L.via(cx, yt, 4, 5)
        L.via(cx, yt, 1, 4)
        L.rect('metal4', cx - 0.5, yb - 0.45, cx + 0.5, ring[1] + 0.2)
        L.via(cx, yb, 1, 4)
        pins = {'t': (cx, yt), 'b': (cx, yb)}
        box = (ring[0], yb - 0.5, ring[2], yt + 0.5)
        left, right = ['t'], ['b']
    else:
        pc = sorted(r['polycontact'], key=lambda a: a[1])[-1]
        sd = sorted(r['nsubdiffcont'], key=lambda a: a[0])
        y0 = snap((sd[0][1] + sd[0][3]) / 2)
        xs = [snap((a[0] + a[2]) / 2) for a in (sd[0], sd[-1])]
        for x in xs:
            L.via(x, y0, 1, 2)
        L.rect('metal2', xs[0] - 0.2, y0 - 0.3, xs[1] + 0.2, y0 + 0.3)
        every = [a for k, v in r.items() for a in v]
        box = bb(every)
        pins = {'g': (snap((pc[0] + pc[2]) / 2), snap((pc[1] + pc[3]) / 2)), 'w': (xs[1], y0)}
        left, right = ['g'], ['w']
    cmds += L.cmds + [f'save {name}']
    return cmds, Prim(key, name, box, pins, left, right)


def build_primitives(work, keys, image=DIGITAL_IMAGE):
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    macro_keys = [k for k in keys if (FAST / f'{k[0]}.pins.json').exists()]
    keys = [k for k in keys if k not in macro_keys]
    cap_keys = [k for k in keys if k[0] in CAP_PCELL]
    keys = [k for k in keys if k not in cap_keys]
    cmds = ['crashbackups stop', 'load primitive_workspace']
    for key in keys:
        model, w, l = key
        name = primitive_name(key)
        if model.startswith('ppolyf'):
            cmds += ['units internal',
                     f'set cell [magic::gencell_makecell gf180mcu::{model} w {w} l {l} guard 1 full_metal 1]']
        else:
            cmds += ['units internal',
                     f'set cell [magic::gencell_makecell gf180mcu::{model} w {w} l {l} nf 1 guard 1 topc 0 botc 1 full_metal 1 gate_to_polycont 0.6 gate_extension 0.8 diff_gate_space 0.3]']
        cmds += ['load $cell', f'save {name}', 'load primitive_workspace']
    for key in cap_keys:
        model, w, l = key
        extra = ' nf 1 guard 1 full_metal 1' if model == 'cap_nmos_03v3_b' else ''
        cmds += ['units internal', f'set cell [magic::gencell_makecell gf180mcu::{CAP_PCELL[model]} w {w} l {l}{extra}]',
                 'load $cell', f'save {primitive_name(key)}_c', 'load primitive_workspace']
    cmds.append('quit -noprompt')
    (work / 'primitives.tcl').write_text('\n'.join(cmds) + '\n')
    r = docker_magic(work, 'primitives.tcl', image)
    prims = {}
    if cap_keys:
        cmds = ['crashbackups stop']
        for key in cap_keys:
            if not (work / f'{primitive_name(key)}_c.mag').exists():
                raise RuntimeError(f'PCell generation failed for {key}; see primitives.tcl.log')
            c, prims[key] = _cap_wrapper(work, key)
            cmds += c
        cmds.append('quit -noprompt')
        (work / 'capwrap.tcl').write_text('\n'.join(cmds) + '\n')
        docker_magic(work, 'capwrap.tcl', image)
    for key in keys:
        p = work / (primitive_name(key) + '.mag')
        if not p.exists():
            raise RuntimeError(f'PCell generation failed for {key}; see primitives.tcl.log')
        prims[key] = analyse_primitive(p, key)
    for key in macro_keys:
        prims[key] = macro_prim(work, key)
    return prims


def pin_order(model):
    if (FAST / f'{model}.pins.json').exists():
        return tuple(json.loads((FAST / f'{model}.pins.json').read_text())['ports'])
    if model.startswith('ppolyf'):
        return ('p', 'n', 'b')
    if model == 'cap_mim_2f0_m4m5_noshield':
        return ('t', 'b')
    if model == 'cap_nmos_03v3_b':
        return ('g', 'w')
    return ('d', 'g', 's', 'b')


class Layout:
    def __init__(self):
        self.cmds = []
        self.net = None       # net of the shapes being drawn (antenna-diode planning)
        self.shapes = []      # (layer, x1, y1, x2, y2, net)

    def rect(self, layer, x1, y1, x2, y2):
        x1, x2 = sorted((snap(x1), snap(x2)))
        y1, y2 = sorted((snap(y1), snap(y2)))
        self.cmds += [f'box values {x1} {y1} {x2} {y2}', f'paint {layer}']
        self.shapes.append((layer, x1, y1, x2, y2, self.net))

    def via(self, x, y, low, high):
        for m in range(low, high + 1):
            h = 0.19 if m == 1 else 0.22 if m == 5 else 0.2
            self.rect(f'metal{m}', x - h, y - h, x + h, y + h)
        for m in range(low, high):
            h = 0.13 if m == 1 else 0.14
            self.rect(f'via{m}', x - h, y - h, x + h, y + h)

    def hwire(self, layer, x1, x2, y, width):
        h = width / 2
        e = max(h, 0.2)  # cover the 0.4 um via landing pads at the ends (no notches)
        self.rect(layer, min(x1, x2) - e, y - h, max(x1, x2) + e, y + h)

    def vwire(self, layer, x, y1, y2, width):
        h = width / 2
        self.rect(layer, x - h, min(y1, y2) - h, x + h, max(y1, y2) + h)


def generate(work, cell, ports, devices, rows=None, max_row_width=160.0, image=DIGITAL_IMAGE,
             extra_trunk_nets=(), power_nets=POWER_NETS, trunk_groups=(), net_space=None, net_width=None,
             over_cell=False):
    """Place and route `devices`; returns a report dict.  `rows` is an optional
    list of lists of device names; otherwise devices are packed in netlist order.
    `trunk_groups` (optional, default none = unchanged behaviour): lists of signal trunk nets placed in
    consecutive M5 trunk columns, in the given order, before all other trunks (e.g. a sensitive pair
    flanked by static nets, so no switching trunk can land beside it).
    `net_space` (optional, default none = unchanged behaviour): {net: extra_um}; the net's channel track gets
    extra_um of additional clearance on both sides, and its M5 trunk keeps the neighbouring trunk column on
    each side free over its span (for low-swing / high-impedance nets that must not couple to their
    complement or to full-swing neighbours).
    `net_width` (optional, default none = unchanged behaviour): {net: um}; wide Metal4 channel tracks and Metal5
    trunk for high-current / low-R nets (e.g. LC tank nodes).  The trunk keeps both neighbouring trunk
    columns free (as net_space) and clears the power straps; track/trunk crossings get a via array.
    Width <= 3.0 um (neighbour columns blocked: two wide trunks sit >= 3.6 um apart).
    `over_cell` (optional, default False = unchanged behaviour): a row's Metal4 tracks start over the row's
    own devices instead of above them (for macros that use only Metal1/2), so the channel is only what the
    track count exceeds the row height by."""
    net_space = net_space or {}
    net_width = net_width or {}
    if any(w > 3.0 for w in net_width.values()):
        raise ValueError('net_width > 3.0 um is not supported by the trunk column pitch')
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    for old in work.glob('*.mag'):
        old.unlink()
    keys = sorted({d.key for d in devices})
    prims = build_primitives(work, keys, image)
    by_name = {d.name: d for d in devices}

    # --- slot geometry
    def slot(dev):
        p = prims[dev.key]
        x0, _, x1, _ = p.bbox
        left = x0 - COL_INNER - PITCH_COL * (len(p.left) - 1) - SLOT_GAP / 2
        right = x1 + COL_INNER + PITCH_COL * (len(p.right) - 1) + SLOT_GAP / 2
        return left, right

    if rows is None:
        rows, cur, width = [], [], 0.0
        for d in devices:
            l, r = slot(d)
            if cur and width + (r - l) > max_row_width:
                rows.append(cur)
                cur, width = [], 0.0
            cur.append(d.name)
            width += r - l
        if cur:
            rows.append(cur)
    # optional horizontal gaps inside a row: an entry 'GAP:<um>' advances the cursor (used to centre
    # a group of devices over / under the group it serves); no effect on rows without such entries
    gaps = {}
    clean = []
    for ri, row in enumerate(rows):
        r_ = []
        for n in row:
            if isinstance(n, str) and n.startswith('GAP:'):
                gaps[(ri, len(r_))] = gaps.get((ri, len(r_)), 0.0) + float(n[4:])
            else:
                r_.append(n)
        clean.append(r_)
    rows = clean
    placed = [n for row in rows for n in row]
    if sorted(placed) != sorted(by_name):
        missing = set(by_name) - set(placed)
        extra = set(placed) - set(by_name)
        raise ValueError(f'row assignment mismatch: missing {sorted(missing)[:5]} extra {sorted(extra)[:5]}')

    # --- nets per row and trunk set
    row_nets = []
    for row in rows:
        nets = []
        for n in row:
            for t in by_name[n].nodes:
                if t not in nets:
                    nets.append(t)
        row_nets.append(nets)
    count = {}
    for nets in row_nets:
        for n in nets:
            count[n] = count.get(n, 0) + 1
    trunk_nets = [n for n in power_nets if n in count]
    trunk_nets += sorted({n for n, c in count.items() if (c > 1 or n in ports or n in extra_trunk_nets)} - set(trunk_nets))
    for p in ports:
        if p not in count:
            raise ValueError(f'port {p} has no devices')
    origin_x = 2.0

    L = Layout()
    terminals = []    # (x, y, net, 'g'|'sd'|'x', gate area) at each pin landing, for antenna planning
    pin_info = {d.model: ad.macro_pin_info(FAST / f'{d.model}.spice', d.model)
                for d in devices if (FAST / f'{d.model}.pins.json').exists()}
    placements = {}
    y_row = 2.0
    tracks = {}       # (row, net) -> y
    pin_routes = []   # (row, net, col_x, pin_y)
    row_extents = []
    for ri, row in enumerate(rows):
        # place devices with bbox bottom at y_row
        x_cursor = origin_x
        heights = []
        for k_, n in enumerate(row):
            x_cursor += gaps.get((ri, k_), 0.0)
            d = by_name[n]
            p = prims[d.key]
            l, r = slot(d)
            cx = snap(x_cursor - l)
            cy = snap(y_row - p.bbox[1])
            placements[n] = (cx, cy)
            x_cursor += r - l
            heights.append(cy + p.bbox[3])
        row_top = max(heights)
        row_right = x_cursor
        # channel tracks
        y = (y_row + 0.9) if over_cell else (row_top + 0.9)
        nets = row_nets[ri]
        order = [n for n in power_nets if n in nets] + [n for n in nets if n not in power_nets]
        prev_extra = 0.0
        for n in order:
            w = TRACK_PWR_W if n in power_nets else net_width.get(n, TRACK_SIG_W)
            ex = net_space.get(n, 0.0)
            y += max(0.0, ex - prev_extra) if prev_extra else ex
            y += w / 2
            tracks[(ri, n)] = snap(y)
            y += w / 2 + TRACK_SPACE + ex
            prev_extra = ex
        channel_top = max(y + 0.5, row_top + 1.0) if over_cell else y + 0.5
        row_extents.append(dict(row=ri, y_bottom=y_row, row_top=row_top, channel_top=channel_top, right=row_right,
                                devices=len(row), tracks=len(order)))
        # device instances and pin escapes
        for n in row:
            d = by_name[n]
            p = prims[d.key]
            cx, cy = placements[n]
            L.cmds += [f'getcell {p.name} child 0 0 parent {cx} {cy}', f'identify X{n}']
            terms = dict(zip(pin_order(d.model), d.nodes))
            for side, names in (('L', p.left), ('R', p.right)):
                for k, t in enumerate(names):
                    px, py = p.pins[t]
                    px, py = cx + px, cy + py
                    if side == 'L':
                        col = cx + p.bbox[0] - COL_INNER - PITCH_COL * k
                    else:
                        col = cx + p.bbox[2] + COL_INNER + PITCH_COL * k
                    col = snap(col)
                    L.net = terms[t]
                    if d.model in pin_info:
                        pr, ga = pin_info[d.model].get(t, (True, 0.))
                        kind = 'sd' if pr else 'g'
                    elif d.model.startswith(('nfet', 'pfet')):
                        kind, ga = ('g', d.w * d.l) if t == 'g' else ('sd', 0.) if t in ('d', 's') else ('x', 0.)
                    else:
                        kind, ga = 'x', 0.
                    terminals.append((px, py, terms[t], kind, ga))
                    L.via(px, py, 1, 2)
                    L.hwire('metal2', px, col, py, 0.4)
                    L.via(col, py, 2, 3)
                    pin_routes.append((ri, terms[t], col, py))
        y_row = channel_top + 1.0
    top = y_row
    width = max(e['right'] for e in row_extents) + 1.0
    # --- Metal5 keepout over MIM capacitors (their top plate is Metal5): no strap or trunk column in
    #     their x-range.  Empty unless the cell has MIM caps (no change for other cells).
    m5_keep = []
    for n, (cx, cy) in placements.items():
        if by_name[n].model == 'cap_mim_2f0_m4m5_noshield':
            b = prims[by_name[n].key].bbox
            m5_keep.append((cx + b[0] - 1.0, cx + b[2] + 1.0))
    m5_ok = lambda x, half: all(x + half < a or x - half > b for a, b in m5_keep)
    # --- power straps (M5, full height), alternating VSS/VDD
    straps = []
    x = origin_x + 3.0
    while x < width - 2.0:
        for k, n in enumerate(power_nets):
            if n in count and m5_ok(x + 3.0 * k, STRAP_W / 2 + 0.5):
                straps.append((n, snap(x + 3.0 * k)))
        x += STRAP_PITCH
    for n in power_nets:   # MIM keepout removed every strap of a net: add one beside the array
        if n in count and not any(sn == n for sn, _ in straps):
            straps.append((n, snap(width + 1.5 + 3.0 * power_nets.index(n))))
    if m5_keep:
        width = max([width] + [sx + STRAP_W for _, sx in straps])
    # --- signal trunks: M5 columns over the array, interval-packed
    pins_x = {}
    for ri, net, col, py in pin_routes:
        pins_x.setdefault(net, []).append(col)
    sig_trunks = [n for n in trunk_nets if n not in power_nets]
    want = {}
    for n in sig_trunks:
        ys = [tracks[(ri, n)] for ri in range(len(rows)) if (ri, n) in tracks]
        lo, hi = min(ys), max(ys)
        if n in ports:
            hi = top - 0.5
        want[n] = (lo, hi)
    columns = []
    x = origin_x + 1.0
    while x < width - 1.0:
        if all(abs(x - sx) > STRAP_W / 2 + 0.9 for _, sx in straps) and m5_ok(x, TRUNK_SIG_W / 2 + 0.5):
            columns.append(snap(x))
        x += TRUNK_PITCH
    occupied = {c: [] for c in columns}
    trunk_x = {}
    for grp in trunk_groups:
        if any(n is None or n in net_width for n in grp):
            _wide_group(grp, want, net_width, pins_x, columns, occupied, trunk_x, straps)
            continue
        grp = [n for n in grp if n in want]
        if not grp:
            continue
        xs = sorted(x for n in grp for x in pins_x[n])
        pref = xs[len(xs) // 2]
        best = None
        for i0 in sorted(range(len(columns) - len(grp) + 1), key=lambda i: abs(columns[i + len(grp) // 2] - pref)):
            cols = columns[i0:i0 + len(grp)]
            if all(all(want[n][1] + 1.2 < a or want[n][0] - 1.2 > b for a, b in occupied[c]) for n, c in zip(grp, cols)):
                best = cols
                break
        if best is None:
            raise RuntimeError(f'no free trunk columns for group {grp}')
        for n, c in zip(grp, best):
            occupied[c].append(want[n])
            trunk_x[n] = c
    for n in sorted((n for n in sig_trunks if n not in trunk_x), key=lambda n: -(want[n][1] - want[n][0])):
        lo, hi = want[n]
        if n in net_width:          # wide trunk: its end caps reach net_width/2 past the span
            lo, hi = lo - net_width[n], hi + net_width[n]
        xs = sorted(pins_x[n])
        pref = xs[len(xs) // 2]
        best = None
        free = lambda c: all(hi + 1.2 < a or lo - 1.2 > b for a, b in occupied[c])
        for ci, c in sorted(enumerate(columns), key=lambda ic: abs(ic[1] - pref)):
            if not free(c):
                continue
            if n in net_width and not all(abs(c - sx) > STRAP_W / 2 + net_width[n] / 2 + 0.6 for _, sx in straps):
                continue
            if n in net_space or n in net_width:
                nb = [columns[j] for j in (ci - 1, ci + 1)
                      if 0 <= j < len(columns) and abs(columns[j] - c) < TRUNK_PITCH * 1.5]
                if len(nb) < 2 or not all(free(x) for x in nb):
                    continue
                for x in nb:
                    occupied[x].append((lo, hi))
            best = c
            break
        if best is None:
            raise RuntimeError(f'no free trunk column for {n}')
        occupied[best].append((lo, hi))
        trunk_x[n] = best
    # --- M3 verticals, M4 tracks
    span = {}
    for ri, net, col, py in pin_routes:
        ty = tracks[(ri, net)]
        L.net = net
        L.vwire('metal3', col, py, ty, 0.4)
        L.via(col, ty, 3, 4)
        lo, hi = span.get((ri, net), (col, col))
        span[(ri, net)] = (min(lo, col), max(hi, col))
    for (ri, net), (lo, hi) in span.items():
        ty = tracks[(ri, net)]
        L.net = net
        if net in power_nets:
            L.hwire('metal4', origin_x, width - 1.0, ty, TRACK_PWR_W)
            for n, sx in straps:
                if n == net:
                    L.via(sx, ty, 4, 5)
            continue
        if net in trunk_x:
            lo, hi = min(lo, trunk_x[net]), max(hi, trunk_x[net])
            if net in net_width:   # via4 array over the wide crossing
                span_ = net_width[net] - 0.44           # via-array pads (0.44 um) stay inside the wire
                k = max(1, int(span_ / 0.8) + 1)
                off = [(i - (k - 1) / 2) * (span_ / (k - 1) if k > 1 else 0) for i in range(k)]
                for dx in off:
                    for dy in off:
                        L.via(trunk_x[net] + dx, ty + dy, 4, 5)
            else:
                L.via(trunk_x[net], ty, 4, 5)
        L.hwire('metal4', lo, hi, ty, net_width.get(net, TRACK_SIG_W))
    for n, sx in straps:
        L.net = n
        L.vwire('metal5', sx, 1.0, top - 0.5, STRAP_W)
    for n, xx in trunk_x.items():
        lo, hi = want[n]
        L.net = n
        L.vwire('metal5', xx, lo, hi, net_width.get(n, TRUNK_SIG_W))
    L.net = None
    # --- antenna diodes (KLayout ANT.16): gate-only nets with long M3-M5 get an N+/Psub diode
    #     under their own M4/M5 wire.  Placed diodes are added to the LVS reference by the caller
    #     via report['antenna_diodes'] (antenna_diodes.spice_lines).
    keepouts, taps = [], []
    for n, (cx, cy) in placements.items():
        b = prims[by_name[n].key].bbox
        keepouts.append((cx + b[0], cy + b[1], cx + b[2], cy + b[3]))
        if by_name[n].model.startswith('nfet'):   # NMOS PCell guard ring = P-substrate tap (macros: rails only)
            taps.append(keepouts[-1])
    # The deck counts a driver's drain diffusion as a finite diode (ratio = perimeter / (gate + 2*diff)), but the
    # planner treats any 'sd' landing as full protection.  pt_pll_ring r9: NX and N16B (one small inverter drain,
    # 1.32 um^2, driving ~880 um M5 trunks) failed ANT.16_i_ANT.6 at ratio 426-427.  For cells listed in
    # ANTENNA_IGNORE_SD the planner ignores driver diffusion, i.e. every long gate net gets its own diode.
    terms_ad = [(x, y, n, 'x' if (k == 'sd' and cell in ANTENNA_IGNORE_SD) else k, ga) for x, y, n, k, ga in terminals]
    req = ad.requests_from_shapes(L.shapes, terms_ad)
    dcmds, diodes = ad.plan(req, [s[:5] for s in L.shapes], keepouts, taps=taps)
    L.cmds += dcmds
    for i, prt in enumerate(ports, 1):
        if prt in power_nets:
            xx = next(sx for n, sx in straps if n == prt)
        else:
            xx = trunk_x[prt]
        L.cmds += [f'box values {snap(xx - 0.2)} {snap(top - 1.0)} {snap(xx + 0.2)} {snap(top - 0.5)}',
                   f'label {prt} FreeSans 0.3 0 0 0 c metal5', f'port make {i}']
    flat = cell
    # Hierarchical (device PCells as subcells): flattening was observed to drop
    # the ppolyf_u_1k device from extraction in Magic 8.3.623.
    # Two sessions: build+save, then reload for DRC/extraction/GDS.  In Magic
    # 8.3.623 extracting in the drawing session (or after `gds write`) was
    # observed to drop the ppolyf_u_1k device from the extracted netlist.
    script = ['crashbackups stop', f'load {cell}', 'units microns', 'snap internal'] + L.cmds + ['save', 'quit -noprompt']
    (work / 'layout.tcl').write_text('\n'.join(script) + '\n')
    r0 = docker_magic(work, 'layout.tcl', image)
    # DRC in its own session: `drc style drc(full)` was observed to disable
    # ppolyf_u_1k device extraction for the rest of the Magic session.
    check = ['crashbackups stop', f'load {flat}', 'select top cell',
             'drc euclidean on', 'drc style drc(full)', 'drc check', 'drc catchup',
             'set f [open drc-count.txt w]', 'puts $f [drc list count total]', 'close $f',
             'set f [open drc-details.txt w]', 'puts $f [drc listall why]', 'close $f', 'quit -noprompt']
    (work / 'drc.tcl').write_text('\n'.join(check) + '\n')
    rd = docker_magic(work, 'drc.tcl', image)
    check = ['crashbackups stop', f'load {flat}', 'select top cell', 'extract all',
             'ext2spice lvs', f'ext2spice -o {flat}.lvs.spice',
             'ext2spice default', 'ext2spice cthresh 0', 'ext2spice rthresh 0', f'ext2spice -o {flat}.ext.spice',
             f'gds write {flat}.gds', 'quit -noprompt']
    (work / 'check.tcl').write_text('\n'.join(check) + '\n')
    r = docker_magic(work, 'check.tcl', image)
    drc_text = (work / 'drc-count.txt').read_text().strip() if (work / 'drc-count.txt').exists() else 'missing'
    report = dict(cell=flat, image=image, size_um=[round(width, 2), round(top, 2)],
                  area_um2=round(width * top, 1), rows=row_extents, trunk_nets=trunk_nets,
                  straps=[[n, sx] for n, sx in straps], trunk_x=trunk_x,
                  devices=len(devices), drc_count_raw=drc_text, antenna_diodes=diodes, magic_returncode=[r0.returncode, rd.returncode, r.returncode])
    (work / 'layout-report.json').write_text(json.dumps(report, indent=1) + '\n')
    return report


def _wide_group(grp, want, net_width, pins_x, columns, occupied, trunk_x, straps, stride=4):
    """trunk_groups entry with wide (net_width) nets and/or None spacers: consecutive entries sit
    `stride` trunk pitches apart (4.8 um), every entry's neighbour columns stay free, and the group does
    not straddle a power strap.  Used to pin a differential pair's trunks symmetrically and keep two
    pairs apart (QVCO I/Q tanks)."""
    nets = [n for n in grp if n is not None and n in want]
    if not nets:
        return
    span = lambda n: ((want[n][0] - net_width.get(n, 0), want[n][1] + net_width.get(n, 0)))
    xs = sorted(x for n in nets for x in pins_x[n])
    pref = xs[len(xs) // 2]
    k = len(grp)
    idx = {c: i for i, c in enumerate(columns)}
    cands = []
    for i0 in range(len(columns)):
        cols = [columns[i0] + j * stride * TRUNK_PITCH for j in range(k)]
        cols = [snap(c) for c in cols]
        if not all(any(abs(c - x) < 1e-3 for x in columns) for c in cols):
            continue
        cands.append(cols)
    cands.sort(key=lambda cols: abs((cols[0] + cols[-1]) / 2 - pref))
    for cols in cands:
        ok = True
        for n, c in zip(grp, cols):
            if n is None or n not in want:
                continue
            lo, hi = span(n)
            near = [x for x in columns if abs(x - c) < TRUNK_PITCH * 1.5]
            hw = net_width.get(n, TRUNK_SIG_W) / 2
            if not all(abs(c - sx) > STRAP_W / 2 + hw + 0.6 for _, sx in straps):
                ok = False
            for x in near:
                if not all(hi + 1.2 < a or lo - 1.2 > b for a, b in occupied[x]):
                    ok = False
            if len(near) < 3:
                ok = False
        if ok:
            for n, c in zip(grp, cols):
                if n is None or n not in want:
                    continue
                for x in [x for x in columns if abs(x - c) < TRUNK_PITCH * 1.5]:
                    occupied[x].append(span(n))
                trunk_x[n] = c
            return
    raise RuntimeError(f'no free trunk columns for wide group {grp}')


def drc_errors(raw):
    try:
        return int(raw.split()[-1]) if raw.strip() else 0
    except ValueError:
        return None


def netgen_lvs(work, layout_spice, layout_cell, schematic_spice, schematic_cell, out='lvs.txt', image=DIGITAL_IMAGE):
    cmd = ['docker', 'run', '--rm', '--network', 'none', '--cpus', '3', '--memory', '8g',
           '--entrypoint', 'netgen', '--mount', f'type=bind,src={work},dst=/work', '-w', '/work', image,
           '-batch', 'lvs', f'{layout_spice} {layout_cell}', f'{schematic_spice} {schematic_cell}',
           f'{PDK}/libs.tech/netgen/gf180mcuD_setup.tcl', out]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    (Path(work) / (out + '.log')).write_text(r.stdout + r.stderr)
    text = (Path(work) / out).read_text() if (Path(work) / out).exists() else ''
    final = text[text.rfind('Final result'):] if 'Final result' in text else text[-2000:]
    unique = 'Circuits match uniquely' in final or 'Netlists match uniquely' in final
    return dict(unique_match=unique and 'mismatch' not in final.lower().replace('property errors', ''),
                summary=final.strip()[:600], log=out)
