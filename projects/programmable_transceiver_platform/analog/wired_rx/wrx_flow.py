"""Shared layout / extraction / LVS / simulation flow for the wired-receive family.

The transistor-level `<block>.spice` file is the schematic source of truth.
This module parses it, generates single-finger gf180mcuD PCells in Magic,
places them on a grid and routes every terminal with the analog/pads house
style: a short M2 stub, a per-terminal M3 escape, a unique M4 row and one
vertical M5 trunk per net.  It then runs Magic DRC, extraction (with
parasitic capacitance), Netgen LVS and ngspice.

Images (all runs use --network none and bounded CPU/memory):
  DIGITAL  svalbard/librelane-gf180-canary:2026.08 -> Magic 8.3.623, Netgen 1.5.316, /pdk/gf180mcuD
  ANALOG   hpretl/iic-osic-tools (pinned digest)   -> ngspice-46, /foss/pdks/gf180mcuD
"""
import hashlib
import json
import math
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import antenna_diodes as ad  # noqa: E402
PROJECT = HERE.parents[1]
REPO = PROJECT.parents[1]
SCRATCH = REPO / 'scratch' / 'wired_rx'
GENERATED = HERE / 'generated'

DIGITAL_IMAGE = 'sha256:b60278092f08c0a42fa93ed640d15d84eec53d7799790962781157ec34ceff43'
DIGITAL_TAG = 'svalbard/librelane-gf180-canary:2026.08'
ANALOG_IMAGE = 'sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305'
ANALOG_REF = 'hpretl/iic-osic-tools@sha256:89641950bbf247c522188629992b6271e391e38372ca0f8e3c850480874948a3'
DIGITAL_PDK = '/pdk/gf180mcuD'
ANALOG_PDK = '/foss/pdks/gf180mcuD'
PDK_REVISION = 'ciel gf180mcu f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7 (analog image); canary /pdk/gf180mcuD tech fingerprint 9e0a3f80'
DOCKER_LIMITS = ['--network', 'none', '--cpus', '3', '--memory', '6g', '-e', 'OMP_NUM_THREADS=1']


def docker(image, workdir, command, *, timeout=1800, extra_mounts=()):
    args = ['docker', 'run', '--rm', *DOCKER_LIMITS, '--entrypoint', '/bin/sh',
            '--mount', f'type=bind,src={workdir},dst=/work', '-w', '/work']
    for src, dst in extra_mounts:
        args += ['--mount', f'type=bind,src={src},dst={dst},readonly']
    args += [image, '-c', command]
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


# ---------------------------------------------------------------- netlist
@dataclass
class Device:
    name: str
    model: str
    nodes: tuple
    w: float
    l: float
    nf: int = 1          # fingers of ONE PCell (isolated-well devices only; everything else is single-finger)
    iso: bool = False    # NMOS in its own DNWELL island (body net != VSS), r10 CTLE r4


@dataclass
class Subckt:
    name: str
    ports: list
    devices: list = field(default_factory=list)
    breaks: set = field(default_factory=set)   # device indices that start a new layout row

    @property
    def nets(self):
        return sorted({n for d in self.devices for n in d.nodes} | set(self.ports))


def _um(value):
    value = value.lower().rstrip('m') if value.lower().endswith('um') else value.lower()
    if value.endswith('u'):
        return float(value[:-1])
    if value.endswith('e-6'):
        return float(value[:-3])
    return float(value) * 1e6


def parse_spice(path, top=None):
    text = Path(path).read_text().replace('\n+', ' ')
    subckts = {}
    current = None
    for raw in text.splitlines():
        line = raw.split(';')[0].strip()
        if line.startswith('* ROWBREAK') and current is not None:
            current.breaks.add(len(current.devices))
            continue
        if not line or line.startswith('*'):
            continue
        tok = line.split()
        if tok[0].lower() == '.subckt':
            current = Subckt(tok[1], tok[2:])
            subckts[tok[1]] = current
        elif tok[0].lower() == '.ends':
            current = None
        elif current is not None and tok[0][0] in 'Xx':
            params = dict(t.split('=') for t in tok if '=' in t)
            pos = [t for t in tok[1:] if '=' not in t]
            model, nodes = pos[-1], tuple(pos[:-1])
            mult = int(params.get('m', 1))
            if model.startswith(('nfet', 'pfet')):
                w, l = _um(params['w']), _um(params['l'])
            elif model.startswith('ppolyf'):
                w, l = _um(params['r_width']), _um(params['r_length'])
            else:
                raise ValueError(f'unsupported device model {model} in {path}')
            if model.startswith('nfet') and len(nodes) == 4 and nodes[3] != 'VSS':
                # isolated p-well NMOS (r10): one m-finger PCell in its own DNWELL island
                current.devices.append(Device(tok[0][1:], model, nodes, w, l, nf=mult, iso=True))
                continue
            for i in range(mult):
                name = tok[0][1:] + (f'_m{i}' if mult > 1 else '')
                current.devices.append(Device(name, model, nodes, w, l))
    if top is None:
        top = next(iter(subckts))
    return subckts[top]


# ---------------------------------------------------------------- layout
def _rects(path):
    layer, out = None, {}
    for line in Path(path).read_text().splitlines():
        if line.startswith('<< '):
            layer = line[3:-3]
        if line.startswith('rect '):
            out.setdefault(layer, []).append([float(v) * .005 for v in line.split()[1:]])
    return out


