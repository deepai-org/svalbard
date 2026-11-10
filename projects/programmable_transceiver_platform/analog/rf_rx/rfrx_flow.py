"""Layout / DRC / extraction / LVS / ngspice flow for the RF receive family.

Schematic source of truth: the transistor-level ``<block>.spice`` files that
``netlists.py`` writes.  This module parses them (hierarchical: PDK primitives
plus instances of other subcircuits), lays every subcircuit out in Magic and
checks it.

Layout style (same idea as analog/pads and analog/wired_rx, extended with MIM
capacitors and hierarchy):

* every primitive is a single-finger gf180mcuD PCell with its guard ring;
* each primitive terminal gets a short M2 jog to a private M3 escape that drops
  to its own M4 track in the routing band under its placement row;
* every net owns one vertical M5 trunk in a bank on the left edge;
* MIM capacitors (M4/M5 plates) sit in rows like any device; the bands keep
  >=1.2 um from the CAPM layer, and plate pins are dropped to M3;
* a subcircuit that is instantiated by a parent is a "macro": its ports are
  M3 pins on its bottom edge, so the parent routes it exactly like a primitive.
  Parents keep macros as instances (hierarchical extraction / LVS) and flatten
  only the PCells.

Images (always --network none, bounded CPU/memory):
  DIGITAL svalbard/librelane-gf180-canary:2026.08  Magic 8.3.623 / Netgen 1.5.316, /pdk/gf180mcuD
  ANALOG  hpretl/iic-osic-tools (pinned digest)     ngspice-46, /foss/pdks/gf180mcuD
"""
import hashlib
import json
import math
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import antenna_diodes as ad  # noqa: E402
from gds_uniquify import publish_checked  # noqa: E402

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
REPO = PROJECT.parents[1]
SCRATCH = REPO / 'scratch' / 'rf_rx'
GENERATED = HERE / 'generated'

DIGITAL_IMAGE = 'sha256:b60278092f08c0a42fa93ed640d15d84eec53d7799790962781157ec34ceff43'
DIGITAL_TAG = 'svalbard/librelane-gf180-canary:2026.08'
ANALOG_IMAGE = 'sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305'
ANALOG_REF = 'hpretl/iic-osic-tools@sha256:89641950bbf247c522188629992b6271e391e38372ca0f8e3c850480874948a3'
DIGITAL_PDK = '/pdk/gf180mcuD'
ANALOG_PDK = '/foss/pdks/gf180mcuD'
PDK_NOTE = ('layout/LVS: canary image /pdk/gf180mcuD; simulation: analog image ciel gf180mcu '
            'f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7')
DOCKER_LIMITS = ['--network', 'none', '--cpus', '3', '--memory', '6g', '--env', 'OMP_NUM_THREADS=1']

MOS = ('nfet_03v3', 'pfet_03v3')
RES = ('ppolyf_u_1k', 'ppolyf_u')
CAP = ('cap_mim_2f0_m4m5_noshield',)
POWER = ('VDD', 'VSS')

TRACK = .75         # M4 track pitch in routing bands
TRUNK = 1.0         # M5 trunk pitch in the bank
GAP = 1.0           # spacing between device footprints in a row
# Abutting MIM PCells that share a bottom plate trips MIMTM.2 at the merged plate
# edges in this Magic deck, so every capacitor keeps its own plate and bottom pin.
MERGE_CAP_PLATES = False
SIGNAL_TRUNK_EXTRA = 1.2   # extra spacing between two adjacent signal trunks
AGGRESSORS = {'lo_p', 'lo_n'}   # rail-to-rail 2.4 GHz LO: guard tracks and extra trunk spacing
AGGRESSOR_EXTRA = 3.0
# pins that carry DC / slow controls (their nets are AC-quiet, good trunk neighbours)
STATIC_PINS = {'pt_rfrx_inv': '*', 'pt_rfrx_nor2': '*', 'pt_rfrx_nor3': '*', 'pt_rfrx_bias': '*',
               'pt_rfrx_vcm': '*', 'pt_rfrx_tgs': {'on', 'onb'}, 'pt_rfrx_tgm': {'on', 'onb'},
               'pt_rfrx_tgl': {'on', 'onb'}, 'pt_rfrx_nsw': {'on'}, 'pt_rfrx_ota': {'inp', 'vbp', 'pd'}}
STATIC_PORTS = {'ibias', 'en', 'dir_tx', 'inj', 'rx_direct', 'byp_s1', 'byp_s23', 'obs_sel0', 'obs_sel1',
                'bw0', 'bw1', 'bw2', 'bw3', 'gain0', 'gain1', 'gain2', 'gain3', 'gain4', 'gain5', 'gainc0', 'gainc1', 'fz', 'island_off', 'atb_vcm', 'atb_vbp',
                'gain_lo', 'byp', 'atb_nbias', 'obs_en', 'inj_en'}
_PIN_NAMES = {}


def sub_pin_names(model, k):
    return _PIN_NAMES.get(model, [None] * 99)[k]
POWER_TRUNK_W = 2.4


def docker(image, workdir, command, *, timeout=3600):
    args = ['docker', 'run', '--rm', *DOCKER_LIMITS, '--entrypoint', '/bin/sh',
            '--mount', f'type=bind,src={workdir},dst=/work', '-w', '/work', image, '-c', command]
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def sha256(path):
    return 'sha256:' + hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ------------------------------------------------------------------ netlist
@dataclass
class Device:
    name: str
    model: str
    nodes: tuple
    w: float = 0.
    l: float = 0.
    nf: int = 1

    @property
    def kind(self):
        if self.model in MOS:
            return 'mos'
        if self.model in RES:
            return 'res'
        if self.model in CAP or self.model == 'capgroup':
            return 'cap'
        return 'macro'


@dataclass
class Subckt:
    name: str
    ports: list
    devices: list = field(default_factory=list)

    @property
    def nets(self):
        out = []
        for n in list(self.ports) + [n for d in self.devices for n in d.nodes]:
            if n not in out:
                out.append(n)
        return out


def _um(v):
    v = v.lower()
    if v.endswith('u'):
        return float(v[:-1])
    return float(v) * 1e6


