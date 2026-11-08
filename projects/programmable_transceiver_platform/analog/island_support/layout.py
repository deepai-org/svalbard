"""Magic layout generator for the island switch and ATB switch cells.

All geometry is computed here (microns) and emitted as a Magic Tcl script.
Device drawing, contact/via sizes and the M3-column / M4-track routing style
follow the DRC-clean precedent in ip/blocks/analog/wireline_serdes/clock_pulse/
layout.tcl. Routing conflicts (same-layer, different-net) are checked in
Python before emission; Magic DRC and Netgen LVS remain the authority.
"""
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import design  # noqa: E402

COL_PITCH = 1.0       # minimum centre spacing of different-net M3 columns
TRACK_PITCH = 1.3


def parse_devices(netlist):
    devs = []
    for line in netlist.splitlines():
        if not line.startswith('X'):
            continue
        tok = line.split()
        p = dict(re.findall(r'\b([wlm])=([\d.]+)', line))
        devs.append({'name': tok[0], 'd': tok[1], 'g': tok[2], 's': tok[3], 'b': tok[4], 'kind': tok[5],
                     'w': float(p['w']), 'l': float(p['l']), 'm': int(p.get('m', 1))})
    return devs


def ports_of(netlist):
    for line in netlist.splitlines():
        if line.startswith('.subckt'):
            t = line.split()
            return t[1], t[2:]
    raise ValueError


class Layout:
    def __init__(self, name):
        self.name = name
        self.rects = []
        self.labels = []
        self.cols = []        # (x, y1, y2, net)
        self.track_y = {}
        self.net_x = {}

    def r(self, layer, x1, y1, x2, y2):
        self.rects.append((layer, min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))

    def via(self, layer, x, y):
        self.r(layer, x - .18, y - .18, x + .18, y + .18)

    def stack(self, x, y, top):
        self.r('metal1', x - .38, y - .38, x + .38, y + .38)
        self.r('metal2', x - .23, y - .23, x + .23, y + .23)
        self.via('via1', x, y)
        if top >= 3:
            self.r('metal3', x - .23, y - .23, x + .23, y + .23)
            self.via('via2', x, y)

    def m2m3(self, x, y):
        self.r('metal2', x - .23, y - .23, x + .23, y + .23)
        self.r('metal3', x - .23, y - .23, x + .23, y + .23)
        self.via('via2', x, y)

    def col_free(self, x, y1, y2, net):
        lo, hi = min(y1, y2) - .7, max(y1, y2) + .7
        for (cx, a, b, n) in self.cols:
            if n != net and abs(cx - x) < COL_PITCH - 1e-6 and not (hi < a or lo > b):
                return False
        return True

    def column(self, x, y, net, bank):
        """Vertical M3 from (x, y) to the net's M4 track in `bank`, via3 at the track."""
        ty = self.track_y[(bank, net)]
        if not self.col_free(x, y, ty, net):
            raise RuntimeError(f'M3 column conflict {self.name} {net} x={x:.2f}')
        self.cols.append((x, min(y, ty), max(y, ty), net))
        self.r('metal3', x - .23, min(y, ty) - .38, x + .23, max(y, ty) + .38)
        self.r('metal4', x - .38, ty - .38, x + .38, ty + .38)
        self.via('via3', x, ty)
        self.net_x.setdefault((bank, net), []).append(x)

    def tcl(self, outdir):
        L = ['crashbackups stop', f'load {self.name}', 'units microns', 'box values 0 0 0 0']
        for (layer, x1, y1, x2, y2) in self.rects:
            L.append(f'box values {x1:.3f} {y1:.3f} {x2:.3f} {y2:.3f}')
            L.append(f'paint {layer}')
        i = 0
        for (name, layer, (x1, y1, x2, y2), *rest) in self.labels:
            is_port = rest[0] if rest else True
            L.append(f'box values {x1:.3f} {y1:.3f} {x2:.3f} {y2:.3f}')
            L.append(f'label {name} FreeSans 0.4 0 0 0 c {layer}')
            if is_port:
                i += 1
                L.append(f'port make {i}')
        L += ['select top cell', f'save {self.name}', f'gds write {self.name}.gds',
              'quit -noprompt']
        return '\n'.join(L) + '\n'