def _terminals(path):
    """Terminal centres (D,G,S,B) or (A,B,sub) from a saved single-finger PCell."""
    r = _rects(path)
    diffusion = next((k for k in ('mvndiffc', 'ndiffc', 'pdiffc', 'mvpdiffc') if k in r), None)
    body = next(k for k in ('mvpsubdiffcont', 'psubdiffcont', 'nsubdiffcont', 'mvnsubdiffcont',
                            'mvnsdiffc', 'nsdiffc', 'nwellc') if k in r)
    ctr = lambda a: ((a[0] + a[2]) / 2, (a[1] + a[3]) / 2)
    # Body: the guard ring's topmost Metal1 bar, tapped near its right end.
    topbar = max(r['metal1'], key=lambda a: (a[3], a[2] - a[0]))
    bpt = (topbar[2] - .3, (topbar[1] + topbar[3]) / 2)
    allx = [v for ly, rr in r.items() if ly != 'checkpaint' for a in rr for v in (a[0], a[2])]
    ally = [v for ly, rr in r.items() if ly != 'checkpaint' for a in rr for v in (a[1], a[3])]
    bbox = (min(allx), min(ally), max(allx), max(ally))
    if diffusion is None:
        pc = r['polycontact']
        return [ctr(max(pc, key=lambda a: a[3])), ctr(min(pc, key=lambda a: a[1])), bpt], bbox
    source = min(r[diffusion], key=lambda a: a[0])
    drain = max(r[diffusion], key=lambda a: a[2])
    gate = min(r['polycontact'], key=lambda a: a[1])
    return [ctr(drain), ctr(gate), ctr(source), bpt], bbox


# ---- isolated p-well (DNWELL) multi-finger NMOS, r10 (CTLE r4 follower).  Ring recipe = analog/rf_tx/layoutlib.py
# (RFT-01, KLayout-clean there): N+ tap ring (DNWELL contact, on the rail) 1.0 um outside the PCell's p-well, DNWELL
# 2.7 um beyond the p-well, P+ substrate guard ring 2.6 um outside the DNWELL.  Fingers: source/drain columns get a
# Metal1+Metal2 stripe over the full finger (via1 array), sources and drains are collected on two Metal3 buses over
# the fingers (via2 arrays) that reach out to the left (source) / right (drain) where ISO_ESC Metal3 escapes per bus
# go down to the row tracks: every escape and every via array stays below the 85 C EM limits at ~3.5 mA.
ISO_GAP, ISO_RING, ISO_DNW, ISO_PG_SPACE, ISO_PG, ISO_HALO = 1.0, 1.0, 2.7, 2.6, 0.8, 0.4
ISO_ESC = 8