def parse_spice(path):
    text = Path(path).read_text().replace('\n+', ' ')
    subs, cur = {}, None
    for raw in text.splitlines():
        line = raw.split(';')[0].strip()
        if not line or line.startswith('*'):
            continue
        tok = line.split()
        key = tok[0].lower()
        if key == '.subckt':
            cur = Subckt(tok[1], tok[2:])
            subs[tok[1]] = cur
            _PIN_NAMES[tok[1]] = tok[2:]
        elif key == '.ends':
            cur = None
        elif cur is not None and key[0] == 'x':
            params = dict(t.split('=', 1) for t in tok[1:] if '=' in t)
            pos = [t for t in tok[1:] if '=' not in t]
            model, nodes = pos[-1], tuple(pos[:-1])
            if model in MOS:
                d = Device(tok[0], model, nodes, _um(params['w']), _um(params['l']))
            elif model in RES:
                d = Device(tok[0], model, nodes, _um(params['r_width']), _um(params['r_length']))
            elif model in CAP:
                d = Device(tok[0], model, nodes, _um(params['c_width']), _um(params['c_length']))
            else:
                d = Device(tok[0], model, nodes)
            prev = cur.devices[-1] if cur.devices else None
            if (prev is not None and d.kind == 'mos' and prev.model == d.model and prev.w == d.w
                    and prev.l == d.l and prev.nodes == d.nodes):
                prev.nf += 1        # consecutive identical parallel fingers -> one multi-finger PCell
            else:
                cur.devices.append(d)
    return subs


# ------------------------------------------------------------------ magic helpers
def magic(work, script, timeout=3600):
    cmd = f'magic -dnull -noconsole -rcfile {DIGITAL_PDK}/libs.tech/magic/gf180mcuD.magicrc /work/{script}'
    res = docker(DIGITAL_IMAGE, work, cmd, timeout=timeout)
    (work / (script + '.log')).write_text(res.stdout + res.stderr)
    if res.returncode:
        raise RuntimeError(f'magic failed on {script}: {res.stderr[-2000:]}')
    return res


def _rects(path):
    layer, out = None, {}
    for line in Path(path).read_text().splitlines():
        if line.startswith('<< '):
            layer = line[3:-3]
        elif line.startswith('rect ') and layer and layer != 'checkpaint':
            out.setdefault(layer, []).append([float(v) * .005 for v in line.split()[1:5]])
    return out


def _bounds(rects):
    return (min(r[0] for r in rects), min(r[1] for r in rects),
            max(r[2] for r in rects), max(r[3] for r in rects))


def prim_key(d):
    def f(v):
        return ('%g' % v).replace('.', 'p')
    short = {'nfet_03v3': 'n', 'pfet_03v3': 'p', 'ppolyf_u_1k': 'rh', 'ppolyf_u': 'rl',
             'cap_mim_2f0_m4m5_noshield': 'c'}[d.model]
    return f'rfrx_{short}_w{f(d.w)}_l{f(d.l)}' + (f'_nf{d.nf}' if d.nf > 1 else '')


def build_primitives(work, devices):
    kinds = {}
    for d in devices:
        kinds[prim_key(d)] = d
    todo = [k for k in sorted(kinds) if not (work / (k + '.mag')).exists()]
    if todo:
        cmds = ['crashbackups stop', 'load prim_workspace']
        for k in todo:
            d = kinds[k]
            if d.kind == 'mos':
                gen = (f'gf180mcu::{d.model} w {d.w} l {d.l} nf {d.nf} guard 1 topc 0 botc 1 full_metal 1 '
                       'gate_to_polycont 0.6 gate_extension 0.8 diff_gate_space 0.3')
            elif d.kind == 'res':
                gen = f'gf180mcu::{d.model} w {d.w} l {d.l} guard 1 full_metal 1'
            else:
                gen = f'gf180mcu::cap_mim_2p0fF w {d.w} l {d.l}'
            cmds += ['units internal', f'set cell [magic::gencell_makecell {gen}]',
                     'load $cell', f'save {k}', 'load prim_workspace']
        cmds += ['quit -noprompt']
        (work / 'primitives.tcl').write_text('\n'.join(cmds) + '\n')
        magic(work, 'primitives.tcl')
        # some MIM PCell sizes violate MIMTM.2 on their own: refuse them early
        caps = [k for k in todo if kinds[k].kind == 'cap']
        if caps:
            cmds = ['crashbackups stop', 'drc euclidean on', 'drc style drc(full)']
            for k in caps:
                cmds += [f'load {k}', 'select top cell', 'drc check', 'drc catchup',
                         f'puts "CAPDRC {k} [drc list count total]"']
            (work / 'capcheck.tcl').write_text('\n'.join(cmds + ['quit -noprompt']) + '\n')
            res = magic(work, 'capcheck.tcl')
            bad = [l for l in res.stdout.splitlines() if l.startswith('CAPDRC') and l.split()[-1] != '0']
            if bad:
                raise ValueError('MIM PCell sizes with standalone DRC errors: ' + '; '.join(bad))
    return {k: primitive_geometry(work / (k + '.mag'), kinds[k]) for k in kinds}