# ---------------------------------------------------------------------------
# One MOS device (multi-finger, shared diffusion) with its three route columns.
# ---------------------------------------------------------------------------

def mos_geometry(dev):
    p = dev['l'] + .52
    nf = dev['m']
    w = dev['w']
    yoff = max(.70, w / 2 - .8)
    return p, nf, w, yoff


def mos_footprint(dev):
    p, nf, w, yoff = mos_geometry(dev)
    span = nf * p
    left = 2.6              # gate column (x0-1.8) and its pad
    right = 1.6             # source column (+0.8) and its pad
    return left + span + right


def draw_mos(lay, dev, x0, cy):
    """x0: first contact column. Returns dict of terminal access points."""
    p, nf, w, yoff = mos_geometry(dev)
    pmos = dev['kind'].startswith('pfet')
    diff, cont = ('pdiff', 'pdc') if pmos else ('ndiff', 'ndc')
    xs = [x0 + i * p for i in range(nf + 1)]
    gates = [x0 + p / 2 + k * p for k in range(nf)]
    lay.r(diff, xs[0] - .18, cy - w / 2, xs[-1] + .18, cy + w / 2)
    gy = cy - max(yoff + .88, w / 2 + .70)
    half = max(.20, dev['l'] / 2)
    for gx in gates:
        lay.r('polysilicon', gx - dev['l'] / 2, gy, gx + dev['l'] / 2, cy + w / 2 + .22)
        lay.r('polycontact', gx - .115, gy - .115, gx + .115, gy + .115)
    lay.r('polysilicon', gates[0] - half, gy - .30, gates[-1] + half, gy + .30)
    for x in xs:
        lay.r(cont, x - .115, cy - w / 2 + .065, x + .115, cy + w / 2 - .065)
        lay.r('metal1', x - .18, cy - w / 2, x + .18, cy + w / 2)
    dy, sy = cy + yoff, cy - yoff
    drains = xs[0::2]
    sources = xs[1::2]
    for x in drains:
        lay.r('metal1', x - .28, cy - .28, x + .28, dy + .28)
        lay.via('via1', x, dy)
        lay.r('metal2', x - .28, dy - .28, x + .28, dy + .28)
    for x in sources:
        lay.r('metal1', x - .28, sy - .28, x + .28, cy + .28)
        lay.via('via1', x, sy)
        lay.r('metal2', x - .28, sy - .28, x + .28, sy + .28)
    xg = x0 - 1.8
    xd = x0 - .8
    xsrc = xs[-1] + .8           # beyond the last diffusion column (even nf ends on a drain)
    # Drain/source M2 straps to their route columns.
    lay.r('metal2', xd - .38, dy - .38, drains[-1] + .38, dy + .38)
    lay.r('metal2', sources[0] - .38, sy - .38, xsrc + .38, sy + .38)
    lay.m2m3(xd, dy)
    lay.m2m3(xsrc, sy)
    lay.r('metal1', xg - .38, gy - .30, gates[-1] + .35, gy + .30)
    lay.stack(xg, gy, 3)
    return {'d': (xd, dy), 's': (xsrc, sy), 'g': (xg, gy),
            'bottom': gy - .5, 'top': max(cy + w / 2 + .3, dy + .5), 'left': x0 - 2.4, 'right': xsrc + .6}


def place_row(lay, devs, x_start, cy, gap=1.2):
    x = x_start
    placed = []
    for dev in devs:
        x0 = x + 2.4
        info = draw_mos(lay, dev, x0, cy)
        placed.append((dev, info))
        x = info['right'] + gap
    return placed, x


def tap_strip(lay, kind, x1, x2, y, net, stack_x, bank):
    """Substrate/well tap strip with M1, joined to its net track by one column."""
    diff, cont = ('nsubdiff', 'nsubdiffcont') if kind == 'n' else ('psubdiff', 'psubdiffcont')
    lay.r(diff, x1 - .37, y - .37, x2 + .37, y + .37)
    lay.r(cont, x1 - .30, y - .25, x2 + .30, y + .25)
    lay.r('metal1', min(x1, stack_x) - .40, y - .40, max(x2, stack_x) + .40, y + .40)
    lay.stack(stack_x, y, 3)
    lay.column(stack_x, y, net, bank)