def _iso_prim(cell, path, nf, w):
    """Magic commands that turn the saved nf-finger nfet PCell into the island, and its pin table:
    [(dx, dy, role, escape_x, start_level)], role in d/s/g/b/nw/pg; bbox."""
    r = _rects(path)
    g5 = lambda v: round(round(v / .005) * .005, 3)
    pw = r['pwell']
    x0, y0, x1, y1 = (min(a[0] for a in pw), min(a[1] for a in pw), max(a[2] for a in pw), max(a[3] for a in pw))
    cmds = [f'load {cell}', 'units microns', 'snap internal']
    box = lambda a: 'box values ' + ' '.join(f'{g5(v):.3f}' for v in a)

    def ring(a, b):
        return [(x0 - b, y0 - b, x1 + b, y0 - a), (x0 - b, y1 + a, x1 + b, y1 + b),
                (x0 - b, y0 - b, x0 - a, y1 + b), (x1 + a, y0 - b, x1 + b, y1 + b)]
    e = 0.08
    pg_a = ISO_DNW + ISO_PG_SPACE
    for a, b, diff, cont in ((ISO_GAP, ISO_GAP + ISO_RING, 'nsubdiff', 'nsubdiffcont'), (pg_a, pg_a + ISO_PG, 'psubdiff', 'psubdiffcont')):
        for rc in ring(a, b):
            cmds += [box(rc), f'paint {diff}', 'paint metal1']
            if diff == 'nsubdiff':
                # explicit N-well 0.14 um around the tap ring: Magic writes NWELL exactly under an N-tap, which its
                # own DRC flags (DF.4a 0.12) when that GDS is read back; with the drawn N-well both views are clean
                cmds += [box((rc[0] - .14, rc[1] - .14, rc[2] + .14, rc[3] + .14)), 'paint nwell']
        for rc in ring(a, b):
            cmds += [box((rc[0] + e, rc[1] + e, rc[2] - e, rc[3] - e)), f'paint {cont}']
    cmds += [box((x0 - ISO_DNW, y0 - ISO_DNW, x1 + ISO_DNW, y1 + ISO_DNW)), 'paint dnwell']
    cols = sorted(r['ndiffc'], key=lambda a: a[0])
    ylo, yhi = cols[0][1], cols[0][3]
    xs = [(a[0] + a[2]) / 2 for a in cols]
    src, drn = xs[0::2], xs[1::2]
    for xc in xs:
        cmds += [box((xc - .19, ylo, xc + .19, yhi)), 'paint metal1', 'paint metal2',
                 box((xc - .13, ylo + .06, xc + .13, yhi - .06)), 'paint via1']
    bh = min(3.0, (yhi - ylo) / 2 - 1.0)
    ys = (-0.6 - bh, -0.6)          # source bus y range (below the finger centre)
    yd = (0.6, 0.6 + bh)
    xe = max(x1 + 0.9, xs[-1] + 1.2)                       # first escape beyond the p-well edge
    esc_d = [g5(xe + .9 * k) for k in range(ISO_ESC)]
    esc_s = [g5(-xe - .9 * k) for k in range(ISO_ESC)]
    for (ya, yb), cx_, lo, hi in ((yd, drn, drn[0] - .19, esc_d[-1] + .2), (ys, src, esc_s[-1] - .2, src[-1] + .19)):
        cmds += [box((lo, ya, hi, yb)), 'paint metal3']
        for xc in cx_:
            cmds += [box((xc - .2, ya, xc + .2, yb)), 'paint metal2', box((xc - .14, ya + .07, xc + .14, yb - .07)), 'paint via2']
    pc = sorted(r['polycontact'], key=lambda a: a[0])
    gy0, gy1 = pc[0][1], pc[0][3]
    cmds += [box((pc[0][0] - .055, gy0, pc[-1][2] + .055, gy1)), 'paint metal1']
    gx = (pc[len(pc) // 2][0] + pc[len(pc) // 2][2]) / 2
    yb_ring = y0 + .3                                      # the PCell p-ring bottom Metal1 bar (body)
    pins = [(x, (yd[0] + yd[1]) / 2, 'd', x, 3) for x in esc_d] + [(x, (ys[0] + ys[1]) / 2, 's', x, 3) for x in esc_s]
    pins += [(gx, (gy0 + gy1) / 2, 'g', g5(gx - .4), 1), (g5(gx - 1.6), yb_ring, 'b', g5(gx - 1.6), 1),
             (g5(gx + .8), y0 - ISO_GAP - ISO_RING / 2, 'nw', g5(gx + .8), 1),
             (g5(gx + 2.0), y0 - pg_a - ISO_PG / 2, 'pg', g5(gx + 2.0), 1)]
    cmds += ['units internal', 'save', 'load prim_workspace']
    out = pg_a + ISO_PG + ISO_HALO
    bbox = (min(x0 - out, esc_s[-1] - .5), y0 - out, max(x1 + out, esc_d[-1] + .5), y1 + out)
    well = dict(area_um2=round((x1 - x0) * (y1 - y0), 3), perim_um=round(2 * (x1 - x0 + y1 - y0), 3))
    return cmds, pins, bbox, well


GAP = 2.0                     # um between neighbouring PCell bounding boxes
OFFS4 = (1.2, 0., -1.2, 2.0)  # D, G, S, B escape x offsets from the device centre
OFFS3 = (-1.2, 0., 1.2)       # resistor A (top), B (bottom), body


def generate_layout(sub, work, *, columns=None, quiet=None, over_dev=False, trunks_over=False, row_width=None,
                    matched=None, spaced=(), currents=None, iso_rail='VDD_WIRE_SW', ant_retry=0, trunk_match=(), track_before=None):
    """Write <name>.mag/.gds, DRC counts and extraction products into `work`.

    r10 options (CTLE r4; all default off, other blocks unchanged):
      matched(d) -> bool : a row holding such a device gets NO foreign metal: its Metal4 tracks sit in a band below
                           the devices (even with over_dev) and the row starts to the right of the Metal5 trunk bank
                           (with trunks_over), so only a matched device's own escapes are above it (AP4 review 2).
      spaced             : nets that get an empty track slot / trunk slot on both sides (AP4 review 3).
      currents(d)        : {node index: mA}, + = the net feeds the device terminal.  Row tracks, trunks and their
                           via4 junctions are widened to the 85 C EM limits (Metal1-4 2.09 mA/um, Metal5 4.5 mA/um,
                           0.58 mA/cut) with a 1.3x margin; a single terminal above 0.58 mA/1.3 raises.
      track_before       : {net: other}: in every row, net's track is placed directly before other's (default order is
                           alphabetical), e.g. to put a shared bias line between the two halves of a pair.
      trunk_match        : pairs of nets whose Metal5 trunks are drawn over the same y span (the shorter one gets a
                           dummy extension), so a differential pair split over two rows sees equal trunk capacitance.
      ant_retry          : antenna-diode requests without a legal site get their own row track extended past the
                           right end of the rows and are planned again, up to ant_retry times; what is still
                           unplaced is returned as 'antenna_unplaced' (callers must fail on it)."""
    K = lambda d: (d.model, d.w, d.l) + ((d.nf, 'iso') if d.iso else ())
    EM_K = 1.3
    work.mkdir(parents=True, exist_ok=True)
    for old in work.glob('*'):
        if old.is_file():
            old.unlink()
    kinds = sorted({K(d) for d in sub.devices})
    keys = {k: f'{sub.name}__prim_{i}' for i, k in enumerate(kinds)}   # block-unique (chip GDS merge)
    cmds = ['crashbackups stop', 'load prim_workspace']
    for kk, name in keys.items():
        model, w, l = kk[:3]
        if len(kk) > 3:
            cmds += ['units internal',
                     f'set cell [magic::gencell_makecell gf180mcu::{model} w {w} l {l} nf {kk[3]} guard 1 topc 0 botc 1 '
                     'full_metal 1 gate_to_polycont 0.6 gate_extension 0.8 diff_gate_space 0.3]',
                     'load $cell', f'save {name}', 'load prim_workspace']
        elif model.startswith('ppoly'):
            cmds += ['units internal',
                     f'set cell [magic::gencell_makecell gf180mcu::{model} w {w} l {l} guard 1 full_metal 1]',
                     'load $cell', f'save {name}', 'load prim_workspace']
        else:
            cmds += ['units internal',
                     f'set cell [magic::gencell_makecell gf180mcu::{model} w {w} l {l} nf 1 guard 1 topc 0 botc 1 '
                     'full_metal 1 gate_to_polycont 0.6 gate_extension 0.8 diff_gate_space 0.3]',
                     'load $cell', f'save {name}', 'load prim_workspace']
    cmds += ['quit -noprompt']
    (work / 'primitives.tcl').write_text('\n'.join(cmds) + '\n')
    res = magic(work, 'primitives.tcl')
    pins, boxes, iso_pins, iso_well = {}, {}, {}, {}
    iso_cmds = ['crashbackups stop', 'load prim_workspace']
    for k, name in keys.items():
        if len(k) > 3:
            c_, iso_pins[k], boxes[k], iso_well[name] = _iso_prim(name, work / (name + '.mag'), k[3], k[1])
            iso_cmds += c_
        else:
            pins[k], boxes[k] = _terminals(work / (name + '.mag'))
    if iso_pins:
        (work / 'iso.tcl').write_text('\n'.join(iso_cmds + ['quit -noprompt']) + '\n')
        magic(work, 'iso.tcl')

    def dev_pins(d):
        """[(dx, dy, net, escape dx, kind, gate area, start metal level, mA into the device)] in PCell coordinates."""
        cur_ = (currents(d) if currents else None) or {}
        if d.iso:
            role = dict(d=(d.nodes[0], 'sd', 0), s=(d.nodes[2], 'sd', 2), g=(d.nodes[1], 'g', 1), b=(d.nodes[3], 'x', 3),
                        nw=(iso_rail, 'x', None), pg=('VSS', 'x', None))
            out = []
            for dx, dy, ro, ex, lvl in iso_pins[K(d)]:
                net, kind, idx = role[ro]
                ma = cur_.get(idx, 0.) / ISO_ESC if ro in 'ds' else 0.
                out.append((dx, dy, net, ex, kind, d.nf * d.w * d.l if ro == 'g' else 0., lvl, ma))
            return out
        mos = d.model.startswith(('nfet', 'pfet'))
        offs = OFFS3 if len(d.nodes) == 3 else OFFS4
        return [(dx, dy, net, offs[t], ('g' if t == 1 else 'sd' if t in (0, 2) else 'x') if mos else 'x',
                 d.w * d.l if mos and t == 1 else 0., 1, cur_.get(t, 0.))
                for t, ((dx, dy), net) in enumerate(zip(pins[K(d)], d.nodes))]
    DP = [dev_pins(d) for d in sub.devices]
    for d, pl in zip(sub.devices, DP):
        for q in pl:
            if abs(q[7]) * EM_K > 0.58:
                raise ValueError(f'{d.name}: {q[7]:.2f} mA through one terminal (single-cut escape); split the device')

    # Grid placement: uniform column pitch; each device row carries its own
    # routing band with one Metal4 track per net used in that row.
    wmax = max(b[2] - b[0] for b in boxes.values())
    pitch = max(11., wmax + 7.5)
    n = len(sub.devices)
    nets = sub.nets
    # Trunk order: internal nets (short spans) at 1.0 um pitch, then port nets,
    # which run to the cell edge.  Long parallel M5 port trunks couple strongly
    # (58 fF clock->data observed at 1.0 um pitch), so switching ports are kept
    # apart: quiet (supply/static-control) ports are interleaved between them and
    # two adjacent switching ports get a 4 um gap.
    trunk_pitch = 1.0
    quiet_fn = quiet or (lambda p: p.startswith(('VDD', 'VSS', 'SEL', 'WT')) or p[0].islower())
    if columns is None:
        avg_h = sum(boxes[K(d)][3] - boxes[K(d)][1] for d in sub.devices) / n
        columns = max(1, min(16, round(math.sqrt(n * (avg_h + 8.) / pitch))))
    row_of, r, c, wacc = [], 0, 0, 0.
    for i in range(n):
        # AP4-1 (cdr repack, 2026-11-13): row_width (um) fills each row to a width instead of a device count, so
        # rows of narrow logic devices and rows of wide devices come out equally long.  Default off (count only).
        bi = boxes[K(sub.devices[i])]
        wi = max(bi[2] - bi[0], 3.6) + GAP
        full = (c == columns) if row_width is None else (wacc + wi > row_width)
        if (full and c > 0) or (i in sub.breaks and c > 0):
            r, c, wacc = r + 1, 0, 0.
        row_of.append(r)
        c += 1
        wacc += wi
    rows_list = [[d for d, rr in zip(sub.devices, row_of) if rr == k] for k in range(r + 1)]
    rows_pins = [[pl for pl, rr in zip(DP, row_of) if rr == k] for k in range(r + 1)]
    net_rows = {}
    for i, d in enumerate(sub.devices):
        for q in DP[i]:
            net_rows.setdefault(q[2], set()).add(row_of[i])
    # EM (r10): current each net exchanges with each row -> track widths; trunk width from the row exchanges
    row_in, row_out = {}, {}
    for i, pl in enumerate(DP):
        for q in pl:
            if q[7] > 0:
                row_in[(q[2], row_of[i])] = row_in.get((q[2], row_of[i]), 0.) + q[7]
            elif q[7] < 0:
                row_out[(q[2], row_of[i])] = row_out.get((q[2], row_of[i]), 0.) - q[7]
    cuts = lambda w_: max(1, int((w_ - .12 + .26 + 1e-9) / .52))
    up = lambda v, lo: max(lo, math.ceil(v * 10 - 1e-9) / 10)

    def track_ma(nt, r_):
        return EM_K * max(row_in.get((nt, r_), 0.), row_out.get((nt, r_), 0.))

    def track_w(nt, r_):
        return up(track_ma(nt, r_) / 2.09, .4)

    def trunk_w(nt):
        ex = [row_in.get((nt, r_), 0.) - row_out.get((nt, r_), 0.) for r_ in range(r + 1)]
        i_ = EM_K * max(sum(abs(v) for v in ex) / 2, abs(sum(ex)))
        w_ = up(i_ / 4.5, .44)
        for r_ in range(r + 1):           # the via4 junction with each row track must hold that row's exchange
            need = math.ceil(EM_K * abs(ex[r_]) / .58 - 1e-9)
            while need > cuts(track_w(nt, r_)) * cuts(w_):
                w_ = round(w_ + .1, 2)
        return w_
    # nets confined to one device row are routed on that row's Metal4 track only
    local = {nt for nt, rs in net_rows.items() if len(rs) == 1 and nt not in sub.ports}
    internal = [nt for nt in nets if nt not in sub.ports and nt not in local]
    qp = [p for p in sub.ports if quiet_fn(p)]
    dp = [p for p in sub.ports if not quiet_fn(p)]
    order = []
    while qp or dp:
        if dp:
            order.append(dp.pop(0))
        if qp:
            order.append(qp.pop(0))
    trunk_x, x = {}, 1.0
    twid = {nt: trunk_w(nt) for nt in nets} if currents else {}

    def take(nt, x_):
        """trunk centre for net nt starting at slot x_; returns (centre, next free slot)."""
        extra = max(0, math.ceil((twid.get(nt, .44) - .44) / trunk_pitch - 1e-9))
        sp_ = trunk_pitch if nt in spaced else 0.
        return x_ + sp_ + extra * trunk_pitch / 2, x_ + 2 * sp_ + (1 + extra) * trunk_pitch
    for nt in internal:
        trunk_x[nt], x = take(nt, x)
    x += 2.0
    prev_dyn = False
    for p in order:
        dyn = not quiet_fn(p)
        if dyn and prev_dyn:
            x += 4.0
        trunk_x[p], x = take(p, x)
        x += (1.0 if dyn else 0.)
        prev_dyn = dyn
    trunk_end = x
    x0 = x + 3. + wmax / 2
    if trunks_over:
        # AP4-1 (detect/ctle repack, 2026-11-13): the Metal5 trunks run over the device rows (primitives are Metal1,
        # escapes Metal2/3, row tracks Metal4), so the dedicated trunk column on the left (1 um per net) is not
        # needed; trunk order and spacing rules are unchanged.  Default off.
        x0 = 1.0 + wmax / 2
    rows = len(rows_list)
    cmds = ['crashbackups stop', 'load ' + sub.name + '_h', 'units microns', 'snap internal']

    shapes, cur = [], [None]   # net-tagged rectangles for antenna-diode planning

    def rect(layer, x1, y1, x2, y2):
        cmds.extend([f'box values {min(x1, x2):.3f} {min(y1, y2):.3f} {max(x1, x2):.3f} {max(y1, y2):.3f}',
                     f'paint {layer}'])
        shapes.append((layer, min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2), cur[0]))

    def via(x, y, low, high):
        for m in range(low, high + 1):
            h = .19 if m == 1 else .22 if m == 5 else .2
            rect(f'metal{m}', x - h, y - h, x + h, y + h)
        for m in range(low, high):
            h = .13 if m == 1 else .14
            rect(f'via{m}', x - h, y - h, x + h, y + h)

    def wire(layer, x1, y1, x2, y2, width=None):
        h = width / 2 if width else (.22 if layer == 'metal5' else .2)
        rect(layer, min(x1, x2) - h, min(y1, y2) - h, max(x1, x2) + h, max(y1, y2) + h)

    span = {net: [math.inf, -math.inf] for net in nets}
    placements = []
    keepouts, taps, terminals = [], [], []
    ybase = 2.
    track_pitch = .9
    row_geo = []          # per row: (track_y, band y range) for the antenna retry (r10)
    for r in range(rows):
        row = rows_list[r]
        clear = bool(matched) and any(matched(d) for d in row)
        od = over_dev and not clear
        row_nets = sorted({q[2] for pl in rows_pins[r] for q in pl},
                          key=lambda nt: nets.index((track_before or {}).get(nt, nt)) - (.5 if nt in (track_before or {}) else 0))
        # StrongARM integrating/output nets (named *_1pa,*_2oa,*_3ob,*_4pb) get empty
        # guard tracks on both sides so no switching neighbour couples to one side only
        track_y, track_wd, slot = {}, {}, 0
        for nt in row_nets:
            if nt.endswith('_1pa'):
                slot += 3
            if nt in spaced:
                slot += 1
            tw_ = track_w(nt, r) if currents else .4
            extra = max(0, math.ceil((tw_ - .4) / track_pitch - 1e-9))
            track_y[nt] = ybase + .6 + (slot + extra / 2) * track_pitch
            track_wd[nt] = tw_
            slot += 1 + extra
            if nt in spaced:
                slot += 1
            if nt.endswith('_4pb'):
                slot += 3
        band_top = ybase + .6 + slot * track_pitch + 1.6
        if od:
            # r6 AREA (cdr): the primitives use Metal1 only, so the row's Metal4 tracks (and the Metal2/3
            # escapes) run over the devices; the row is max(device height, band) tall instead of their sum
            band_h, band_top = band_top - ybase, ybase + 1.0
        row_hmax = 0.
        # compact placement: each device gets max(bbox,3.6um)+GAP of width, escapes stay
        # inside +/-2um of the device centre
        cxs, xcur = [], x0 - wmax / 2
        if clear and trunks_over:
            xcur = trunk_end + 3.0           # matched row: right of every Metal5 trunk
        for d in row:
            b = boxes[K(d)]
            wslot = max(b[2] - b[0], 3.6) + GAP
            cxs.append(xcur + wslot / 2 - (b[0] + b[2]) / 2)
            xcur += wslot
        row_w = xcur
        for c, d in enumerate(row):
            k = K(d)
            b = boxes[k]
            row_hmax = max(row_hmax, b[3] - b[1])
            cx = cxs[c]
            cy = band_top - b[1]
            cmds += [f'getcell {keys[k]} child 0 0 parent {cx:.3f} {cy:.3f}', f'identify X{d.name}']
            placements.append(dict(device=d.name, x=round(cx, 3), y=round(cy, 3)))
            keepouts.append((cx + b[0], cy + b[1], cx + b[2], cy + b[3]))
            if not d.model.startswith('pfet'):     # NMOS / resistor guard ring = P-substrate tap
                taps.append(keepouts[-1])
            for dx, dy, net, eo, kind, ga, lvl, _ma in rows_pins[r][c]:
                x, y = cx + dx, cy + dy
                cur[0] = net
                terminals.append((x, y, net, kind, ga))
                esc = cx + eo
                ry = track_y[net]
                if lvl == 1:
                    via(x, y, 1, 2)
                    wire('metal2', x, y, esc, y)
                    via(esc, y, 2, 3)
                else:                              # pin already on a Metal3 bus of the primitive
                    rect('metal3', esc - .2, y - .2, esc + .2, y + .2)
                wire('metal3', esc, y, esc, ry)
                via(esc, ry, 3, 4)
        for net, ry in track_y.items():
            cur[0] = net
            escs = [cxs[c] + q[3] for c in range(len(row)) for q in rows_pins[r][c] if q[2] == net]
            tw_ = track_wd[net]
            if net in local:
                lo_x, hi_x = min(escs), max(escs)
                if hi_x - lo_x < 1.5:
                    hi_x = lo_x + 1.5
                wire('metal4', lo_x, ry, hi_x, ry, width=tw_)
                cmds.extend([f'box values {lo_x - .2:.3f} {ry - .2:.3f} {lo_x + .2:.3f} {ry + .2:.3f}',
                             f'label {net} FreeSans 0.3 0 0 0 c metal4'])
                continue
            wire('metal4', min(trunk_x[net], min(escs)), ry, max(trunk_x[net], max(escs)), ry, width=tw_)
            kw_ = twid.get(net, .44)
            if tw_ > .4 or kw_ > .44:           # EM junction: via4 array over the track x trunk overlap
                hx, hy = max(kw_, .44) / 2, max(tw_, .4) / 2
                rect('metal4', trunk_x[net] - hx, ry - hy, trunk_x[net] + hx, ry + hy)
                rect('metal5', trunk_x[net] - hx, ry - hy, trunk_x[net] + hx, ry + hy)
                rect('via4', trunk_x[net] - hx + .06, ry - hy + .06, trunk_x[net] + hx - .06, ry + hy - .06)
            else:
                via(trunk_x[net], ry, 4, 5)
            span[net][0] = min(span[net][0], ry)
            span[net][1] = max(span[net][1], ry)
        row_geo.append(dict(row=r, y0=round(ybase, 2), tracks=len(track_y), slots=slot, clear=clear, dev_h=round(row_hmax, 2), w=round(row_w, 1), first=row[0].name))
        ybase = band_top + (max(row_hmax, band_h - 1.0) if od else row_hmax) + 1.5
        max_row_w = max(locals().get('max_row_w', 0.), row_w)
    height = ybase + 1.
    width = max_row_w
    top = height
    for a_, b_ in trunk_match:
        if a_ in span and b_ in span and a_ not in local and b_ not in local:
            lo_, hi_ = min(span[a_][0], span[b_][0]), max(span[a_][1], span[b_][1])
            span[a_][0] = span[b_][0] = lo_
            span[a_][1] = span[b_][1] = hi_
    for net in nets:
        if net in local:
            continue
        lo, hi = span[net]
        if net in sub.ports:
            hi = top
        if lo == math.inf:
            lo = top - 2.
        hi = max(hi, lo + 1.5)
        cur[0] = net
        wire('metal5', trunk_x[net], lo, trunk_x[net], hi, width=twid.get(net, .44))
    cur[0] = None
    # r10 self-check of matched=: Metal4 / Metal5 of a net that is not the device's own, drawn over a matched device
    foreign = []
    if matched:
        for d, pl_, ko in zip(sub.devices, DP, keepouts):
            if matched(d):
                own = {q[2] for q in pl_}
                foreign += [(d.name, s_[0], s_[5]) for s_ in shapes if s_[0] in ('metal4', 'metal5') and s_[5] not in own
                            and s_[1] < ko[2] and s_[3] > ko[0] and s_[2] < ko[3] and s_[4] > ko[1]]
    # antenna diodes (KLayout ANT.16): gate-only partial nets with long M2-M5 get an N+/Psub diode
    # under their own M3-M5 wire; returned as 'antenna_diodes' for the LVS reference (lvs_reference).
    req = ad.requests_from_shapes(shapes, terminals)
    dcmds, diodes = ad.plan(req, [s[:5] for s in shapes], keepouts, taps=taps)
    for attempt in range(ant_retry):
        # r10 (AP4 review 1): a request without a legal site (devices under the tracks) gets its own Metal4 row
        # track extended past the right end of the rows, where a diode fits; requests are then planned again
        bad = [rq for rq, dd in zip(req, diodes) if not dd.get('placed')]
        if not bad:
            break
        for n_, rq in enumerate(bad):
            seg = next((sg for sg in rq['segs'] if sg[0] == 'metal4'), None)
            if seg is None:
                continue
            cur[0] = rq['net']
            n_ext = locals().get('n_ext', 0) + 1
            wire('metal4', max(seg[1], seg[3]), seg[2], width + 3.2 * n_ext, seg[2])
        cur[0] = None
        req = ad.requests_from_shapes(shapes, terminals)
        dcmds, diodes = ad.plan(req, [s[:5] for s in shapes], keepouts, taps=taps)
    cmds.extend(dcmds)
    for idx, port in enumerate(sub.ports, 1):
        x = trunk_x[port]
        cmds += [f'box values {x - .22:.3f} {top - 1.0:.3f} {x + .22:.3f} {top:.3f}',
                 f'label {port} FreeSans 0.3 0 0 0 c metal5', f'port make {idx}']
    for net in sorted(set(nets) - set(sub.ports) - local):
        x = trunk_x[net]
        y = span[net][1]
        cmds += [f'box values {x - .22:.3f} {y - .22:.3f} {x + .22:.3f} {y + .22:.3f}',
                 f'label {net} FreeSans 0.3 0 0 0 c metal5']
    flat = sub.name
    cmds += ['select top cell', f'flatten {flat}', f'load {flat}', 'save',
             'select top cell', 'drc euclidean on', 'drc style drc(full)', 'drc check', 'drc catchup',
             'set f [open drc-count.txt w]', 'puts $f [drc list count total]', 'close $f',
             'set f [open drc-details.txt w]', 'puts $f [drc listall why]', 'close $f',
             f'gds write {flat}.gds',
             'select top cell', 'set f [open bbox.txt w]', 'puts $f [box values]', 'close $f',
             'quit -noprompt']
    (work / 'layout.tcl').write_text('\n'.join(cmds) + '\n')
    res = magic(work, 'layout.tcl')
    # Extract in a fresh session from the saved flat cell (in-session extraction
    # after flatten dropped the high-R poly resistor device).
    (work / 'extract.tcl').write_text('\n'.join([
        'crashbackups stop', f'load {flat}', 'extract all',
        'ext2spice lvs', f'ext2spice -o {flat}.lvs.spice',
        'ext2spice lvs', 'ext2spice cthresh 0', f'ext2spice -o {flat}.ext.spice',
        'quit -noprompt']) + '\n')
    magic(work, 'extract.tcl')
    drc_text = (work / 'drc-count.txt').read_text().strip() if (work / 'drc-count.txt').exists() else 'missing'
    try:
        drc = int(drc_text.split()[-1]) if drc_text else 0
    except ValueError:
        drc = None
    bb = [float(v) for v in (work / 'bbox.txt').read_text().split()]
    size = [round(bb[2] - bb[0], 2), round(bb[3] - bb[1], 2)]
    if iso_well:
        (work / 'iso-wells.json').write_text(json.dumps(iso_well, indent=1) + '\n')
    if currents:
        (work / 'em-widths.json').write_text(json.dumps(dict(
            limits='85 C: Metal1-4 2.09 mA/um, Metal5 4.5 mA/um, 0.58 mA/cut; design currents x1.3',
            trunks={nt: dict(width_um=w_) for nt, w_ in sorted(twid.items()) if w_ > .44},
            tracks={f'{nt}@row{r_}': dict(ma_x1p3=round(track_ma(nt, r_), 3), width_um=track_w(nt, r_))
                    for nt in nets for r_ in range(rows) if track_ma(nt, r_) > 0}), indent=1) + '\n')
    return dict(drc_count=drc, drc_raw=drc_text, columns=columns, rows=rows, pitch_um=pitch, antenna_diodes=diodes,
                antenna_unplaced=[d_['net'] for d_ in diodes if not d_.get('placed')], iso_wells=iso_well, row_report=row_geo,
                matched_foreign_metal=sorted(set(foreign)),
                bbox_um=bb, size_um=size, area_um2=round(size[0] * size[1], 1),
                planned_size_um=[round(width, 2), round(height, 2)], placements=len(placements),
                magic_log_tail=res.stdout[-1500:] + res.stderr[-1500:])


def lvs_reference(spice, top, diodes, out):
    """Schematic + the generator's antenna diodes (flat top subckt), written to `out`."""
    text = Path(spice).read_text()
    lines = ad.spice_lines(diodes or [])
    if lines:
        k = text.index(f'.subckt {top} ')
        e = text.index('.ends', k)
        text = text[:e] + '\n'.join(lines) + '\n' + text[e:]
    Path(out).write_text(text)
    return Path(out)


def magic(work, script):
    cmd = f'magic -dnull -noconsole -rcfile {DIGITAL_PDK}/libs.tech/magic/gf180mcuD.magicrc /work/{script}'
    res = docker(DIGITAL_IMAGE, work, cmd, timeout=3600)
    (work / (script + '.log')).write_text(res.stdout + res.stderr)
    if res.returncode:
        raise RuntimeError(f'magic failed on {script}: {res.stderr[-2000:]}')
    return res


def lvs(work, layout_spice, layout_cell, schematic_spice, schematic_cell, out='lvs.txt'):
    import shutil
    shutil.copy(schematic_spice, Path(work) / 'schematic.spice')
    schematic_spice = 'schematic.spice'
    cmd = (f'netgen -batch lvs "{layout_spice} {layout_cell}" "{schematic_spice} {schematic_cell}" '
           f'{DIGITAL_PDK}/libs.tech/netgen/gf180mcuD_setup.tcl {out} -json')
    res = docker(DIGITAL_IMAGE, work, cmd, timeout=3600)
    (work / 'netgen.log').write_text(res.stdout + res.stderr)
    text = (work / out).read_text() if (work / out).exists() else ''
    unique = 'Circuits match uniquely.' in text
    final = re.findall(r'Final result: (.*)', text)
    return dict(unique_match=unique, final_result=final[-1] if final else None,
                netgen_tail=res.stdout[-600:])


def ngspice(work, deck, *, timeout=3600):
    cmd = f'/foss/tools/bin/ngspice -b {deck} > {deck}.log 2>&1; echo rc=$?'
    for attempt in range(3):
        res = docker(ANALOG_IMAGE, work, cmd, timeout=timeout)
        log = (work / f'{deck}.log').read_text() if (work / f'{deck}.log').exists() else ''
        # a killed container leaves a truncated log; retry (observed once on the shared host)
        if 'executed from .control section' in log or 'rror' in log[-2000:]:
            break
    (work / 'docker-rc.txt').write_text(f'{res.returncode} attempts={attempt + 1}\n{res.stdout[-300:]}{res.stderr[-300:]}')
    return log


SIM_HEADER = f""".include {ANALOG_PDK}/libs.tech/ngspice/design.ngspice
.lib {ANALOG_PDK}/libs.tech/ngspice/sm141064.ngspice {{corner}}
.lib {ANALOG_PDK}/libs.tech/ngspice/sm141064.ngspice res_{{rescorner}}
.lib {ANALOG_PDK}/libs.tech/ngspice/sm141064.ngspice diode_{{rescorner}}
.option temp={{temp}} gmin=1e-12 reltol=1e-3
"""


def sim_header(corner='typical', temp=27):
    rc = {'typical': 'typical', 'ff': 'ff', 'ss': 'ss', 'fs': 'typical', 'sf': 'typical'}[corner]
    return SIM_HEADER.format(corner=corner, rescorner=rc, temp=temp)


def sha256(path):
    return 'sha256:' + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parse_meas(log):
    """Collect `name = value` lines printed by ngspice .meas/.print."""
    out = {}
    for m in re.finditer(r'^\s*([a-z_][a-z0-9_]*)\s*=\s*([-+0-9.eE]+)', log, re.M):
        try:
            out[m.group(1)] = float(m.group(2))
        except ValueError:
            pass
    return out


def run_cases(block, sub, netfile, bench_fns, tag, *, corner='typical', temp=27, vdd=3.3, kwargs=None):
    """Run every case of every bench for one netlist/corner; return {case: metrics}."""
    import shutil
    out = {}
    for fn in bench_fns:
        for case, text, analyse in fn(sub, 'dut.spice', corner=corner, temp=temp, vdd=vdd, **(kwargs or {})):
            work = SCRATCH / 'sim' / block / tag / case
            work.mkdir(parents=True, exist_ok=True)
            shutil.copy(netfile, work / 'dut.spice')
            (work / 'tb.cir').write_text(text)
            for old in ('tran.txt', 'ac.txt'):
                if (work / old).exists():
                    (work / old).unlink()
            log = ngspice(work, 'tb.cir')
            data = work / ('tran.txt' if (work / 'tran.txt').exists() else 'ac.txt')
            try:
                metrics = analyse(log, data)
            except Exception as exc:  # recorded, never hidden
                metrics = dict(pass_=False, error=repr(exc)[:300], log_tail=log[-600:])
                metrics['pass'] = False
            if 'error' in log.lower() and 'pass' in metrics and not metrics.get('error'):
                errs = [l for l in log.splitlines() if 'error' in l.lower()][:3]
                if errs:
                    metrics['ngspice_errors'] = errs
            out[case] = metrics
    return out


def slicer_delays(sub, netfile, rates, tag, corner='typical', temp=27, vdd=3.3):
    import shutil
    import sims
    out = {}
    for rate in rates:
        work = SCRATCH / 'sim' / 'slicer' / tag / f'delay_{rate / 1e9:g}G'
        work.mkdir(parents=True, exist_ok=True)
        shutil.copy(netfile, work / 'dut.spice')
        (work / 'tb.cir').write_text(sims.slicer_delay_deck(sub, 'dut.spice', rate, corner, temp, vdd))
        ngspice(work, 'tb.cir')
        try:
            out[rate] = sims.slicer_delay_from(work / 'tran.txt', vdd)
        except Exception:
            out[rate] = 0.
    return out



EXPORT_SH = r"""set -u
export PDK_ROOT=/foss/pdks PDK=gf180mcuD PDKPATH=/foss/pdks/gf180mcuD
export PATH=/foss/tools/bin:/foss/tools/klayout:/foss/tools/sak:$PATH
printf 'crashbackups stop\nload CELL\nselect top cell\ncif ostyle gdsii\ngds write CELL.gds\nquit -noprompt\n' > export.tcl
magic -dnull -noconsole -rcfile $PDKPATH/libs.tech/magic/gf180mcuD.magicrc export.tcl > export.log 2>&1
magic --version > magic-version.txt 2>&1
cat > layers.py <<'XEOF'
import klayout.db as db, json
ly = db.Layout(); ly.read('CELL.gds')
top = ly.top_cell()
out = {}
for li in ly.layer_indexes():
    info = ly.get_info(li)
    out[f'{info.layer}/{info.datatype}'] = sum(1 for _ in top.begin_shapes_rec(li))
json.dump(dict(top=top.name, layers=out), open('layers.json', 'w'), indent=1)
XEOF
python3 layers.py > layers.log 2>&1 || klayout -b -r layers.py >> layers.log 2>&1
rm -rf klayout; sak-drc.sh -k -w /work/klayout /work/CELL.gds > klayout.log 2>&1
echo "KLAYOUT_RC $?" >> klayout.log
"""


def export_gds(work, cell, n_hres):
    """Publishable GDS from the analog image's Magic 8.3.678 (keeps HRES 62/0) + KLayout GF180 DRC."""
    work = Path(work)
    (work / 'export.sh').write_text(EXPORT_SH.replace('CELL', cell))
    args = ['docker', 'run', '--rm', *DOCKER_LIMITS, '--entrypoint', '/bin/bash',
            '--mount', f'type=bind,src={work},dst=/work', '-w', '/work', ANALOG_IMAGE, '/work/export.sh']
    r = subprocess.run(args, capture_output=True, text=True, timeout=7200)
    (work / 'export-stage.log').write_text(r.stdout + r.stderr)
    lay = json.loads((work / 'layers.json').read_text())['layers'] if (work / 'layers.json').exists() else {}
    lyrdbs = list((work / 'klayout').rglob('*.lyrdb')) if (work / 'klayout').exists() else []
    cats = {}
    for f in lyrdbs:
        for m in re.finditer(r'<item>.*?<category>(.*?)</category>', f.read_text(), re.S):
            k = m.group(1).strip("'")
            cats[k] = cats.get(k, 0) + 1
    rc = re.findall(r'KLAYOUT_RC (\d+)', (work / 'klayout.log').read_text()) if (work / 'klayout.log').exists() else []
    out = dict(magic=(work / 'magic-version.txt').read_text().strip() if (work / 'magic-version.txt').exists() else None,
               image=ANALOG_IMAGE, marker_shapes={'HRES 62/0': lay.get('62/0', 0), 'RES_MK 110/5': lay.get('110/5', 0)},
               ppolyf_u_1k_devices=n_hres,
               klayout_drc=dict(violations=sum(cats.values()) if lyrdbs else None, by_rule=cats,
                                rc=rc[-1] if rc else None, lyrdb_files=len(lyrdbs)))
    out['hres_ok'] = n_hres == 0 or out['marker_shapes']['HRES 62/0'] > 0
    out['pass'] = bool((work / f'{cell}.gds').exists() and out['hres_ok'] and out['klayout_drc']['violations'] == 0)
    return out