def primitive_geometry(path, d):
    """Pins (local coords), escape x per terminal, bbox and per-terminal extra paint."""
    r = _rects(path)
    bbox = _bounds([a for v in r.values() for a in v])
    ctr = lambda a: ((a[0] + a[2]) / 2, (a[1] + a[3]) / 2)
    if d.kind == 'cap':
        mim = _bounds(r.get('mimcap', []) + r.get('mimcapcontact', []))
        m4 = _bounds(r['metal4'])
        ym = (mim[1] + mim[3]) / 2
        x_top = round((mim[0] + mim[2]) / 2, 3)
        y_tab = m4[1] - 1.6
        x_bot = mim[2] + .8
        pins = [(x_top, y_tab), (x_bot, ym)]
        esc = [x_top, x_bot]
        # top plate: M5 tab down out of the plate, via4 -> M4 landing -> via3 -> M3
        extra = [('rect', 'metal5', x_top - .3, y_tab - .22, x_top + .3, mim[1] + 1.2)]
        fp = (m4[0] - .3, y_tab - .5, m4[2] + .3, m4[3])
        return dict(pins=pins, esc=esc, level=[0, 0], bbox=bbox, fp=fp, extra=extra, kind='cap', mim=mim, m4=m4)
    m1 = r['metal1']
    bar = min((a for a in m1 if (a[2] - a[0]) > .6 * (bbox[2] - bbox[0])), key=lambda a: a[1])
    yb = (bar[1] + bar[3]) / 2
    m1all = m1 + r.get('psubdiffcont', []) + r.get('nsubdiffcont', [])
    vbars = [a for a in m1all if (a[3] - a[1]) > .4 * (bbox[3] - bbox[1])]
    inner_left = max(a[2] for a in vbars if a[0] < 0)
    inner_right = min(a[0] for a in vbars if a[0] > 0)
    if d.kind == 'mos' and d.nf > 1:
        diff = next(k for k in ('ndiffc', 'pdiffc') if k in r)
        strips = sorted(r[diff], key=lambda a: a[0])
        if len(strips) != d.nf + 1:
            raise ValueError(f'unexpected strip count in {path}')
        ylo, yhi = min(a[1] for a in strips), max(a[3] for a in strips)
        if yhi - ylo < 1.4:
            raise ValueError(f'finger too short for split S/D straps in {path}')
        yd, ys = yhi - .24, ylo + .24
        pcs = r['polycontact']
        gy = ctr(pcs[0])[1]
        gx = round(sum(ctr(a)[0] for a in pcs) / len(pcs), 3)
        if (ylo - .055) - (gy + .19) < .23:
            raise ValueError(f'gate strap too close to S/D strips in {path}')
        eR, eL = bbox[2] + .7, bbox[0] - .7
        extra = [('rect', 'metal1', min(a[0] for a in pcs) - .06, gy - .19, max(a[2] for a in pcs) + .06, gy + .19)]
        xs = [ctr(a)[0] for a in strips]
        for i, x in enumerate(xs):
            y = ys if i % 2 == 0 else yd
            extra += [('rect', 'metal1', x - .19, y - .19, x + .19, y + .19),
                      ('rect', 'via1', x - .13, y - .13, x + .13, y + .13),
                      ('rect', 'metal2', x - .2, y - .2, x + .2, y + .2)]
        extra += [('rect', 'metal2', xs[1] - .2, yd - .2, eR + .2, yd + .2),
                  ('rect', 'metal2', eL - .2, ys - .2, xs[-1 if d.nf % 2 == 0 else -2] + .2, ys + .2)]
        bx = inner_right - .19 + .05
        pins = [(eR, yd), (gx, gy), (eL, ys), (bx, yb)]
        esc = [eR, gx, eL, bx]
        level = [2, 1, 2, 1]
        if bx < gx + .7 or eR - bx < .7:
            raise ValueError(f'body escape spacing in {path}')
        fp = (eL - .3, bbox[1], eR + .3, bbox[3])
        return dict(pins=pins, esc=esc, level=level, bbox=bbox, fp=fp, extra=extra, kind='mos')
    if d.kind == 'mos':
        diff = next(k for k in ('ndiffc', 'pdiffc') if k in r)
        src = min(r[diff], key=lambda a: a[0])
        drn = max(r[diff], key=lambda a: a[2])
        gate = min(r['polycontact'], key=lambda a: a[1])
        gx, gy = ctr(gate)
        bx = inner_right - .19 + .05   # pad merges into the ring's right bar: no M1 notch
        if bx < gx + .7:
            raise ValueError(f'body pin too close to gate escape in {path}')
        pins = [ctr(drn), (gx, gy), ctr(src), (bx, yb)]
        esc = [bbox[2] + .7, gx, bbox[0] - .7, bx]
    else:
        pc = r['polycontact']
        top, bot = ctr(max(pc, key=lambda a: a[3])), ctr(min(pc, key=lambda a: a[1]))
        bx = inner_left + .19 - .05
        if bx > bot[0] - .7:
            raise ValueError(f'body pin too close to terminal escape in {path}')
        pins = [top, bot, (bx, yb)]
        esc = [bbox[2] + .7, bot[0], bx]
    fp = (min(esc + [bbox[0]]) - .3, bbox[1], max(esc + [bbox[2]]) + .3, bbox[3])
    return dict(pins=pins, esc=esc, level=[1] * len(pins), bbox=bbox, fp=fp, extra=[], kind=d.kind)


# ------------------------------------------------------------------ layout of one subcircuit
class Painter:
    def __init__(self):
        self.cmds = []
        self.net = None       # net of the shapes being drawn (antenna-diode planning)
        self.shapes = []      # (layer, x1, y1, x2, y2, net)

    def rect(self, layer, x1, y1, x2, y2):
        self.cmds += [f'box values {min(x1, x2):.3f} {min(y1, y2):.3f} {max(x1, x2):.3f} {max(y1, y2):.3f}',
                      f'paint {layer}']
        self.shapes.append((layer, min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2), self.net))

    def via(self, x, y, low, high):
        for m in range(low, high + 1):
            h = .19 if m == 1 else .22 if m == 5 else .2
            self.rect(f'metal{m}', x - h, y - h, x + h, y + h)
        for m in range(low, high):
            h = .13 if m == 1 else .14 if m < 4 else .15
            self.rect(f'via{m}', x - h, y - h, x + h, y + h)

    def wire(self, layer, x1, y1, x2, y2, width=None):
        h = width / 2 if width else (.22 if layer == 'metal5' else .2)
        self.rect(layer, min(x1, x2) - h, min(y1, y2) - h, max(x1, x2) + h, max(y1, y2) + h)


def _snap(v, g=.01):
    return round(round(v / g) * g, 3)