POWER_NETS = ('VDD', 'VSS', 'VISL')


def build_tracks(lay, bank, nets, y0):
    y = y0
    for net in nets:
        wide = net in POWER_NETS
        y += .15 if wide else 0
        lay.track_y[(bank, net)] = y
        y += TRACK_PITCH + (.15 if wide else 0)
    return y


def finish_tracks(lay, ports):
    for (bank, net), xs in lay.net_x.items():
        y = lay.track_y[(bank, net)]
        half = .38 if net in POWER_NETS else .23
        lay.r('metal4', min(xs) - .38, y - half, max(xs) + .38, y + half)
    done = set()
    for net in list(ports) + sorted({n for _, n in lay.net_x}):
        if net in done:
            continue
        for bank in ('A', 'B'):
            if (bank, net) in lay.net_x:
                x = min(lay.net_x[(bank, net)])
                y = lay.track_y[(bank, net)]
                # Ports are pins; other nets get plain labels so extraction keeps names.
                if net in ports or net not in ('VDD', 'VISL'):
                    lay.labels.append((net, 'metal4', (x - .3, y - .2, x + .3, y + .2), net in ports))
                done.add(net)
                break


def route_devices(lay, placed, bank):
    for dev, info in placed:
        for term in ('d', 's', 'g'):
            x, y = info[term]
            lay.column(x, y, dev[term], bank)


def _ordered(nets_iter):
    out = []
    for n in nets_iter:
        if n not in out:
            out.append(n)
    return out


def logic_block(lay, devs, x_start, y_base, extra_nets=(), edge_net=None):
    """NMOS row + p-tap, bank A, PMOS rows (one per well net, side by side in
    disjoint x ranges) + n-taps, bank B. Nets present in both banks are joined
    by M3 columns to the right of all devices."""
    # edge_net (the tapped/sensitive node): its devices go first in each row,
    # its track is the bank row nearest the PMOS row (top of bank A, bottom of
    # bank B) and the banks are joined at the left edge, keeping its wiring short.
    def first(d):
        return 0 if edge_net in (d['d'], d['s']) else 1
    nm = sorted([d for d in devs if d['kind'].startswith('nfet')], key=first)
    pm_all = sorted([d for d in devs if d['kind'].startswith('pfet')], key=first)
    wells = _ordered(d['b'] for d in pm_all)
    nets_a = _ordered([n for d in nm for n in (d['d'], d['g'], d['s'])] + ['VSS'])
    nets_b = _ordered([n for d in pm_all for n in (d['d'], d['g'], d['s'])] + wells + list(extra_nets))
    if edge_net in nets_a:
        nets_a = [n for n in nets_a if n != edge_net] + [edge_net]
    if edge_net in nets_b:
        nets_b = [edge_net] + [n for n in nets_b if n != edge_net]
    cy_n = y_base + max(max(mos_geometry(d)[3] + .88, d['w'] / 2 + .7) for d in nm) + 1.0
    placed_n, x_end_n = place_row(lay, nm, x_start, cy_n)
    top_n = max(info['top'] for _, info in placed_n)
    y_ptap = top_n + 1.2
    bank_a0 = y_ptap + 1.6
    bank_a1 = build_tracks(lay, 'A', nets_a, bank_a0)
    tap_strip(lay, 'p', x_start + .5, x_end_n - .5, y_ptap, 'VSS', x_start - 1.0, 'A')
    lay.r('pwell', x_start - 2.5, y_base - .5, x_end_n + 1.0, y_ptap + 1.2)
    route_devices(lay, placed_n, 'A')
    x = x_start
    y_row_base = bank_a1 + 1.5
    rows = []
    for well in wells:
        pm = [d for d in pm_all if d['b'] == well]
        cy_p = y_row_base + max(max(mos_geometry(d)[3] + .88, d['w'] / 2 + .7) for d in pm) + .6
        placed_p, x_end_p = place_row(lay, pm, x, cy_p)
        top_p = max(info['top'] for _, info in placed_p)
        rows.append((well, x, x_end_p, placed_p, top_p))
        x = x_end_p + 6.5          # NW.2b: different-potential wells >= 1.7 um apart
    y_ntap = max(r[4] for r in rows) + 1.2
    bank_b0 = y_ntap + 1.6
    bank_b1 = build_tracks(lay, 'B', nets_b, bank_b0)
    x_max = max(x_end_n, x)
    for well, x1, x2, placed_p, _ in rows:
        route_devices(lay, placed_p, 'B')
        tap_strip(lay, 'n', x1 + .5, x2 - .5, y_ntap, well, x2 + .6, 'B')
        lay.r('nwell', x1 - 1.5, y_row_base - .3, x2 + 1.6, y_ntap + 1.2)
    # Bank joins at the right edge.
    if edge_net in nets_a and edge_net in nets_b:
        xl = x_start - 2.6
        ya = lay.track_y[('A', edge_net)]
        lay.column(xl, ya, edge_net, 'B')
        lay.net_x.setdefault(('A', edge_net), []).append(xl)
        lay.r('metal4', xl - .38, ya - .38, xl + .38, ya + .38)
        lay.via('via3', xl, ya)
    xj = x_max + 1.5
    for net in nets_a:
        if net in nets_b and net != edge_net:
            ya = lay.track_y[('A', net)]
            lay.column(xj, ya, net, 'B')
            lay.net_x.setdefault(('A', net), []).append(xj)
            lay.r('metal4', xj - .38, ya - .38, xj + .38, ya + .38)
            lay.via('via3', xj, ya)
            xj += COL_PITCH
    return {'x_max': xj + 1.0, 'nets_a': nets_a, 'nets_b': nets_b, 'y_top': bank_b1 + .5}