def layout_subckt(sub, work, geoms, macros, *, row_width=None, top=False):
    """Place and route one subcircuit.  Returns macro description (pins, size).

    Rows of devices (tallest first) sit above routing bands.  In each band a net
    owns one M4 track shared by all its terminals in that row.  Each net owns a
    vertical M5 trunk; trunks of nets whose vertical extents do not overlap share
    a bank column (interval packing), which keeps the bank narrow.
    """
    items = []
    capgroups = {}
    for d in sub.devices:
        if d.kind == 'cap' and MERGE_CAP_PLATES:
            capgroups.setdefault(d.nodes[1], []).append(d)
            continue
        g = macros[d.model] if d.kind == 'macro' else geoms[prim_key(d)]
        if len(g['pins']) != len(d.nodes):
            raise ValueError(f'{sub.name}:{d.name} has {len(d.nodes)} nodes, cell has {len(g["pins"])} pins')
        items.append((d, dict(g, cells=[(d.model if d.kind == 'macro' else prim_key(d), 0., 0., d.name)])))
    # MIM capacitors sharing a bottom plate: abut their PCells so the M4 plates merge
    for bot, caps in capgroups.items():
        caps.sort(key=lambda d: -d.w)
        cells, pins, esc, extra, x = [], [], [], [], 0.
        y0 = min(geoms[prim_key(c)]['m4'][1] for c in caps)
        top = max(geoms[prim_key(c)]['m4'][3] - geoms[prim_key(c)]['m4'][1] for c in caps) + y0
        for i, c in enumerate(caps):
            g = geoms[prim_key(c)]
            dx = x - g['m4'][0]
            dy = y0 - g['m4'][1]
            cells.append((prim_key(c), dx, dy, c.name))
            pins.append((g['pins'][0][0] + dx, g['pins'][0][1] + dy))
            esc.append(g['esc'][0] + dx)
            extra += [(e[0], e[1], e[2] + dx, e[3] + dy, e[4] + dx, e[5] + dy) for e in g['extra']]
            if i == 0:
                bpin = (g['pins'][1][0] + dx, g['pins'][1][1] + dy)
            x += g['m4'][2] - g['m4'][0]
        y_tab = min(pp[1] for pp in pins)
        gd = Device('+'.join(c.name for c in caps), 'capgroup', tuple(c.nodes[0] for c in caps) + (bot,))
        gg = dict(pins=pins + [bpin], esc=esc + [bpin[0]], level=[0] * (len(caps) + 1),
                  fp=(-.3, y_tab - .5, x + .3, top), extra=extra, kind='cap', cells=cells, ntop=len(caps))
        items.append((gd, gg))
    nets = sub.nets
    for i, (d, g) in enumerate(items):
        g['order'] = i
    # height classes (tallest first); netlist order inside a class keeps related devices together
    static = set(POWER)
    for d, g in items:
        spins = STATIC_PINS.get(d.model)
        for k, n in enumerate(d.nodes):
            if spins is not None and (spins == '*' or (sub_pin_names(d.model, k) in spins)):
                static.add(n)
            if d.kind == 'mos' and k == 1 and n in ('island_off',):
                static.add(n)
    static |= {n for n in sub.ports if n in STATIC_PORTS}
    hclass = lambda it: round(math.log((it[1]['fp'][3] - it[1]['fp'][1]) + 1.) / math.log(1.6))
    orderings = {'short_first': sorted(items, key=lambda it: (hclass(it), it[1]['order'])),
                 'tall_first': sorted(items, key=lambda it: (-hclass(it), it[1]['order']))}
    port_y = 1.0

    def shelves(rw, order='short_first'):
        rows, cur, cw = [], [], 0.
        for d, g in orderings[order]:
            w = g['fp'][2] - g['fp'][0] + GAP
            if cur and cw + w > rw:
                rows.append(cur)
                cur, cw = [], 0.
            cur.append((d, g))
            cw += w
        if cur:
            rows.append(cur)
        rows_of = {}
        for ri, row in enumerate(rows):
            for d, _ in row:
                for n in d.nodes:
                    rows_of.setdefault(n, set()).add(ri)
        needs_trunk = {n for n in nets if n in sub.ports or len(rows_of.get(n, ())) > 1}
        plan, y = [], port_y + 2.5
        span = {}
        for ri, row in enumerate(rows):
            # relative escape x of every terminal (row starts at 0)
            ext, cx = {}, 0.
            for d, g in row:
                ox = cx - g['fp'][0]
                for ex, n in zip(g['esc'], d.nodes):
                    lo, hi = ext.get(n, (math.inf, -math.inf))
                    ext[n] = (min(lo, ox + ex), max(hi, ox + ex))
                cx += g['fp'][2] - g['fp'][0] + GAP
            # left-edge packing; trunk nets run to the bank (start at -inf)
            ivs = sorted(((-math.inf if n in needs_trunk else lo), hi, n) for n, (lo, hi) in ext.items())
            tracks, tidx = [], {}
            for n in [n for n in ext if n in AGGRESSORS]:
                # large-swing RF clock: own track with an empty guard track on each side
                tracks += [math.inf, math.inf, math.inf]
                tidx[n] = len(tracks) - 2
            for lo, hi, n in ivs:
                if n in tidx:
                    continue
                for ti, last in enumerate(tracks):
                    if last + 1.2 < lo:
                        tracks[ti] = hi
                        tidx[n] = ti
                        break
                else:
                    tracks.append(hi)
                    tidx[n] = len(tracks) - 1
            band0 = y
            track = {n: band0 + .6 + tidx[n] * TRACK for n in ext}
            band_top = band0 + .6 + len(tracks) * TRACK + .4
            cap = any(g['kind'] == 'cap' for _, g in row)
            y_dev = band_top + 1.0
            row_h = max(g['fp'][3] - g['fp'][1] for _, g in row)
            plan.append(dict(row=row, track=track, y_dev=y_dev, band_h=round(band_top - band0, 1), row_h=round(row_h, 1),
                             used_w=round(cx, 1), ntracks=len(tracks)))
            for n in needs_trunk & set(ext):
                lo, hi = span.get(n, (math.inf, -math.inf))
                ty = track[n]
                span[n] = (min(lo, ty), max(hi, ty))
            y = y_dev + row_h + .8
        height = y + 1.
        for n in sub.ports:
            span[n] = (port_y, span.get(n, (port_y, port_y + 1.))[1])
        # bank columns by interval packing (power nets keep their own wide column).  Signal and
        # static (DC / control) nets use separate columns, interleaved so that a signal trunk's
        # neighbours are static nets (M5-M5 coupling then only loads, it does not cross-couple).
        cols, assign = [], {}
        for n in sorted(needs_trunk, key=lambda n: (n not in POWER, span[n][0], n)):
            lo, hi = span[n]
            kind = 'p' if n in POWER else ('x' if n in static else 's')
            if kind != 'p':
                for ci, (cw_, ivs_, k_) in enumerate(cols):
                    if k_ == kind and all(hi + 1.5 < a_ or lo - 1.5 > b_ for a_, b_ in ivs_):
                        ivs_.append((lo, hi))
                        assign[n] = ci
                        break
            if n not in assign:
                cols.append([POWER_TRUNK_W if kind == 'p' else .44, [(lo, hi)], kind])
                assign[n] = len(cols) - 1
        pw = [i for i, c in enumerate(cols) if c[2] == 'p']
        sg = [i for i, c in enumerate(cols) if c[2] == 's']
        st = [i for i, c in enumerate(cols) if c[2] == 'x']
        seq = list(pw)
        while sg or st:
            if sg:
                seq.append(sg.pop(0))
            if st:
                seq.append(st.pop(0))
        xs, x, prev = [0.] * len(cols), 1.5, None
        for ci in seq:
            cw_, _, k_ = cols[ci]
            if prev is not None:
                x += (TRUNK - .44) + (SIGNAL_TRUNK_EXTRA if (k_ == 's' and cols[prev][2] == 's') else 0.)
                if any(n_ in AGGRESSORS and assign[n_] in (ci, prev) for n_ in assign):
                    x += AGGRESSOR_EXTRA
            xs[ci] = _snap(x + cw_ / 2)
            x += cw_
            prev = ci
        x += (TRUNK - .44)
        bank_right = x + 1.5
        wmax = max(pr['used_w'] for pr in plan)
        trunk = {n: (xs[assign[n]], cols[assign[n]][0]) for n in sorted(needs_trunk)}
        return dict(plan=plan, span=span, trunk=trunk, bank_right=bank_right, ncols=len(cols),
                    long_nets=sorted(((round(span[n][1] - span[n][0]), n) for n in needs_trunk), reverse=True)[:40],
                    width=bank_right + wmax + 1., height=height, rows=len(rows))

    widest = max(g['fp'][2] - g['fp'][0] + GAP for _, g in items)
    best = None
    for order in orderings:
        for k in range(80):
            rw = widest * (1.06 ** k) if row_width is None else row_width
            L = shelves(rw, order)
            if row_width is None and max(L['width'] / L['height'], L['height'] / L['width']) > 2.5:
                continue
            if best is None or L['width'] * L['height'] < best[0]:
                best = (L['width'] * L['height'], rw, order)
    L = shelves(best[1], best[2])
    trunk, span = L['trunk'], L['span']
    p = Painter()
    placed = []
    keepouts, taps, terminals = [], [], []
    for pr in L['plan']:
        cx = L['bank_right']
        reach = {}
        for d, g in pr['row']:
            fp = g['fp']
            ox = _snap(cx - fp[0])
            oy = _snap(pr['y_dev'] - fp[1])
            for cell, dx, dy, nm in g['cells']:
                p.cmds += [f'getcell {cell} child 0 0 parent {ox + dx:.3f} {oy + dy:.3f}', f'identify {nm}']
                placed.append(dict(name=nm, cell=cell, x=ox + dx, y=oy + dy))
            keepouts.append((ox + fp[0], oy + fp[1], ox + fp[2], oy + fp[3]))
            if g['kind'] != 'cap' and not d.model.startswith('pfet'):   # NMOS/resistor guard ring, macro taps
                taps.append(keepouts[-1])
            for ex_ in g['extra']:
                if ex_[0] == 'top_tab':
                    xt, ym, xin = ex_[1]
                    p.wire('metal5', ox + xt, oy + ym, ox + xin, oy + ym, width=.6)
                elif ex_[0] == 'rect':
                    _, layer, x1, y1, x2, y2 = ex_
                    p.rect(layer, ox + x1, oy + y1, ox + x2, oy + y2)
            for t, ((px, py), ex, net, lev) in enumerate(zip(g['pins'], g['esc'], d.nodes, g['level'])):
                X, Y, E = ox + px, oy + py, ox + ex
                ty = pr['track'][net]
                p.net = net
                if g['kind'] == 'mos':
                    terminals.append((X, Y, net, 'g' if t == 1 else 'sd' if t in (0, 2) else 'x',
                                      d.w * d.l if t == 1 else 0.))
                elif g['kind'] == 'macro':
                    # child port: diffusion (or a child antenna diode) protects; else its gate area counts
                    pr_, ga_ = (g.get('port_info') or [(True, 0.)] * len(d.nodes))[t]
                    terminals.append((X, Y, net, 'sd' if pr_ else 'g', ga_))
                if g['kind'] == 'macro':
                    pass
                elif g['kind'] == 'cap':
                    p.via(E, Y, 3, 5 if t < g.get('ntop', 1) else 4)
                elif lev == 2:
                    p.via(E, Y, 2, 3)
                elif abs(E - X) < 1e-6:
                    p.via(X, Y, 1, 3)
                else:
                    p.via(X, Y, 1, 2)
                    p.wire('metal2', X, Y, E, Y)
                    p.via(E, Y, 2, 3)
                p.wire('metal3', E, Y, E, ty)
                p.via(E, ty, 3, 4)
                lo_, hi_ = reach.get(net, (math.inf, -math.inf))
                reach[net] = (min(lo_, E), max(hi_, E))
            cx += fp[2] - fp[0] + GAP
        for net, (xa, xe) in reach.items():
            ty = pr['track'][net]
            p.net = net
            if net in trunk:
                tx = trunk[net][0]
                p.wire('metal4', tx, ty, xe, ty)
                p.via(tx, ty, 4, 5)
            elif xe > xa:
                p.wire('metal4', xa, ty, xe, ty)
    # ---- trunks, ports, labels
    pins = []
    for n in trunk:
        lo, hi = span[n]
        p.net = n
        p.wire('metal5', trunk[n][0], lo, trunk[n][0], max(hi, lo + 1.), width=trunk[n][1])
    p.net = None
    # antenna diodes (KLayout ANT.16): gate-only partial nets with long M2-M5 get an N+/Psub diode
    # under their own M3-M5 wire; reported as 'antenna_diodes' for the LVS reference.
    req = ad.requests_from_shapes(p.shapes, terminals)
    dcmds, diodes = ad.plan(req, [s[:5] for s in p.shapes], keepouts, taps=taps)
    p.cmds += dcmds
    for i, n in enumerate(sub.ports, 1):
        xx = trunk[n][0]
        p.via(xx, port_y, 3, 5)
        p.cmds += [f'box values {xx - .2:.3f} {port_y - .2:.3f} {xx + .2:.3f} {port_y + .2:.3f}',
                   f'label {n} FreeSans 0.25 0 0 0 c metal3', f'port make {i}']
        pins.append((xx, port_y))
    for n in trunk:
        if n in sub.ports:
            continue
        xx, yy = trunk[n][0], span[n][1]
        p.cmds += [f'box values {xx - .2:.3f} {yy - .2:.3f} {xx + .2:.3f} {yy + .2:.3f}',
                   f'label {n} FreeSans 0.25 0 0 0 c metal5']
    width, height = L['width'], L['height']
    flat = [f'select cell {nm}\nflatten -doinplace' for d, g in items if d.kind != 'macro' for _, _, _, nm in g['cells']]
    script = ['crashbackups stop', 'drc off', f'load {sub.name}', 'units microns', 'snap internal'] + p.cmds + \
        flat + ['select top cell', 'save', 'quit -noprompt']
    (work / f'{sub.name}.tcl').write_text('\n'.join(script) + '\n')
    if (work / f'{sub.name}.mag').exists():
        (work / f'{sub.name}.mag').unlink()
    magic(work, f'{sub.name}.tcl')
    dnets = {q['net'] for q in diodes if q.get('placed')}
    port_info = [(n in dnets or any(k_ == 'sd' and n_ == n for _, _, n_, k_, _ in terminals),
                  sum(a_ for _, _, n_, k_, a_ in terminals if n_ == n and k_ == 'g')) for n in sub.ports]
    return dict(pins=pins, esc=[pp[0] for pp in pins], level=[3] * len(pins), bbox=(0., 0., width, height),
                fp=(-.5, 0., width + .5, height), extra=[], kind='macro', port_info=port_info, antenna_diodes=diodes,
                size_um=[round(width, 2), round(height, 2)], placed=placed, nets=len(nets), rows=L['rows'],
                bank_um=round(L['bank_right'], 1), ncols=L['ncols'], long_nets=L['long_nets'],
                row_report=[(len(pr['row']), pr['band_h'], pr['row_h'], pr['used_w']) for pr in L['plan']])


def layout_quad(sub, work, geoms):
    """Hand-placed symmetric passive mixer quad (pt_rxmix_quad).

    Four identical multi-finger NMOS in a row (A B C D, see netlists.quad).  Drains (rf) go up to
    two M4 rails, sources (x) and gates (lo) go down: rail order below the devices is x_p, x_n,
    VSS (shield), lo_p, lo_n.  Every gate stub crosses x_p and x_n once, every lo_p device sits
    next to one x_p and one x_n source, and port stubs are ordered lo_n, lo_p, VSS, x_p, x_n,
    rf_p, rf_n, so each LO net couples equally to the p and n sides of rf and x."""
    devs = sub.devices
    want = [('rf_p', 'lo_p', 'x_p'), ('rf_n', 'lo_p', 'x_n'), ('rf_p', 'lo_n', 'x_n'), ('rf_n', 'lo_n', 'x_p')]
    if [d.nodes[:3] for d in devs] != want:
        raise ValueError('pt_rxmix_quad: unexpected device order/connectivity')
    g = geoms[prim_key(devs[0])]
    p = Painter()
    order = ['lo_n', 'lo_p', 'VSS', 'x_p', 'x_n', 'rf_p', 'rf_n']
    stub_x = {n: 1.5 + i * 1.2 for i, n in enumerate(order)}
    fp = g['fp']
    y_dev = 9.3                                    # device bbox bottom: puts the port row at y = 1
    oy = y_dev - g['bbox'][1]
    bot = {n: y_dev - 1.5 - i * 1.2 for i, n in enumerate(['x_p', 'x_n', 'VSS', 'lo_p', 'lo_n'])}
    top_y = oy + g['bbox'][3]
    top = {n: top_y + 1.5 + i * 1.2 for i, n in enumerate(['rf_p', 'rf_n'])}
    rail = dict(bot, **top)
    port_y = min(bot.values()) - 2.0
    x = stub_x['rf_n'] + 2.5
    placed = []
    for d in devs:
        ox = _snap(x - fp[0])
        p.cmds += [f'getcell {prim_key(d)} child 0 0 parent {ox:.3f} {oy:.3f}', f'identify {d.name}']
        placed.append(d.name)
        for e in g['extra']:
            _, layer, x1, y1, x2, y2 = e
            p.rect(layer, ox + x1, oy + y1, ox + x2, oy + y2)
        for (px, py), ex, net, lev in zip(g['pins'], g['esc'], d.nodes, g['level']):
            X, Y, E = ox + px, oy + py, ox + ex
            if lev == 2:
                p.via(E, Y, 2, 3)
            else:
                p.via(X, Y, 1, 3)
            p.wire('metal3', E, Y, E, rail[net])
            p.via(E, rail[net], 3, 4)
        x += fp[2] - fp[0] + GAP
    x_end = x
    for n, y in rail.items():
        p.wire('metal4', stub_x[n] - .3, y, x_end, y, width=.5)
    pins = []
    for i, n in enumerate(sub.ports, 1):
        xs = stub_x[n]
        p.via(xs, rail[n], 3, 4)
        p.wire('metal3', xs, rail[n], xs, port_y)
        p.cmds += [f'box values {xs - .2:.3f} {port_y - .2:.3f} {xs + .2:.3f} {port_y + .2:.3f}',
                   f'label {n} FreeSans 0.25 0 0 0 c metal3', f'port make {i}']
        pins.append((xs, port_y))
    height = max(top.values()) + 1.5
    width = x_end + 1.
    flat = [f'select cell {nm}\nflatten -doinplace' for nm in placed]
    script = ['crashbackups stop', 'drc off', f'load {sub.name}', 'units microns', 'snap internal'] + p.cmds + \
        flat + ['select top cell', 'save', 'quit -noprompt']
    (work / f'{sub.name}.tcl').write_text('\n'.join(script) + '\n')
    if (work / f'{sub.name}.mag').exists():
        (work / f'{sub.name}.mag').unlink()
    magic(work, f'{sub.name}.tcl')
    return dict(pins=pins, esc=[pp[0] for pp in pins], level=[3] * len(pins), bbox=(0., 0., width, height),
                fp=(-.5, 0., width + .5, height), extra=[], kind='macro',
                size_um=[round(width, 2), round(height, 2)], placed=placed, nets=len(sub.nets), rows=1,
                bank_um=0., ncols=0, long_nets=[], row_report=[])