def tap_block(lay, devs, edge='NODE'):
    """ATB leaf/group layout with the tapped node kept local: banks outside the
    rows (A below NMOS, B above PMOS), the two T1 devices first in their rows
    with equal drain-column x, joined by one short M3 strap between the rows."""
    def first(d):
        return 0 if edge in (d['d'], d['s']) else 1
    nm = sorted([d for d in devs if d['kind'].startswith('nfet')], key=first)
    pm = sorted([d for d in devs if d['kind'].startswith('pfet')], key=first)
    assert {d['b'] for d in pm} == {'VDD'}
    assert nm[0]['d'] == edge and pm[0]['d'] == edge
    assert sum(edge in (d['d'], d['g'], d['s']) for d in devs) == 2
    nets_a = [n for n in _ordered([n for d in nm for n in (d['d'], d['g'], d['s'])] + ['VSS']) if n != edge]
    nets_b = [n for n in _ordered([n for d in pm for n in (d['d'], d['g'], d['s'])] + ['VDD']) if n != edge]
    bank_a1 = build_tracks(lay, 'A', nets_a, 0.0)
    y_ptap = bank_a1 + 1.6
    goff_n = max(max(mos_geometry(d)[3] + .88, d['w'] / 2 + .7) for d in nm)
    cy_n = y_ptap + 1.0 + goff_n + .2
    placed_n, x_end_n = place_row(lay, nm, 0.0, cy_n)
    top_n = max(info['top'] for _, info in placed_n)
    y_row_base = top_n + 2.0
    goff_p = max(max(mos_geometry(d)[3] + .88, d['w'] / 2 + .7) for d in pm)
    cy_p = y_row_base + goff_p + .6
    placed_p, x_end_p = place_row(lay, pm, 0.0, cy_p)
    top_p = max(info['top'] for _, info in placed_p)
    y_ntap = top_p + 1.2
    bank_b0 = y_ntap + 1.6
    build_tracks(lay, 'B', nets_b, bank_b0)
    # Edge net: direct strap.
    (xn, yn), (xp, yp) = placed_n[0][1]['d'], placed_p[0][1]['d']
    assert abs(xn - xp) < 1e-9
    if not lay.col_free(xn, yn, yp, edge):
        raise RuntimeError('edge strap conflict')
    lay.cols.append((xn, yn, yp, edge))
    lay.r('metal3', xn - .23, yn - .38, xn + .23, yp + .38)
    ym = (yn + yp) / 2
    lay.labels.append((edge, 'metal3', (xn - .2, ym - .3, xn + .2, ym + .3), True))
    for placed, bank in ((placed_n, 'A'), (placed_p, 'B')):
        for dev, info in placed:
            for term in ('d', 's', 'g'):
                if dev[term] != edge:
                    x, y = info[term]
                    lay.column(x, y, dev[term], bank)
    tap_strip(lay, 'p', .5, x_end_n - .5, y_ptap, 'VSS', -1.0, 'A')
    lay.r('pwell', -2.5, y_ptap - 1.0, x_end_n + 1.0, top_n + .5)
    tap_strip(lay, 'n', .5, x_end_p - .5, y_ntap, 'VDD', x_end_p + .6, 'B')
    lay.r('nwell', -1.5, y_row_base - .3, x_end_p + 1.6, y_ntap + 1.2)
    xj = max(x_end_n, x_end_p + 1.6) + 1.5
    for net in nets_a:
        if net in nets_b:
            ya = lay.track_y[('A', net)]
            lay.column(xj, ya, net, 'B')
            lay.net_x.setdefault(('A', net), []).append(xj)
            lay.r('metal4', xj - .38, ya - .38, xj + .38, ya + .38)
            lay.via('via3', xj, ya)
            xj += COL_PITCH