HANDMADE = {'pt_rxmix_quad': layout_quad}


def macro_order(subs, top):
    order, seen = [], set()

    def visit(name):
        if name in seen:
            return
        seen.add(name)
        for d in subs[name].devices:
            if d.kind == 'macro':
                if d.model not in subs:
                    raise ValueError(f'unknown subcircuit {d.model} used in {name}')
                visit(d.model)
        order.append(name)
    visit(top)
    return order


def build_block(spice, top, work, *, row_widths=None):
    """Lay out `top` and every subcircuit it uses, then DRC + extract + LVS."""
    work.mkdir(parents=True, exist_ok=True)
    (work / Path(spice).name).write_text(Path(spice).read_text())
    subs = parse_spice(spice)
    order = macro_order(subs, top)
    prims = [d for n in order for d in subs[n].devices if d.kind != 'macro']
    geoms = build_primitives(work, prims)
    macros = {}
    for name in order:
        if name in HANDMADE:
            macros[name] = HANDMADE[name](subs[name], work, geoms)
            continue
        macros[name] = layout_subckt(subs[name], work, geoms, macros,
                                     row_width=(row_widths or {}).get(name), top=(name == top))
    # ---- DRC, GDS, extraction
    cmds = ['crashbackups stop', f'load {top}', 'select top cell', 'expand',
            'extract all',
            'ext2spice lvs', f'ext2spice -o {top}.lvs.spice',
            'ext2spice lvs', 'ext2spice cthresh 0', f'ext2spice -o {top}.ext.spice',
            'select top cell', 'set f [open bbox.txt w]', 'puts $f [box values]', 'close $f',
            'drc euclidean on', 'drc style drc(full)', 'drc check', 'drc catchup',
            'set f [open drc-count.txt w]', 'puts $f [drc list count total]', 'close $f',
            'drc count total',
            'set f [open drc-details.txt w]', 'puts $f [drc listall why]', 'close $f',
            'cif ostyle gdsii',   # drc(full) switches the CIF output style; GDS must use gdsii
            f'gds write {top}.gds',
            'quit -noprompt']
    (work / 'check.tcl').write_text('\n'.join(cmds) + '\n')
    magic(work, 'check.tcl')
    drc_raw = (work / 'drc-count.txt').read_text().strip()
    tot = re.findall(r'Total DRC errors found: (\d+)', (work / 'check.tcl.log').read_text())
    drc = int(tot[-1]) if tot else None
    bb = [float(v) * .005 for v in (work / 'bbox.txt').read_text().split()]
    # LVS reference = schematic + every subcircuit's antenna diodes (each cell is its own layout cell)
    ref = Path(spice).read_text()
    for name, m in macros.items():
        lines = ad.spice_lines(m.get('antenna_diodes') or [], prefix=f'DANT_{name}_')
        if lines:
            k = re.search(rf'(?mi)^\.subckt\s+{re.escape(name)}\s', ref).start()
            e = ref.lower().index('.ends', k)
            ref = ref[:e] + '\n'.join(lines) + '\n' + ref[e:]
    (work / 'lvs_reference.spice').write_text(ref)
    lv = lvs(work, f'{top}.lvs.spice', top, 'lvs_reference.spice', top)
    return dict(drc_count=drc, drc_raw=drc_raw, bbox_um=[round(v, 2) for v in bb],
                area_um2=round((bb[2] - bb[0]) * (bb[3] - bb[1]), 0),
                lvs=lv, cells={k: dict(size_um=v['size_um'], rows=v['rows'], nets=v['nets'], bank_um=v['bank_um'],
                                       row_report=v['row_report'])
                               for k, v in macros.items()})


def lvs(work, layout_spice, layout_cell, schematic_spice, schematic_cell, out='lvs.txt'):
    cmd = (f'netgen -batch lvs "{layout_spice} {layout_cell}" "{schematic_spice} {schematic_cell}" '
           f'{DIGITAL_PDK}/libs.tech/netgen/gf180mcuD_setup.tcl {out}')
    res = docker(DIGITAL_IMAGE, work, cmd)
    (work / 'netgen.log').write_text(res.stdout + res.stderr)
    text = (work / out).read_text() if (work / out).exists() else ''
    log = res.stdout
    final = [f.strip() for f in re.findall(r'Final result: (.*)', text) if f.strip()]
    unique = bool(final) and 'Circuits match uniquely' in final[-1]
    return dict(unique_match=unique, final_result=final[-1] if final else None,
                top_level_match=('Circuits match uniquely' in text.split('Subcircuit summary')[-1]) if text else False)


# ------------------------------------------------------------------ ngspice
def sim_header(corner='typical', temp=27):
    rc = {'typical': 'typical', 'ff': 'ff', 'ss': 'ss', 'fs': 'typical', 'sf': 'typical'}[corner]
    return (f'.include {ANALOG_PDK}/libs.tech/ngspice/design.ngspice\n'
            f'.lib {ANALOG_PDK}/libs.tech/ngspice/sm141064.ngspice {corner}\n'
            f'.lib {ANALOG_PDK}/libs.tech/ngspice/sm141064.ngspice res_{rc}\n'
            f'.lib {ANALOG_PDK}/libs.tech/ngspice/sm141064.ngspice mimcap_{rc}\n'
            f'.lib {ANALOG_PDK}/libs.tech/ngspice/sm141064.ngspice diode_{rc}\n'   # antenna diodes (extracted)
            f'.option temp={temp} gmin=1e-12 reltol=1e-3\n')