# ---------------------------------------------------------------------------
# Pass-device array (island switch)
# ---------------------------------------------------------------------------

ROW_PITCH = 14.0
STRIPE_W = 1.2
STRIPE_PITCH = 2.4
M5_W = 4.0
M5_GAP = 1.0
EDGE_W = 12.0
EDGE_FEEDS = 4     # label points per edge bar = required ring/island-grid straps (see pass_array)


def pass_array(lay, nf, x0, y0, nets):
    """nf fingers of pfet W=10 L=0.28 in rows; drains VISL, sources VDD,
    gate GATE, well VMAX. Returns side-column x positions."""
    rows, per_row, total = design.array_shape(nf)
    assert total == nf, (nf, total)
    W = design.FINGER_W_UM
    p = design.PASS_L_UM + .52
    xs = [x0 + i * p for i in range(per_row + 1)]
    gates = [x0 + p / 2 + k * p for k in range(per_row)]
    xg, xv, xvisl, xvdd = x0 - 1.8, x0 - 3.0, x0 - 4.2, x0 - 5.4
    stripes = []
    k = 0
    xs0 = x0 + .6
    while xs0 + STRIPE_W / 2 <= xs[-1] + .4:
        stripes.append((xs0, 'VDD' if k % 2 == 0 else 'VISL'))
        xs0 += STRIPE_PITCH
        k += 1
    cys = [y0 + 6.0 + r * ROW_PITCH for r in range(rows)]
    for cy in cys:
        lay.r('pdiff', xs[0] - .18, cy - W / 2, xs[-1] + .18, cy + W / 2)
        gy = cy - W / 2 - .70
        for gx in gates:
            lay.r('polysilicon', gx - .14, gy, gx + .14, cy + W / 2 + .22)
            lay.r('polycontact', gx - .115, gy - .115, gx + .115, gy + .115)
        lay.r('polysilicon', gates[0] - .2, gy - .30, gates[-1] + .2, gy + .30)
        lay.r('metal1', xg - .38, gy - .30, gates[-1] + .35, gy + .30)
        lay.stack(xg, gy, 3)
        for i, x in enumerate(xs):
            lay.r('pdc', x - .115, cy - W / 2 + .065, x + .115, cy + W / 2 - .065)
            lay.r('metal1', x - .18, cy - W / 2, x + .18, cy + W / 2)
            if i % 2 == 0:   # drain -> VISL strap (upper half)
                lay.r('metal1', x - .28, cy + .40, x + .28, cy + W / 2)
                lay.r('via1', x - .18, cy + .50, x + .18, cy + W / 2 - .10)
            else:            # source -> VDD strap (lower half)
                lay.r('metal1', x - .28, cy - W / 2, x + .28, cy - .40)
                lay.r('via1', x - .18, cy - W / 2 + .10, x + .18, cy - .50)
        lay.r('metal2', xs[0] - .40, cy + .40, xs[-1] + .40, cy + W / 2)
        lay.r('metal2', xs[0] - .40, cy - W / 2, xs[-1] + .40, cy - .40)
        for sx, net in stripes:
            if net == 'VISL':
                lay.r('via2', sx - STRIPE_W / 2 + .1, cy + .55, sx + STRIPE_W / 2 - .1, cy + W / 2 - .15)
            else:
                lay.r('via2', sx - STRIPE_W / 2 + .1, cy - W / 2 + .15, sx + STRIPE_W / 2 - .1, cy - .55)
        # VMAX well tap strip above the row
        ty = cy + W / 2 + 1.6
        lay.r('nsubdiff', xs[0] - .37, ty - .37, xs[-1] + .37, ty + .37)
        lay.r('nsubdiffcont', xs[0] - .30, ty - .25, xs[-1] + .30, ty + .25)
        lay.r('metal1', xv - .40, ty - .40, xs[-1] + .40, ty + .40)
        lay.stack(xv, ty, 3)
    y_bot = cys[0] - W / 2 - 1.2
    y_top = cys[-1] + W / 2 + 1.6 + .6
    for sx, net in stripes:
        lay.r('metal3', sx - STRIPE_W / 2, y_bot, sx + STRIPE_W / 2, y_top)
    # Gate and well columns inside the array (vertical M3 at xg, xv).
    for x in (xg, xv):
        lay.r('metal3', x - .23, y_bot - .4, x + .23, y_top)
    for x in (xvisl, xvdd):
        lay.r('metal3', x - .23, y_bot - .4, x + .23, y_top)
    # Per-row M4 bars: VISL over the drain half, VDD over the source half.
    plate_l = xvdd - .6
    plate_r = xs[-1] + .6
    bars = {'VISL': [], 'VDD': []}
    for cy in cys:
        bars['VISL'].append((cy + .5, cy + W / 2 - .1))
        bars['VDD'].append((cy - W / 2 + .1, cy - .5))
    for net, rngs in bars.items():
        for a_, b_ in rngs:
            lay.r('metal4', plate_l, a_, plate_r, b_)
            for sx, sn in stripes:
                if sn == net:
                    lay.r('via3', sx - STRIPE_W / 2 + .12, a_ + .3, sx + STRIPE_W / 2 - .12, b_ - .3)
            xc = xvisl if net == 'VISL' else xvdd
            lay.r('via3', xc - .18, a_ + .3, xc + .18, b_ - .3)
    # M5 grid: interleaved vertical stripes, VDD joined by a top edge bar (ring
    # side), VISL by a bottom edge bar (island side). The top-level ring and
    # island grid are meant to abut these bars along their full length.
    m5 = []
    x = xs[0] - .2
    k = 0
    while x + M5_W <= plate_r + 1e-6:
        m5.append((x, 'VDD' if k % 2 == 0 else 'VISL'))
        x += M5_W + M5_GAP
        k += 1
    top_a, top_b = y_top + .8, y_top + .8 + EDGE_W
    bot_a, bot_b = y_bot - .8 - EDGE_W, y_bot - .8
    for x1, net in m5:
        if net == 'VDD':
            lay.r('metal5', x1, y_bot, x1 + M5_W, top_b)
        else:
            lay.r('metal5', x1, bot_a, x1 + M5_W, y_top)
        for a_, b_ in bars[net]:
            lay.r('via4', x1 + .3, a_ + .3, x1 + M5_W - .3, b_ - .3)
    xl, xr = m5[0][0], m5[-1][0] + M5_W
    lay.r('metal5', xl, top_a, xr, top_b)
    lay.r('metal5', xl, bot_a, xr, bot_b)
    lay.r('nwell', xv - 1.4, y_bot - .6, xs[-1] + 1.6, y_top + .9)
    # Port pads: an M4 strip under each full edge bar, tied up by a via4 field
    # everywhere except a small window that carries the label. Magic's RC
    # extraction drops a port whose label sits on a via cut. A single small pad
    # was measured to add a 0.46 ohm via bottleneck that the real abutment of
    # the ring to the M5 bar would not have.
    # EDGE_FEEDS label windows spread evenly along each bar stand in for the
    # ring / island grid meeting the bar along its length.
    xms = [xl + (xr - xl) * (i + .5) / EDGE_FEEDS for i in range(EDGE_FEEDS)]
    for net, (a_, b_) in (('VDD', (top_a, top_b)), ('VISL', (bot_a, bot_b))):
        ym = (a_ + b_) / 2
        lay.r('metal4', xl + .4, a_ + .4, xr - .4, b_ - .4)
        edges = [xl + .8] + [v for xm in xms for v in (xm - 2.0, xm + 2.0)] + [xr - .8]
        for i in range(0, len(edges), 2):
            lay.r('via4', edges[i], a_ + .8, edges[i + 1], b_ - .8)
        for xm in xms:
            lay.r('via4', xm - 2.0, a_ + .8, xm + 2.0, ym - 1.0)
            lay.labels.append((net, 'metal4', (xm - .4, ym + .1, xm + .4, b_ - 1.6), True))
    return {'xg': xg, 'xv': xv, 'xvisl': xvisl, 'xvdd': xvdd, 'y_bot': y_bot, 'y_top': y_top,
            'x_right': xs[-1] + 1.6, 'rows': rows, 'per_row': per_row, 'stripes': len(stripes)}