def ngspice(work, deck, *, timeout=3600):
    res = docker(ANALOG_IMAGE, work, f'/foss/tools/bin/ngspice -b {deck} > {deck}.log 2>&1; echo rc=$?', timeout=timeout)
    return (work / f'{deck}.log').read_text()


def parse_meas(log):
    out = {}
    for m in re.finditer(r'^\s*([a-z_][a-z0-9_]*)\s*=\s*([-+0-9.eE]+)', log, re.M):
        try:
            out[m.group(1)] = float(m.group(2))
        except ValueError:
            pass
    return out


# ------------------------------------------------------------------ per-block entry point
BLOCKS = ('lna', 'rxmix_i', 'rxmix_q', 'bbfilter_i', 'bbfilter_q', 'bb_tap')


def export_gds(work, top):
    """GDS export with the analog image's Magic 8.3.678.  The canary Magic 8.3.623 gdsii style
    drops the HRES (62/0) marker of ppolyf_u_1k resistors (checked: layer absent), which would
    fabricate 1k-poly resistors as plain p+ poly."""
    (work / 'gds.tcl').write_text('\n'.join(['crashbackups stop', f'load {top}', 'cif ostyle gdsii',
                                             f'gds write {top}_gdsii.gds', 'quit -noprompt']) + '\n')
    res = docker(ANALOG_IMAGE, work, f'/foss/tools/bin/magic -dnull -noconsole -rcfile '
                 f'{ANALOG_PDK}/libs.tech/magic/gf180mcuD.magicrc /work/gds.tcl')
    (work / 'gds.tcl.log').write_text(res.stdout + res.stderr)
    if res.returncode or not (work / f'{top}_gdsii.gds').exists():
        raise RuntimeError('GDS export failed: ' + res.stderr[-1000:])
    return work / f'{top}_gdsii.gds'


def klayout_drc(work, gds, top):
    """Independent KLayout gf180mcu DRC (sak-drc.sh -k, analog image).  Returns violation counts."""
    import shutil
    from collections import Counter
    kd = work / 'klayout'
    if kd.exists():
        shutil.rmtree(kd)
    kd.mkdir()
    shutil.copy(gds, kd / f'{top}.gds')
    args = ['docker', 'run', '--rm', *DOCKER_LIMITS, '--env', 'PDK=gf180mcuD', '--env', f'PDKPATH={ANALOG_PDK}',
            '--entrypoint', '/bin/bash', '--mount', f'type=bind,src={kd},dst=/work', '-w', '/work', ANALOG_IMAGE,
            '-lc', f'sak-drc.sh -k -w /work/out /work/{top}.gds > /work/klayout.log 2>&1']
    subprocess.run(args, capture_output=True, text=True, timeout=7200)
    dbs = list((kd / 'out').glob('*/*.lyrdb'))
    if not dbs:
        return dict(ran=False, log_tail=(kd / 'klayout.log').read_text()[-800:])
    t = dbs[0].read_text()
    cats = Counter(re.findall(r'<item>.*?<category>(.*?)</category>', t, re.S))
    return dict(ran=True, violations=sum(cats.values()), by_rule=dict(cats), deck='gf180mcuD klayout (sak-drc.sh -k)')


def generate(block):
    """Layout + DRC + extraction + LVS for one block; publish results into generated/."""
    import shutil
    top = f'pt_{block}'
    work = SCRATCH / 'layout' / block
    if work.exists():
        shutil.rmtree(work)
    res = build_block(HERE / f'{block}.spice', top, work)
    # self-contained flat view for inspection: cell `<block>` in generated/<block>.mag
    (work / 'flat.tcl').write_text('\n'.join([
        'crashbackups stop', f'load {top}', 'select top cell', f'flatten -nolabels {block}',
        f'load {block}', 'select top cell', 'save', 'quit -noprompt']) + '\n')
    magic(work, 'flat.tcl')
    GENERATED.mkdir(exist_ok=True)
    gds = export_gds(work, top)
    res['klayout_drc'] = klayout_drc(work, gds, top)
    shutil.copy(gds, GENERATED / f'{block}.gds')
    res['klayout_precheck'] = publish_checked(GENERATED / f'{block}.gds', block, top)   # unique names + KLayout precheck
    shutil.copy(work / f'{block}.mag', GENERATED / f'{block}.mag')
    shutil.copy(work / f'{top}.ext.spice', GENERATED / f'{block}.ext.spice')
    shutil.copy(work / f'{top}.lvs.spice', GENERATED / f'{block}.lvs.spice')
    shutil.copy(work / 'lvs.txt', GENERATED / f'{block}-lvs.txt')
    drc_details = (work / 'drc-details.txt').read_text()
    res.update(block=block, top_cell=top, digital_image=DIGITAL_IMAGE, digital_tag=DIGITAL_TAG,
               drc_details=drc_details.strip(),
               sources={p.name: sha256(p) for p in (HERE / f'{block}.spice', HERE / 'netlists.py',
                                                      Path(__file__))},
               artifacts={p: sha256(GENERATED / p) for p in
                          (f'{block}.gds', f'{block}.mag', f'{block}.ext.spice', f'{block}-lvs.txt')})
    (GENERATED / f'{block}-layout.json').write_text(json.dumps(res, indent=1) + '\n')
    return res


if __name__ == '__main__':
    import sys
    for b in (sys.argv[1:] or BLOCKS):
        r = generate(b)
        print(b, 'DRC', r['drc_count'], 'LVS', r['lvs']['final_result'], 'area_um2', r['area_um2'])