def isw_layout(name, nf):
    net = design.isw_netlist(name, nf)
    devs = [d for d in parse_devices(net) if d['name'] != 'XMP']
    _, ports = ports_of(net)
    lay = Layout(name)
    # Control strip stacked under the array; the array's side columns
    # (x0-5.4 .. x0-1.8) sit left of the strip's devices.
    blk = logic_block(lay, devs, 9.0, 0.0, extra_nets=('GATE', 'VMAX', 'VISL', 'VDD'))
    x0 = 9.0
    y0 = blk['y_top'] + EDGE_W + 3.0
    arr = pass_array(lay, nf, x0, y0, None)
    for key, n in (('xg', 'GATE'), ('xv', 'VMAX'), ('xvisl', 'VISL'), ('xvdd', 'VDD')):
        lay.column(arr[key], arr['y_bot'] - .4, n, 'B')
    finish_tracks(lay, [p for p in ports if p not in ('VISL', 'VDD')])
    return lay, {'array': arr, 'logic_x_max': blk['x_max']}


def atb_layout(name):
    net = design.atb_pad_netlist(name) if name == 'atb_pad' else design.atb_tap_netlist(name)
    devs = parse_devices(net)
    _, ports = ports_of(net)
    lay = Layout(name)
    if name == 'atb_pad':
        logic_block(lay, devs, 0.0, 0.0, edge_net='PAD')
        finish_tracks(lay, ports)
    else:
        tap_block(lay, devs, 'NODE')
        finish_tracks(lay, [p for p in ports if p != 'NODE'])
    return lay, {}


def bbox(lay):
    xs = [r[1] for r in lay.rects] + [r[3] for r in lay.rects]
    ys = [r[2] for r in lay.rects] + [r[4] for r in lay.rects]
    return min(xs), min(ys), max(xs), max(ys)


def generate(outdir, cells):
    """cells: list of (name, kind, nf or None). Writes <name>.tcl and <name>.spice."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    info = {}
    for name, kind, nf in cells:
        design.GEOM = False      # LVS reference: W/L/m only
        if kind == 'isw':
            lay, meta = isw_layout(name, nf)
            text = design.isw_netlist(name, nf)
        elif kind == 'logic':
            text = design.iso_clamp_netlist(name)
            lay = Layout(name)
            logic_block(lay, parse_devices(text), 0.0, 0.0)
            finish_tracks(lay, ports_of(text)[1])
            meta = {}
        else:
            lay, meta = atb_layout(name)
            text = design.atb_pad_netlist(name) if name == 'atb_pad' else design.atb_tap_netlist(name)
        design.GEOM = True
        (outdir / f'{name}.tcl').write_text(lay.tcl('/work/layout'))
        (outdir / f'{name}.spice').write_text(text)
        x1, y1, x2, y2 = bbox(lay)
        meta.update({'bbox_um': [round(x1, 3), round(y1, 3), round(x2, 3), round(y2, 3)],
                     'area_um2': round((x2 - x1) * (y2 - y1), 1), 'rects': len(lay.rects)})
        info[name] = meta
    return info


if __name__ == '__main__':
    import json
    out = sys.argv[1] if len(sys.argv) > 1 else '/tmp/isl_layout'
    print(json.dumps(generate(out, [('atb_leaf_s', 'atb', None), ('atb_pad', 'atb', None),
                                    ('isw_test', 'isw', 40)]), indent=1))
