#!/usr/bin/env python3
"""QVCO r5 RF tank layout (LO owner, 2026-11-11): hand-placed strips (rfstrip.py) for everything that
carries tank current, PDK MIM PCells for the band bank, engine-placed bias/PRE/ATB aux cell.

Floorplan (core I at left, core Q its mirror image at right; inner edges face each other):
  bank   16 unit cells per core in 2 columns x 8 (15 band units: bit k = 2^k cells; 1 fixed-C cell).
         Unit cell: MIM_P | B-line channel (M2) | switch strip (5 x 5 um + 2 pull-downs) | MIM_N.
         MIM top plates (M5) = tank nodes: one vertical M5 bus per MIM column (P N | N P).
  rows   (top->bottom) varactor, header, PMOS pair, coupling B, coupling A, NMOS pair, tail x2.
         Tank M5 buses continue down over M4 straps (via4) and drop via3 onto every strip's M3 P/N bus.
         Coupling: core I's strip (row A) has its gate bars extended on M3 into core Q to Q's straps;
         core Q's strip (row B) mirrored.  No routing channel carries tank current.
Layers: M1 device/bars, M2+M3 horizontal in-strip buses and bars, M4 vertical straps (+ MIM bottom
plates in the bank), M5 tank buses / MIM top plates.
    python3 qvco_rf_layout.py rf [tag]
"""
import json
import math
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import layout_engine as le  # noqa: E402
import rfstrip as R  # noqa: E402

ROOT = HERE.parents[4]
WORK = ROOT / 'scratch' / 'lo' / 'r4_qvco2'

# r5 sizes (qvco_r5.py P0 + layout units)
D = dict(
    nn=24, ncp=8, np=32, wf=5.0,          # fingers per side (pair, coupling, PMOS), finger W
    tail_f=40, tail_w=20.0,               # tail: per core 2 rows x tail_f/2 ... (total tail_f*tail_w*2 = 1600 um)
    hdr_f=50, hdr_w=10.0,                 # header PMOS fingers x W per core
    var_f=17, var_w=10.0, var_l=1.0,      # varactor fingers per side
    mim=8.4,                              # bank unit MIM side (um)
    cfix_mim=8.4,                         # fixed-C cell MIM side (the 16th cell; series pair across P-N)
    sw_f=5, sw_w=5.0,                     # unit switch fingers x W (+ 2 pull-down fingers)
)
MIMX, MIMY = 10.8, 9.6        # PCell M4 ring size for the 8.4 um cap (scaled with the cap below)


class XF(R.RF):
    """RF painter with an x transform: x' = ox + sx * x (sx = +1 core I, -1 core Q)."""
    def __init__(self, base=None):
        super().__init__()
        self.ox, self.sx = 0.0, 1
        if base is not None:
            self.cmds, self.shapes = base.cmds, base.shapes

    def rect(self, layer, x1, y1, x2, y2):
        a, b = self.ox + self.sx * x1, self.ox + self.sx * x2
        super().rect(layer, a, y1, b, y2)

    def label(self, net, layer, x, y, port=None):
        super().label(net, layer, self.ox + self.sx * x, y, port)

    def inst(self, cell, x, y, flip=False):
        """Place subcell with its origin at local (x, y); flip mirrors it in x (combined with sx)."""
        gx = self.ox + self.sx * x
        mirror = (self.sx < 0) != flip
        self.cmds += [f'getcell {cell}' + (' h' if mirror else '') + f' child 0 0 parent {R.s(gx)} {R.s(y)}']


def mim_ring(side):
    """PCell geometry (um, relative to its origin) for a square cap of `side` (cap_mim_2p0fF)."""
    h = side / 2
    return dict(cap=(-h - 0.6 + 0.6 - 0.0, -h, h, h),
                contact=(-h + 0.4 - 0.6, -h + 0.4, h - 0.4 - 0.6, h - 0.4),
                ring=(-h - 1.2 + 0.0, -h - 0.6, h + 1.2, h + 0.6),
                v4=(h + 0.45, -h - 0.265, h + 0.89, h + 0.265))


def mim_geom(side):
    # measured on the 8.4 / 20 um PCells (pc/mimb0.mag, mim20.mag): cap x [-h-0.6, h-0.6], contact x [-h-0.2, h-1.0],
    # y [-h+0.4, h-0.4]; M4 ring x [-h-1.2, h+1.2], y [-h-0.6, h+0.6]; via4 strip x [h+0.45, h+0.89], y [-h-0.265, h+0.265]
    h = side / 2
    return dict(cap=(-h - 0.6, -h, h - 0.6, h), contact=(-h - 0.2, -h + 0.4, h - 1.0, h - 0.4),
                ring=(-h - 1.2, -h - 0.6, h + 1.2, h + 0.6), v4=(h + 0.45, -h - 0.265, h + 0.89, h + 0.265))


# ---------------------------------------------------------------- bank unit cell (local coordinates)
CELL_H = 10.9                # MIM rings 9.6 tall: >= 1.2 um ring-to-ring (KLayout MIMTM.1)
CHAN = [('B0', 11.7), ('B1', 12.5), ('B2', 13.3), ('B3', 14.1), ('VSS', 14.9)]


def bank_cell(L, x0, y0, bnet, mimname, fixed=False):
    """One unit at (x0, y0) local; MIM_P left, MIM_N right (mirrored).  Returns tank-bus x ranges.
    fixed: no switch, X and Y joined on M4 (series MIM pair across P-N)."""
    g = mim_geom(D['mim'])
    rx = g['ring'][2]                       # ring half-width (5.4)
    cy = y0 + CELL_H / 2
    cxp = x0 + rx
    L.inst(mimname, cxp, cy)
    # switch strip
    sx0 = x0 + 16.0
    nf = D['sw_f']
    cols = ['VSS'] + ['X' if i % 2 == 0 else 'Y' for i in range(nf + 1)] + ['VSS']
    gates = [bnet] * (nf + 2)
    ys0 = y0 + 2.4
    gs = None
    if not fixed:
        gs = L.strip(sx0, ys0, D['sw_w'], 0.28, 'n', cols, gates, {'bot': bnet, 'top': bnet},
                     {'X': (0.2, 1.4), 'Y': (1.8, 3.0), 'VSS': (3.4, 4.6)}, taps='bot', tapnet='VSS')
        xr = gs['x2']
    else:
        xr = sx0 + (nf + 2) * 0.88 + 0.185
    cxn = xr + 0.55 + rx
    L.inst(mimname, cxn, cy, flip=True)
    # MIM_N ring inner edge (flipped): x from cxn - rx
    xn_in = cxn - rx
    xp_in = cxp + rx
    if not fixed:
        b = gs['buses']
        # X -> MIM_P ring (M4 stub over the channel), Y -> MIM_N ring
        xa, ya, xb_, yb = b['X']
        L.rect('metal4', xp_in - 0.5, ya, xa + 0.9, yb)
        L.varea(3, xa + 0.07, ya + 0.07, xa + 0.75, yb - 0.07)
        xa, ya, xb_, yb = b['Y']
        L.rect('metal4', xb_ - 0.9, ya, xn_in + 0.5, yb)
        L.varea(3, xb_ - 0.75, ya + 0.07, xb_ - 0.07, yb - 0.07)
        # VSS bus -> channel VSS line (M2), tap -> VSS line
        xa, ya, xb_, yb = b['VSS']
        vx = x0 + dict(CHAN)['VSS']
        L.rect('metal2', vx - 0.2, ya, xa + 0.3, yb)
        tn, tx1, ty1, tx2, ty2 = gs['taps']['bot']
        L.rect('metal1', vx - 0.19, ty1, tx1 + 0.3, ty2)
        L.rect('via1', vx - 0.13, (ty1 + ty2) / 2 - 0.13, vx + 0.13, (ty1 + ty2) / 2 + 0.13)
        # gate bars -> B line (M1 extension + via1)
        bx = x0 + dict(CHAN)[bnet]
        for k in ('bot', 'top'):
            yb_ = gs['ybar'][k]
            L.rect('metal1', bx - 0.19, yb_ - 0.19, gs['xg'][0], yb_ + 0.19)
            L.rect('via1', bx - 0.13, yb_ - 0.13, bx + 0.13, yb_ + 0.13)
    else:
        # fixed cell: join the two bottom plates on M4 at mid height
        L.rect('metal4', xp_in - 0.5, cy - 1.0, xn_in + 0.5, cy + 1.0)
    width = cxn + rx - x0
    return dict(xp=cxp, xn=cxn, width=width)


# ---------------------------------------------------------------- whole RF cell
def build(tag='', params=None):
    p = dict(D)
    p.update(params or {})
    D.update(p)
    work = WORK / ('rf' + tag)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    g = mim_geom(D['mim'])
    # MIM PCells
    mt = ['crashbackups stop', 'units internal',
          f"set c [magic::gencell_makecell gf180mcu::cap_mim_2p0fF w {D['mim']} l {D['mim']}]", 'load $c', 'save mimu',
          'quit -noprompt']
    (work / 'mim.tcl').write_text('\n'.join(mt) + '\n')
    le.docker_magic(work, 'mim.tcl')
    L = XF()
    L.auto_port = True
    info = {}
    for core, (ox, sx) in (('I', (0.0, 1)), ('Q', (2 * 79.0 + 2.0, -1))):
        L.ox, L.sx = ox, sx
        info[core] = core_layout(L, core)
    script = R.magic_script('pt_lc_qvco_rf', L.cmds)
    (work / 'layout.tcl').write_text(script)
    le.docker_magic(work, 'layout.tcl')
    (work / 'drc.tcl').write_text(R.drc_script('pt_lc_qvco_rf'))
    le.docker_magic(work, 'drc.tcl')
    print((work / 'drc-count.txt').read_text()[:4000])
    (work / 'info.json').write_text(json.dumps(info, indent=1, default=str))
    return work


BANK_Y = None
SPLIT_LABELS = True
XM = 40.2                                  # strip centre (TS strap)
OXQ = 160.0                                # core Q mirror origin
# side straps (local x, M4 width); tank straps are under the M5 buses
COLGAP = 1.6                               # MIM ring to ring >= 1.2 um (MIMTM.1)
STRAPS = {'VSS': (5.3, 1.0), 'VT': (6.6, 0.6), 'TS': (XM + 0.3, 2.0), 'VDDC': (74.6, 1.2), 'VDD': (76.2, 1.4),
          'CMLSEL': (77.6, 0.6), 'IBIAS': (78.6, 0.6)}


def via3_on(L, x, w, y1, y2):
    """M3 (already there) -> M4 strap at x (width w): via3 area over y1..y2."""
    L.varea(3, x - w / 2 + 0.07, y1 + 0.07, x + w / 2 - 0.07, y2 - 0.07)


def hook(L, rect, x, w, top=3):
    """Extend an M2/M3 bus or bar rectangle (x1,y1,x2,y2) on M3 to strap x and drop a via3 there."""
    x1, y1, x2, y2 = rect
    a, b = min(x1, x - w / 2), max(x2, x + w / 2)
    L.rect('metal3', a, y1, b, y2)
    via3_on(L, x, w, y1, y2)


def tap_hook(L, rect, x, w):
    """Tap row (M1) -> strap at x: extend M1, via1/2/3 stack."""
    net, x1, y1, x2, y2 = rect
    a, b = min(x1, x - w / 2), max(x2, x + w / 2)
    L.rect('metal1', a, y1, b, y2)
    L.rect('metal2', x - w / 2, y1, x + w / 2, y2)
    L.rect('metal3', x - w / 2, y1, x + w / 2, y2)
    L.varea(1, x - w / 2 + 0.07, y1 + 0.07, x + w / 2 - 0.07, y2 - 0.07)
    L.varea(2, x - w / 2 + 0.07, y1 + 0.07, x + w / 2 - 0.07, y2 - 0.07)
    via3_on(L, x, w, y1, y2)


def rows_paint(L, core, rows, bus, bank_y, out):
    other = 'Q' if core == 'I' else 'I'
    P, N, OP, ON = core + 'P', core + 'N', other + 'P', other + 'N'
    TS, VDDC = 'TS' + core, 'VDDC' + core
    hb = 3.0
    tank = {P: bus[P], N: bus[N]}
    def tank_hooks(g, nets):
        for net in nets:
            r = g['buses'].get(net)
            rects = [r] if r else []
            rects += [v[1:] for v in g.get('bars', {}).values() if v[0] == net]
            for rr in rects:
                for x in tank[net]:
                    hook(L, rr, x, 2 * hb - 0.4)
    st = {k: v for k, v in STRAPS.items()}
    def centred(n, pitch):
        return XM - n * pitch / 2
    # ---- tails (two rows, L = 1)
    nt = D['tail_f']
    for key in ('T1', 'T2'):
        y0 = rows[key] + 2.4
        cols = ['VSS' if i % 2 == 0 else TS for i in range(nt + 1)]
        g = L.strip(centred(nt, 1.6), y0, D['tail_w'], 1.0, 'n', cols, ['IBIAS'] * nt, {'bot': 'IBIAS', 'top': 'IBIAS'},
                    {TS: (1.0, 9.0), 'VSS': (11.0, 19.0)}, taps='both', tapnet='VSS')
        hook(L, g['buses'][TS], *st['TS'])
        hook(L, g['buses']['VSS'], *st['VSS'])
        for k in ('bot', 'top'):
            hook(L, g['bars'][k][1:], *st['IBIAS'])
            tap_hook(L, g['taps'][k], *st['VSS'])
    # ---- NMOS cross pair
    n = 2 * D['nn']
    unit_c, unit_g = ['TS', 'P', 'TS', 'N'], ['N', 'N', 'P', 'P']
    rep = n // 4
    mp = {'TS': TS, 'P': P, 'N': N}
    cols = [mp[c] for c in unit_c * rep] + [TS]
    gates = [mp[c] for c in unit_g * rep]
    y0 = rows['N'] + 2.4
    g = L.strip(centred(n, 0.88), y0, D['wf'], 0.28, 'n', cols, gates, {'bot': N, 'top': P},
                {P: (0.2, 1.4), TS: (1.8, 3.0), N: (3.4, 4.6)}, taps='both', tapnet='VSS')
    tank_hooks(g, (P, N))
    hook(L, g['buses'][TS], *st['TS'])
    for k in ('bot', 'top'):
        tap_hook(L, g['taps'][k], *st['VSS'])
    # ---- coupling: own strip in row CA (core I) / CB (core Q); gate bars to the other core's straps
    n = 2 * D['ncp']
    rep = n // 4
    # P-QVCO sign inversion (qvco.spice: XCI IP IN QP QN, XCQ QP QN IN IP): core I P-drain gate = QN, N-drain = QP;
    # core Q P-drain gate = IP, N-drain = IN
    gpd, gnd = (ON, OP) if core == 'I' else (OP, ON)
    mpc = {'TS': TS, 'P': P, 'N': N, 'GN': gpd, 'GP': gnd}
    cols = [mpc[c] for c in unit_c * rep] + [TS]
    gates = [mpc[c] for c in ['GN', 'GN', 'GP', 'GP'] * rep]
    y0 = rows['CA' if core == 'I' else 'CB'] + 2.4
    g = L.strip(centred(n, 0.88), y0, D['wf'], 0.28, 'n', cols, gates, {'bot': gpd, 'top': gnd},
                {P: (0.2, 1.4), TS: (1.8, 3.0), N: (3.4, 4.6)}, taps='both', tapnet='VSS')
    tank_hooks(g, (P, N))
    hook(L, g['buses'][TS], *st['TS'])
    for k in ('bot', 'top'):
        tap_hook(L, g['taps'][k], *st['VSS'])
    other_x = {OP: [OXQ - x for x in bus[P]], ON: [OXQ - x for x in bus[N]]}   # mirror: other core's P/N straps   # other core's straps, local x
    for k in ('bot', 'top'):
        net = g['bars'][k][0]
        x = min(other_x[net])                       # nearest (inner) strap of the other core
        hook(L, g['bars'][k][1:], x, 2 * hb - 0.4)
    # ---- PMOS cross pair (nwell = VDDC)
    n = 2 * D['np']
    rep = n // 4
    mpp = {'TS': VDDC, 'P': P, 'N': N}
    cols = [mpp[c] for c in unit_c * rep] + [VDDC]
    gates = [mpp[c] for c in unit_g * rep]
    y0 = rows['P'] + 3.2
    g = L.strip(centred(n, 0.88), y0, D['wf'], 0.28, 'p', cols, gates, {'bot': N, 'top': P},
                {P: (0.2, 1.4), VDDC: (1.8, 3.0), N: (3.4, 4.6)}, taps='both', tapnet=VDDC)
    tank_hooks(g, (P, N))
    hook(L, g['buses'][VDDC], *st['VDDC'])
    for k in ('bot', 'top'):
        tap_hook(L, g['taps'][k], *st['VDDC'])
    # ---- header PMOS (nwell = VDD): VDDC <- VDD, gate CMLSEL (active-high off)
    n = D['hdr_f']
    cols = [VDDC if i % 2 == 0 else 'VDD' for i in range(n + 1)]
    y0 = rows['H'] + 3.2
    g = L.strip(centred(n, 0.88), y0, D['hdr_w'], 0.28, 'p', cols, ['CMLSEL'] * n, {'bot': 'CMLSEL', 'top': 'CMLSEL'},
                {VDDC: (0.4, 4.6), 'VDD': (5.4, 9.6)}, taps='both', tapnet='VDD')
    hook(L, g['buses'][VDDC], *st['VDDC'])
    hook(L, g['buses']['VDD'], *st['VDD'])
    for k in ('bot', 'top'):
        hook(L, g['bars'][k][1:], *st['CMLSEL'])
        tap_hook(L, g['taps'][k], *st['VDD'])
    # ---- varactors (nwell = VTUNE): gates alternate P/N, shared well contacts
    n = 2 * D['var_f']
    cols = ['VTUNE'] * (n + 1)
    gates = [P if i % 2 == 0 else N for i in range(n)]
    y0 = rows['V'] + 1.6
    g = L.strip(centred(n, 1.6), y0, D['var_w'], D['var_l'], 'v', cols, gates, {'bot': N, 'top': P},
                {'VTUNE': (4.4, 5.6)})
    tank_hooks(g, (P, N))
    hook(L, g['buses']['VTUNE'], *st['VT'])
    # ---- side straps (M4), from the aux gap (y = -2) to their top row
    tops = {'VSS': rows['CB'] + 11.0, 'VT': rows['V'] + 9.0, 'TS': rows['CB'] + 9.0, 'VDDC': rows['H'] + 13.0,
            'VDD': rows['H'] + 16.0, 'CMLSEL': rows['H'] + 16.0, 'IBIAS': rows['T2'] + 26.0}
    for k, (x, w) in st.items():
        L.rect('metal4', x - w / 2, -2.0, x + w / 2, tops[k])
    # VSS: the bank VSS line (M3, edge) runs down on the VSS strap; join at the top of the VSS strap
    via3_on(L, st['VSS'][0], st['VSS'][1], tops['VSS'] - 1.0, tops['VSS'])
    lab = {'VSS': 'VSS', 'VT': 'VTUNE', 'TS': TS, 'VDDC': VDDC, 'VDD': 'VDD', 'CMLSEL': 'CMLSEL', 'IBIAS': 'IBIAS'}
    sfx = '' if not SPLIT_LABELS else '_' + core
    for k, (x, w) in st.items():
        nm = lab[k] if k in ('TS', 'VDDC', 'VSS') else lab[k] + sfx
        L.label(nm, 'metal4', x, -1.6)
    for n, x in out['edge'].items():
        if n != 'VSS':
            L.label(n + sfx, 'metal3', x, -1.6)
    for net, xl in bus.items():
        L.label(net, 'metal5', xl[0], out['bank_top'] + (1.0 if net == P else 7.0))
    L.rect('metal3', st['VSS'][0] - 0.5, tops['VSS'] - 1.0, st['VSS'][0] + 0.5, tops['VSS'])


def core_layout(L, core):
    """Paint one core in local coordinates (outer edge x = 0).  Returns straps."""
    other = 'Q' if core == 'I' else 'I'
    P, N = core + 'P', core + 'N'
    OP, ON = other + 'P', other + 'N'
    TS, VDDC = 'TS' + core, 'VDDC' + core
    out = {}
    # ---- row y positions (bottom -> top)
    y = 0.0
    rows = {}
    def take(h):
        nonlocal y
        y0 = y
        y += h
        return y0
    # strip heights: W + 2 * (BAR_OFF + 0.18 + 0.37) + taps (0.95 + 0.3) per side
    tail_h = D['tail_w'] + 2 * (0.7 + 0.5) + 2 * 1.4
    rows['T1'] = take(tail_h + 0.8)
    rows['T2'] = take(tail_h + 0.8)
    std = D['wf'] + 2 * 1.2 + 2 * 1.4 + 0.8
    rows['N'] = take(std)
    rows['CA'] = take(std)
    rows['CB'] = take(std)
    rows['P'] = take(std + 1.6)
    rows['H'] = take(D['hdr_w'] + 2 * 1.2 + 2 * 1.4 + 2.4)
    rows['V'] = take(D['var_w'] + 2 * 1.2 + 2.4 + 4.6)
    bank_y = take(0.0)
    # ---- bank
    cells = []
    bits = [0] + [1] * 2 + [2] * 4 + [3] * 8          # 15 band units, bit k -> 2^k cells
    order = []                                         # interleave bits over the 16 positions (bit 3 spread)
    pos = list(range(16))
    assign = {0: 'B3', 1: 'B2', 2: 'B3', 3: 'B1', 4: 'B3', 5: 'B2', 6: 'B3', 7: 'VSS',
              8: 'B3', 9: 'B2', 10: 'B3', 11: 'B0', 12: 'B3', 13: 'B2', 14: 'B3', 15: 'B1'}
    col_x = [6.0, None]
    xs = {}
    for i in range(16):
        col, r = divmod(i, 8)
        bn = assign[i]
        yb = bank_y + r * CELL_H
        if col == 0:
            c = bank_cell(L, 6.0, yb, bn, 'mimu', fixed=(bn == 'FIX'))
            xs.setdefault(0, c)
        else:
            # column 1 mirrored: local mirror about its own centre -> paint with a temporary flip of sx
            w0 = xs[0]['width']
            x1 = 6.0 + w0 + COLGAP
            sx0, ox0 = L.sx, L.ox
            L.ox = ox0 + sx0 * (x1 + w0)          # column-1 origin at its right edge, painted mirrored
            L.sx = -sx0
            c = bank_cell(L, 0.0, yb, bn, 'mimu', fixed=(bn == 'FIX'))
            L.sx, L.ox = sx0, ox0
            xs.setdefault(1, dict(xp=x1 + w0 - c['xp'], xn=x1 + w0 - c['xn'], width=c['width']))
    bank_top = bank_y + 8 * CELL_H
    # ---- tank buses (M5) over the MIM columns, local x
    hb = 3.4
    cont = mim_geom(D['mim'])['contact']
    off = (cont[0] + cont[2]) / 2                      # contact-region centre offset from the cap origin (P side)
    bus = {P: [xs[0]['xp'] + off, xs[1]['xp'] - off], N: [xs[0]['xn'] - off, xs[1]['xn'] + off]}
    ylo = rows['N'] - 0.5
    ptop, njoin = bank_top + 2.0, (bank_top + 3.0, bank_top + 11.0)
    for net, xl in bus.items():
        for x in xl:
            L.rect('metal5', x - hb, ylo, x + hb, ptop if net == P else njoin[1])
            # M4 strap under the bus in the row region (below the bank)
            L.rect('metal4', x - hb + 0.4, ylo, x + hb - 0.4, bank_y - 1.0)
            L.varea(4, x - hb + 0.6, ylo + 0.2, x + hb - 0.6, bank_y - 1.2)
    out['bus'] = bus
    # P join (M4 under the N buses, >= 1.2 um above the top MIM rings) and N join (M5) above the bank
    xa, xb = min(bus[P]), max(bus[P])
    L.rect('metal4', xa - hb, bank_top + 0.6, xb + hb, ptop)
    for x in bus[P]:
        L.varea(4, x - hb + 0.1, bank_top + 0.7, x + hb - 0.1, ptop - 0.1)
    L.rect('metal5', min(bus[N]) - hb, njoin[0], max(bus[N]) + hb, njoin[1])
    out['ptop'], out['njoin'] = ptop, njoin
    # B lines: vertical M2 per column channel through the bank, then M3 horizontals at the bank bottom
    # (rows of the bank) and the outer-edge vertical M3 down to the aux gap
    chan_x = {0: [(n, 6.0 + x) for n, x in CHAN]}
    w0 = xs[0]['width']
    x1 = 6.0 + w0 + COLGAP
    chan_x[1] = [(n, x1 + w0 - x) for n, x in CHAN]
    yb0 = bank_y - 0.6
    for col in (0, 1):
        for n, x in chan_x[col]:
            L.rect('metal2', x - 0.2, yb0 - 0.2 - 0.8 * [c[0] for c in CHAN].index(n), x + 0.2, bank_top - 0.2)
    edge = {'B0': 0.8, 'B1': 1.6, 'B2': 2.4, 'B3': 3.2, 'VSS': STRAPS['VSS'][0]}
    for k, (n, _) in enumerate(CHAN):
        yh = yb0 - 0.8 * k
        xs_n = [x for col in (0, 1) for nn, x in chan_x[col] if nn == n]
        L.rect('metal3', edge[n] - 0.2, yh - 0.2, max(xs_n) + 0.2, yh + 0.2)
        for x in xs_n:
            L.rect('via2', x - 0.14, yh - 0.14, x + 0.14, yh + 0.14)
        L.rect('metal3', edge[n] - 0.2, -2.0, edge[n] + 0.2, yh + 0.2)
    out['edge'] = edge
    out['bank_top'] = bank_top
    rows_paint(L, core, rows, bus, bank_y, out)
    out['rows'] = rows
    out['bank'] = dict(y=bank_y, top=bank_top, cols=xs)
    return out


def ref_netlist(cell='pt_lc_qvco_rf', split=True):
    """LVS reference of the RF cell (both cores), written from the same parameters as the painter."""
    lines = [f'* {cell}: LVS reference generated by qvco_rf_layout.py']
    sfx = lambda c: ('_' + c) if split else ''
    ports = set()
    k = 0
    def dev(s):
        nonlocal k
        k += 1
        lines.append(f'X{k} ' + s)
    assign = {0: 'B3', 1: 'B2', 2: 'B3', 3: 'B1', 4: 'B3', 5: 'B2', 6: 'B3', 7: 'VSS',
              8: 'B3', 9: 'B2', 10: 'B3', 11: 'B0', 12: 'B3', 13: 'B2', 14: 'B3', 15: 'B1'}
    for c, o in (('I', 'Q'), ('Q', 'I')):
        P, N, OP, ON, TS, VC = c + 'P', c + 'N', o + 'P', o + 'N', 'TS' + c, 'VDDC' + c
        VSS, VDD, IB, CS, VT = 'VSS', 'VDD' + sfx(c), 'IBIAS' + sfx(c), 'CMLSEL' + sfx(c), 'VTUNE' + sfx(c)
        for _ in range(2 * D['tail_f']):
            dev(f"{TS} {IB} {VSS} {VSS} nfet_03v3 w={D['tail_w']}u l=1u")
        for _ in range(D['nn']):
            dev(f"{P} {N} {TS} {VSS} nfet_03v3 w={D['wf']}u l=0.28u")
            dev(f"{N} {P} {TS} {VSS} nfet_03v3 w={D['wf']}u l=0.28u")
        gpd, gnd = (ON, OP) if c == 'I' else (OP, ON)
        for _ in range(D['ncp']):
            dev(f"{P} {gpd} {TS} {VSS} nfet_03v3 w={D['wf']}u l=0.28u")
            dev(f"{N} {gnd} {TS} {VSS} nfet_03v3 w={D['wf']}u l=0.28u")
        for _ in range(D['np']):
            dev(f"{P} {N} {VC} {VC} pfet_03v3 w={D['wf']}u l=0.28u")
            dev(f"{N} {P} {VC} {VC} pfet_03v3 w={D['wf']}u l=0.28u")
        for _ in range(D['hdr_f']):
            dev(f"{VC} {CS} {VDD} {VDD} pfet_03v3 w={D['hdr_w']}u l=0.28u")
        for _ in range(D['var_f']):
            dev(f"{P} {VT} cap_nmos_03v3_b c_width={D['var_w']}u c_length={D['var_l']}u")
            dev(f"{N} {VT} cap_nmos_03v3_b c_width={D['var_w']}u c_length={D['var_l']}u")
        for i in range(16):
            bn = assign[i]
            x, y = f'X{c}{i}', f'Y{c}{i}'
            m = D['mim']
            if bn == 'FIX':
                m = D['cfix_mim']
                y = x
            dev(f"{P} {x} cap_mim_2f0_m4m5_noshield c_width={m}u c_length={m}u")
            dev(f"{N} {y} cap_mim_2f0_m4m5_noshield c_width={m}u c_length={m}u")
            if bn == 'FIX':
                continue
            b = 'VSS' if bn == 'VSS' else bn + sfx(c)
            dev(f"{VSS} {b} {x} {VSS} nfet_03v3 w={D['sw_w']}u l=0.28u")
            dev(f"{y} {b} {VSS} {VSS} nfet_03v3 w={D['sw_w']}u l=0.28u")
            for j in range(D['sw_f']):
                dev(f"{x} {b} {y} {VSS} nfet_03v3 w={D['sw_w']}u l=0.28u")
    body = '\n'.join(lines[1:])
    nets = set()
    for ln in lines[1:]:
        nets.update(ln.split()[1:5])
    keep = sorted(n for n in nets if not n.startswith(('X', 'Y')) and '=' not in n and not n.endswith(('fet_03v3', '_b', 'noshield')))
    return lines[0] + f"\n.subckt {cell} " + ' '.join(keep) + '\n' + body + '\n.ends\n'


def lvs_rf(tag='t'):
    work = WORK / ('rf' + tag)
    ext = ['crashbackups stop', 'load pt_lc_qvco_rf', 'select top cell', 'extract all', 'ext2spice lvs',
           'ext2spice -o pt_lc_qvco_rf.lvs.spice', 'quit -noprompt']
    (work / 'ext.tcl').write_text('\n'.join(ext) + '\n')
    le.docker_magic(work, 'ext.tcl')
    (work / 'ref.spice').write_text(ref_netlist())
    r = le.netgen_lvs(work, 'pt_lc_qvco_rf.lvs.spice', 'pt_lc_qvco_rf', 'ref.spice', 'pt_lc_qvco_rf')
    print(r)
    return r


# ---------------------------------------------------------------- aux cell (layout_engine): bias, PRE taps, bleeds, ATB
AUX = 'pt_lc_qvco_aux'
AUX_PORTS = ('EN IBIAS PRE VDDB ATB_EN ATB_VTUNE ATB_ITAIL IP IN QP QN VTUNE VDDCI VDDCQ CMLSEL VDD VSS TAILG').split()
# r6 (LO owner, 2026-11-12): tail-gate RC filter.  The 10 uA / 2-1 um reference diode's flicker (fnoicor=1: 184 nV/rtHz
# at 100 kHz on the tail gates), x800 mirrored, dominated the QVCO close-in noise: L(100 kHz) -69 dBc/Hz, 1/f^3 corner
# 9-16 MHz (scratch/lo/r5_pn flick.py; Kg = df/dVg_tail = 195-353 MHz/V extracted).  TAILG = filtered tail gate:
# RFLT_N x RFLT_L-um (1 um wide, 1 kohm/sq -> 100 kohm each) ppolyf_u_1k from IBIAS + CFLT_N x CFLT_S^2 um n-well MOS cap
# (~27 pF) + ~15 pF of tail gates: pole ~1 kHz, TAILG settles to 0.5 % in 1.0 ms at ss (noise_f.py); EN-to-ready 1.5 ms.
RFLT_N, CFLT_N = 40, 12
RFLT_L, CFLT_S = 100, 24     # segment length (um; 1 um wide -> 100 kohm) and MOS-cap tile side (um)
AUX_W = 620.0      # r6: wide, short aux (it sits below the spirals' free area; was 150)


def aux_netlist():
    filt = "".join(f"XRF{k} {'IBIAS' if k == 0 else f'TF{k}'} {'TAILG' if k == RFLT_N - 1 else f'TF{k + 1}'} VSS ppolyf_u_1k r_width=1u r_length={RFLT_L}u\n" for k in range(RFLT_N))
    filt += "".join(f"XCF{k} TAILG VSS cap_nmos_03v3_b c_width={CFLT_S}u c_length={CFLT_S}u\n" for k in range(CFLT_N))
    return f"""* {AUX}: r5 QVCO aux (bias reference, PRE prescaler tap + 3 matching dummies, CMLSEL bleeds, ATB taps)
.subckt pt_t_inv1 A Y VDD VSS
XP Y A VDD VDD pfet_03v3 w=2u l=0.28u
XN Y A VSS VSS nfet_03v3 w=1u l=0.28u
.ends
.subckt pt_lc_acinv A Y ENB VDD VSS
XC A AI cap_mim_2f0_m4m5_noshield c_width=10u c_length=10u
XRF Y AI VSS ppolyf_u_1k r_width=1u r_length=50u
XN Y AI VSS VSS nfet_03v3 w=6u l=0.28u
XP Y AI VH VDD pfet_03v3 w=12u l=0.28u
XH VH ENB VDD VDD pfet_03v3 w=24u l=0.28u
XZ Y ENB VSS VSS nfet_03v3 w=1u l=0.28u
.ends
.subckt pt_lc_inv1 A Y VDD VSS
XN Y A VSS VSS nfet_03v3 w=6u l=0.28u
XP Y A VDD VDD pfet_03v3 w=12u l=0.28u
.ends
.subckt {AUX} {' '.join(AUX_PORTS)}
XEI EN ENB VDD VSS pt_t_inv1
XNB IBIAS IBIAS NBS VSS nfet_03v3 w=1.44u l=1u
XNBS NBS EN VSS VSS nfet_03v3 w=4u l=0.28u
XNBC IBIAS ENB VSS VSS nfet_03v3 w=1u l=0.28u
{filt}XNBF TAILG ENB VSS VSS nfet_03v3 w=1u l=0.28u
XBP IP PREB ENB VDDB VSS pt_lc_acinv
XBP2 PREB PRE VDDB VSS pt_lc_inv1
XBD1 IN DD1 ENB VDDB VSS pt_lc_acinv
XBD2 QP DD2 ENB VDDB VSS pt_lc_acinv
XBD3 QN DD3 ENB VDDB VSS pt_lc_acinv
XHBI VDDCI CMLSEL VSS VSS nfet_03v3 w=0.5u l=2u
XHBQ VDDCQ CMLSEL VSS VSS nfet_03v3 w=0.5u l=2u
XAI ATB_EN ATB_ENB VDD VSS pt_t_inv1
XRA VTUNE VTA VSS ppolyf_u_1k r_width=1u r_length=20u
XTN VTA ATB_EN ATB_VTUNE VSS nfet_03v3 w=2u l=0.28u
XTP VTA ATB_ENB ATB_VTUNE VDD pfet_03v3 w=4u l=0.28u
XRT ITR TAILG VSS VSS nfet_03v3 w=25u l=1u
XTS ITR ATB_EN ATB_ITAIL VSS nfet_03v3 w=4u l=0.28u
.ends
"""


def aux(tag=''):
    import netlist
    import timing_flow as tf
    work = WORK / ('aux' + tag)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    src = work / 'aux.spice'
    src.write_text(aux_netlist())
    ports, devices = netlist.load(src, AUX)
    rep = le.generate(work, AUX, ports, devices, max_row_width=AUX_W)
    (work / 'schematic.spice').write_text(tf.with_antenna_diodes(netlist.flat_spice(ports, devices, AUX), rep))
    lvs = le.netgen_lvs(work, f'{AUX}.lvs.spice', AUX, 'schematic.spice', AUX)
    out = dict(size_um=rep['size_um'], drc=rep['drc_count_raw'][:200], lvs=lvs, trunk_x=rep['trunk_x'], straps=rep['straps'])
    (work / 'result.json').write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str)[:1500])
    return out


# ---------------------------------------------------------------- core top: RF cell + aux + gap router
TOP = 'pt_lc_qvco5_core'
TOP_PORTS = ('EN CMLSEL VTUNE IBIAS BAND0 BAND1 BAND2 BAND3 PRE IP IN QP QN VDD VDDB VSS ATB_EN ATB_VTUNE ATB_ITAIL').split()
AUX_X = 6.0


def rf_points():
    """RF-cell bottom pins (global x at y = -2.0): net -> list of (x, layer, width)."""
    pts = {}
    def add(net, x, lay, w):
        pts.setdefault(net, []).append((x, lay, w))
    for core in ('I', 'Q'):
        gx = (lambda x: x) if core == 'I' else (lambda x: OXQ - x)
        for k, (x, w) in STRAPS.items():
            net = {'VT': 'VTUNE', 'TS': None, 'VDDC': 'VDDC' + core, 'IBIAS': 'TAILG'}.get(k, k)
            if net:
                add(net, gx(x), 4, w)
        for k, b in enumerate(('B0', 'B1', 'B2', 'B3')):
            add('BAND%d' % k, gx(0.8 * (k + 1)), 3, 0.4)
    return pts


def top(rftag='t3', auxtag='a1', tag=''):
    import timing_flow as tf
    work = WORK / ('top' + tag)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    rfw, axw = WORK / ('rf' + rftag), WORK / ('aux' + auxtag)
    for f in list(rfw.glob('*.mag')) + list(axw.glob('*.mag')):
        if 'flat' in f.name or '_fc' in f.name:
            continue
        shutil.copy(f, work / f.name)
    info = json.loads((rfw / 'info.json').read_text())
    ax = json.loads((axw / 'result.json').read_text())
    aw, ah = ax['size_um']
    global AUX_X
    AUX_X = round(80.0 - aw / 2, 1) if aw > 200 else 6.0   # r6: centre a wide aux under the core
    # tank taps to the aux PRE inputs: extend the outer P strap and the outer N strap of each core to y = -2
    L = XF()
    L.auto_port = False
    for core, tap in (('I', ('IP', 'IN')), ('Q', ('QP', 'QN'))):
        bus = info[core]['bus']
        for net in tap:
            x = bus[net][0]
            gxx = x if core == 'I' else OXQ - x
            L.rect('metal4', gxx - 0.8, -2.0, gxx + 0.8, info[core]['rows']['N'] + 1.0)
    pts = rf_points()
    for core, tap in (('I', ('IP', 'IN')), ('Q', ('QP', 'QN'))):
        bus = info[core]['bus']
        for net in tap:
            x = bus[net][0]
            pts.setdefault(net, []).append((x if core == 'I' else OXQ - x, 4, 1.6))
    # aux pins (M5 trunk tops / straps), global
    nets_aux = {n: x for n, x in ax['trunk_x'].items() if n in AUX_PORTS}
    pw = {'VDD': [x for n, x in ax['straps'] if n == 'VDD'], 'VSS': [x for n, x in ax['straps'] if n == 'VSS']}
    # tracks
    order = ['VSS', 'VDD', 'VTUNE', 'TAILG', 'CMLSEL', 'VDDCI', 'VDDCQ', 'IP', 'IN', 'QP', 'QN']
    widths = {'VSS': 2.0, 'VDD': 2.0, 'VDDCI': 0.8, 'VDDCQ': 0.8}
    y = -3.0
    ytr = {}
    for n in ['BAND0', 'BAND1', 'BAND2', 'BAND3']:       # M2 tracks for the band lines (M3 verticals)
        ytr[n] = y
        y -= 0.9
    y -= 0.6
    for n in order:
        w = widths.get(n, 0.6)
        y -= w / 2
        ytr[n] = y
        y -= w / 2 + 0.6
    aux_top = y - 3.0
    ay = aux_top - ah
    L.cmds += [f'getcell pt_lc_qvco_rf child 0 0 parent 0 0', f'getcell {AUX} child 0 0 parent {AUX_X} {R.s(ay)}']
    def m5v(x, y1, y2, w):
        L.rect('metal5', x - max(w, 0.5) / 2, min(y1, y2), x + max(w, 0.5) / 2, max(y1, y2))
    for n in ['BAND0', 'BAND1', 'BAND2', 'BAND3']:
        xs = [x for x, lay, w in pts[n]]
        yt = ytr[n]
        L.rect('metal2', min(xs) - 0.2, yt - 0.2, max(xs) + 0.2, yt + 0.2)
        for x in xs:
            L.rect('metal3', x - 0.2, yt - 0.2, x + 0.2, -1.8)
            L.rect('via2', x - 0.14, yt - 0.14, x + 0.14, yt + 0.14)
        L.label(n, 'metal2', min(xs), yt, TOP_PORTS.index(n) + 1)
    for n in order:
        w = widths.get(n, 0.6)
        yt = ytr[n]
        xs = []
        for x, lay, pwid in pts.get(n, []):
            vw = 1.6 if n in ('IP', 'IN', 'QP', 'QN') else 0.8 if n in ('VDD', 'VSS') else 0.5
            # RF strap end (M4) -> via4 -> M5 down to the track
            L.rect('metal5', x - vw / 2, yt - w / 2, x + vw / 2, -1.6)
            L.rect('metal4', x - vw / 2, -2.6, x + vw / 2, -1.6)
            L.varea(4, x - vw / 2 + 0.07, -2.53, x + vw / 2 - 0.07, -1.67)
            L.varea(4, x - vw / 2 + 0.07, yt - w / 2 + 0.07, x + vw / 2 - 0.07, yt + w / 2 - 0.07)
            xs.append(x)
        ap = [nets_aux[n] + AUX_X] if n in nets_aux else []
        if n in pw:
            ap = [x + AUX_X for x in pw[n]]
        if n in ('VDDCI', 'VDDCQ', 'IP', 'IN', 'QP', 'QN', 'VTUNE', 'TAILG', 'CMLSEL', 'VDD', 'VSS'):
            for x in ap:
                vw = 2.0 if n in ('VDD', 'VSS') else 0.5
                L.rect('metal5', x - vw / 2, aux_top - 1.0, x + vw / 2, yt + w / 2)
                L.varea(4, x - vw / 2 + 0.07, yt - w / 2 + 0.07, x + vw / 2 - 0.07, yt + w / 2 - 0.07)
                xs.append(x)
        if n in ('IP', 'IN', 'QP', 'QN'):
            # equal track length on all four tank taps (I/Q load match): union of the four spans
            allx = [x for m in ('IP', 'IN', 'QP', 'QN') for x, _, _ in pts.get(m, [])] + \
                   [nets_aux[m] + AUX_X for m in ('IP', 'IN', 'QP', 'QN') if m in nets_aux]
            xs = xs + [min(allx), max(allx)]
        L.rect('metal4', min(xs) - 1.2, yt - w / 2, max(xs) + 1.2, yt + w / 2)
        L.label(n, 'metal4', min(xs), yt, TOP_PORTS.index(n) + 1 if n in TOP_PORTS else None)
    # aux-only ports: M5 stubs below... label on the aux trunk tops (already M5 labels inside aux) -> top labels
    for n in ('EN', 'IBIAS', 'PRE', 'VDDB', 'ATB_EN', 'ATB_VTUNE', 'ATB_ITAIL'):
        x = nets_aux[n] + AUX_X
        L.rect('metal5', x - 0.25, aux_top - 1.0, x + 0.25, aux_top + 1.0)
        L.label(n, 'metal5', x, aux_top + 0.5, TOP_PORTS.index(n) + 1)
    (work / 'layout.tcl').write_text(R.magic_script(TOP, L.cmds))
    le.docker_magic(work, 'layout.tcl')
    (work / 'drc.tcl').write_text(R.drc_script(TOP))
    le.docker_magic(work, 'drc.tcl')
    drc = (work / 'drc-count.txt').read_text()
    ext = ['crashbackups stop', f'load {TOP}', 'select top cell', 'extract all', 'ext2spice lvs',
           f'ext2spice -o {TOP}.lvs.spice', 'quit -noprompt']
    (work / 'ext.tcl').write_text('\n'.join(ext) + '\n')
    le.docker_magic(work, 'ext.tcl')
    (work / 'ref.spice').write_text(top_ref(axw))
    lvs = le.netgen_lvs(work, f'{TOP}.lvs.spice', TOP, 'ref.spice', TOP)
    res = dict(rftag=rftag, drc=drc[:600], lvs=lvs, aux_y=ay, aux_top=aux_top, tracks=ytr, height=info['I']['bank']['top'] + 6.0 - ay)
    (work / 'result.json').write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str)[:2500])
    return res


def top_ref(axw):
    rf = ref_netlist(split=False)
    body = [ln for ln in rf.splitlines() if ln.startswith('X')]
    ren = {'B0': 'BAND0', 'B1': 'BAND1', 'B2': 'BAND2', 'B3': 'BAND3', 'IBIAS': 'TAILG'}
    out = []
    for ln in body:
        tok = ln.split()
        tok = [ren.get(x, x) for x in tok]
        out.append(' '.join(tok))
    sch = (Path(axw) / 'schematic.spice').read_text().splitlines()
    for ln in sch:
        if ln.startswith(('X', 'D')):
            tok = ln.split()
            nets = []
            for x in tok[1:]:
                if '=' in x or x.endswith(('fet_03v3', 'noshield', 'ppolyf_u_1k', 'diode_nd2ps_03v3', '_b')):
                    nets.append(x)
                elif x in AUX_PORTS:
                    nets.append(x)
                else:
                    nets.append('aux_' + x.replace('.', '_'))
            out.append(tok[0] + 'A ' + ' '.join(nets))
    return f".subckt {TOP} {' '.join(TOP_PORTS)}\n" + '\n'.join(out) + '\n.ends\n'


# ---------------------------------------------------------------- assembly: core top + two spirals (DRC; LVS is the core)
ASM = 'pt_lc_qvco5'
AUXTAG_PUBLISHED = 'f5'        # aux build of the published r6b top (top7); top() does not record it
SPIRAL_GAP = 8.0


def asm(coretag='2', tag=''):
    import timing_flow as tf
    work = WORK / ('asm' + tag)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    cw = WORK / ('top' + coretag)
    for f in cw.glob('*.mag'):
        shutil.copy(f, work / f.name)
    shutil.copy(tf.GENERATED / 'lcvco' / 'pt_spiral_ind.mag', work / 'pt_spiral_ind.mag')
    res = json.loads((cw / 'result.json').read_text())
    rftag = res.get('rftag')
    info = json.loads((WORK / ('rf' + rftag) / 'info.json').read_text())
    L = XF()
    L.cmds += [f'getcell {TOP} child 0 0 parent 0 0']
    feeds = {}
    for core, (ox, sx) in (('I', (0.0, 1)), ('Q', (OXQ, -1))):
        L.ox, L.sx = ox, sx
        d = info[core]
        P, N = core + 'P', core + 'N'
        nj = d['njoin']
        sy = (nj[0] + nj[1]) / 2
        sxp = -(186.0 + SPIRAL_GAP)                       # spiral origin, local x (rotated: x' = -y)
        gx = ox + sx * sxp
        L.cmds += [f'getcell pt_spiral_ind {"270" if sx > 0 else "90v"} child 0 0 parent {R.s(gx)} {R.s(sy)}']
        xa, ya = sxp + 137.5, sy - 157.5                   # A (outer turn) -> P1 bus
        xb, yb = sxp + 170.0, sy                           # B (centre underpass) -> N join
        p1 = min(d['bus'][P])
        L.rect('metal5', xa - 5.0, ya - 5.0, p1, ya + 5.0)
        L.rect('metal5', xb - 4.0, nj[0], min(d['bus'][N]), nj[1])
        feeds[core] = dict(A=[ox + sx * xa, ya], B=[ox + sx * xb, yb], A_len_um=p1 - xa, B_len_um=min(d['bus'][N]) - xb)
    # r7 (SG-5): top-level port labels = the core's port labels, same place and port index
    L.ox, L.sx = 0.0, 1
    for net, layer, x, y, port in core_ports(cw / f'{TOP}.mag'):
        L.label(net, layer, x, y, port)
    (work / 'layout.tcl').write_text(R.magic_script(ASM, L.cmds))
    le.docker_magic(work, 'layout.tcl')
    (work / 'drc.tcl').write_text(R.drc_script(ASM))
    le.docker_magic(work, 'drc.tcl')
    tf.gds_export_analog(work, ASM)
    axw = WORK / ('aux' + json.loads((cw / 'result.json').read_text()).get('auxtag', AUXTAG_PUBLISHED))
    ax = json.loads((axw / 'result.json').read_text())
    aux_x = round(80.0 - ax['size_um'][0] / 2, 1) if ax['size_um'][0] > 200 else 6.0     # as top()
    marks = fill_markers(work, tankx=[ax['trunk_x'][n] + aux_x for n in ('IP', 'IN', 'QP', 'QN') if n in ax['trunk_x']],
                         stubs=[feeds[c]['A'] for c in feeds])          # r7 (SG-3): IND_MK / NDMY / PMNDMY written into the exported GDS
    kl = tf.klayout_drc(work, ASM)
    drc = (work / 'drc-count.txt').read_text()
    out = dict(magic_drc=drc[:400], klayout=kl, feeds=feeds, fill_markers=marks)
    (work / 'result.json').write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str)[:2000])
    return out


def core_ports(mag):
    """(net, layer, x um, y um, port index) of every port label of the core top .mag (magscale 1 10: 200 units/um)."""
    import re
    out = []
    lines = Path(mag).read_text().splitlines()
    for i, ln in enumerate(lines):
        m = re.match(r'flabel (\S+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) .* (\S+)$', ln)
        if m and i + 1 < len(lines) and lines[i + 1].startswith('port '):
            layer = {'via2': 'metal2', 'via4': 'metal4'}.get(m.group(1), m.group(1))
            x = (int(m.group(2)) + int(m.group(4))) / 400.0
            y = (int(m.group(3)) + int(m.group(5))) / 400.0
            out.append((m.group(6), layer, x, y, int(lines[i + 1].split()[1])))
    return out


KEEPOUT_UM = 25.0     # AP4-5b rule: one turn width from the outer-turn metal
SPIRAL_STUB_UM = 20.0  # pt_spiral_ind bbox extends this far past the outer turn on the feed side (feed stub only)
MARK_SCRIPT = """import klayout.db as db, json
ly = db.Layout(); ly.read('/work/%(gds)s'); top = ly.cell('%(cell)s'); dbu = ly.dbu
bb = top.bbox(); reg = db.Region(); rec = {}
for inst in top.each_inst():
    if inst.cell.name == 'pt_spiral_ind':
        b = inst.bbox()
        b = db.Box(b.left, b.bottom + int(%(stub)s / dbu), b.right, b.top)     # outer-turn metal (the bbox reaches lower only at the feed stub)
        b = b.enlarged(int(%(halo)s / dbu), int(%(halo)s / dbu))     # NOT clipped: the halo beyond the old outline is part of the cell (review asm8 gap 1)
        b = db.Box(b.left, max(b.bottom, bb.bottom), b.right, b.top)
        reg.insert(b); rec.setdefault('spiral_um', []).append([b.left * dbu, b.bottom * dbu, b.right * dbu, b.top * dbu])
def find(cell, tr, name):
    for inst in cell.each_inst():
        t = tr * inst.trans
        if inst.cell.name == name:
            return inst.cell.bbox().transformed(t)
        r = find(inst.cell, t, name)
        if r is not None:
            return r
rf = find(top, db.Trans(), 'pt_lc_qvco_rf')
aux = find(top, db.Trans(), 'pt_lc_qvco_aux')
# tank core: the RF cell and the tank-track channel between it and the aux block (not the aux block itself)
b = db.Box(rf.left, aux.top, rf.right, rf.top) & bb
reg.insert(b); rec['core_um'] = [b.left * dbu, b.bottom * dbu, b.right * dbu, b.top * dbu]
b = db.Box(min(rf.left, aux.left), aux.top, max(rf.right, aux.right), rf.bottom) & bb      # tank-track channel, full width
reg.insert(b); rec['channel_um'] = [b.left * dbu, b.bottom * dbu, b.right * dbu, b.top * dbu]
for x, y in %(stubs)s:                   # feed stubs of the outer turn (below the outer-turn edge): +-45 um, 25 um below the stub end
    b = db.Box(int((x - 45.0) / dbu), int((y - %(stub)s - %(halo)s - 15.0) / dbu), int((x + 45.0) / dbu), int(y / dbu))
    reg.insert(b); rec.setdefault('stub_um', []).append([b.left * dbu, b.bottom * dbu, b.right * dbu, b.top * dbu])
for x in %(tankx)s:                      # tank-net trunks inside the aux block (PRE taps): +-6 um columns (review asm8 gap 2)
    x = round(x, 1)
    b = db.Box(int(round((x - 6.0) / dbu / 10)) * 10, aux.bottom, int(round((x + 6.0) / dbu / 10)) * 10, aux.top)
    reg.insert(b); rec.setdefault('aux_tank_columns_um', []).append([b.left * dbu, b.bottom * dbu, b.right * dbu, b.top * dbu])
reg.merge()
for l in ((151, 5), (152, 5)):          # IND_MK (no dummy COMP/Poly2; exempts DCF.1a), PMNDMY (no dummy metal).  No NDMY: DE.3 limits it to 15000 um2
    top.shapes(ly.layer(*l)).insert(reg)
nb = top.bbox(); rec['bbox_um'] = [nb.left * dbu, nb.bottom * dbu, nb.right * dbu, nb.top * dbu]; rec['bbox_before_um'] = [bb.left * dbu, bb.bottom * dbu, bb.right * dbu, bb.top * dbu]
ly.write('/work/%(gds)s')
rec.update(area_mm2=reg.area() * dbu * dbu / 1e6, layers=['IND_MK 151/5', 'PMNDMY 152/5'], halo_um=%(halo)s, clipped_to_cell_bbox=False)
open('/work/markers.json', 'w').write(json.dumps(rec, indent=1))
"""


def fill_markers(work, cell=ASM, tankx=(), stubs=()):
    """Fill keep-out markers over both spirals (+ KEEPOUT_UM, clipped to the cell outline) and the tank core
    (RF cell + tank-track channel).  The aux block and the two empty corners stay fillable."""
    import subprocess
    import timing_flow as tf
    work = Path(work)
    (work / 'mark.py').write_text(MARK_SCRIPT % dict(gds=f'{cell}.a.gds', cell=cell, halo=KEEPOUT_UM, stub=SPIRAL_STUB_UM, tankx=list(tankx), stubs=[list(p) for p in stubs]))
    cmd = ['docker', 'run', '--rm', '--network', 'none', '--cpus', '1', '--memory', '8g', '--user', '%d:%d' % (__import__('os').getuid(), __import__('os').getgid()),
           '-e', 'HOME=/tmp', '--entrypoint', '/bin/bash', '-v', f'{work}:/work', '-w', '/work', tf.ANALOG_IMAGE,
           '-c', 'export PATH=$PATH:/foss/tools/klayout LD_LIBRARY_PATH=/foss/tools/klayout; klayout -b -r /work/mark.py > mark.log 2>&1']
    subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    return json.loads((work / 'markers.json').read_text())


def lvs_ref(coreref, main=('IN', 'QN')):
    """LVS reference of the pt_lc_qvco5 top: the core plus the two spirals as DOCUMENTED SHORTS (a drawn inductor
    is metal: it joins its two terminals).  The simulation netlist is qvco5.spice (spiral = pt_spiral model).
    In the layout IP-IN (QP-QN) is one net carrying two port labels; Magic keeps one name on the net (`main`) and
    ties the other label to it with a 0 V source, which asm_lvs rewrites as a 1 mohm resistor.  The reference is
    written the same way: the core sees the `main` name on both tank pins, the other port hangs on the resistor."""
    core = Path(coreref).read_text()
    alias = {'IP': main[0], 'IN': main[0], 'QP': main[1], 'QN': main[1]}
    other = [({'IP', 'IN'} - {main[0]}).pop(), ({'QP', 'QN'} - {main[1]}).pop()]
    return (core + f"""
* LVS view of the top (spirals = metal shorts IP-IN and QP-QN; simulation view: qvco5.spice with pt_spiral)
.subckt {ASM} {' '.join(TOP_PORTS)}
XCORE {' '.join(alias.get(p, p) for p in TOP_PORTS)} {TOP}
RLI {other[0]} {main[0]} 1m
RLQ {other[1]} {main[1]} 1m
.ends
""")


def asm_lvs(tag=''):
    """Read-back LVS of the assembled top: GDS read from disk into an empty Magic session, extracted with shorted
    ports kept apart by 0 V sources (ext2spice short voltage), netgen against lvs_ref()."""
    work = WORK / ('asm' + tag)
    res = json.loads((work / 'result.json').read_text())
    rb = work / 'readback'
    if rb.exists():
        shutil.rmtree(rb)
    rb.mkdir()
    shutil.copy(work / f'{ASM}.a.gds', rb / f'{ASM}.gds')
    (rb / 'rb.tcl').write_text('\n'.join([
        'crashbackups stop', 'gds flatglob *$$*', 'gds noduplicates true', f'gds read {ASM}.gds', f'load {ASM}',
        # flat extraction: the IP-IN / QP-QN shorts through the spirals become shorts between top-level port labels,
        # which `ext2spice short voltage` writes as 0 V sources (a hierarchical extraction silently drops IN and QN)
        f'flatten {ASM}_rb', f'load {ASM}_rb',
        'select top cell', 'extract do aliases', 'extract all', 'ext2spice lvs', 'ext2spice short voltage', f'ext2spice -o {ASM}.rb.spice', 'quit -noprompt']) + '\n')
    le.docker_magic(rb, 'rb.tcl')
    cw = None
    for t in WORK.glob('top*'):
        if (t / 'ref.spice').exists() and (work / f'{TOP}.mag').read_text() == (t / f'{TOP}.mag').read_text():
            cw = t
    import re
    t = (rb / f'{ASM}.rb.spice').read_text()
    shorts = re.findall(r'^V\d+ (\S+) (\S+) 0\.0$', t, re.M)
    t = re.sub(r'^V(\d+) (\S+) (\S+) 0\.0$', r'RSH\1 \2 \3 1m', t, flags=re.M)
    (rb / f'{ASM}.rbr.spice').write_text(t)         # Magic's own file is root-owned
    cnt = lambda n: len(re.findall(rf'(?<=\s){n}(?=\s)', t))
    main = (max(('IP', 'IN'), key=cnt), max(('QP', 'QN'), key=cnt))
    (rb / 'ref.spice').write_text(lvs_ref(cw / 'ref.spice', main))
    lvs = le.netgen_lvs(rb, f'{ASM}.rbr.spice', ASM + '_rb', 'ref.spice', ASM)
    lvs['port_shorts_found_by_magic'] = sorted(sorted(x) for x in shorts)
    lvs['unique_match'] = bool(lvs['unique_match'] and lvs['port_shorts_found_by_magic'] == [['IN', 'IP'], ['QN', 'QP']])
    # second check, same GDS: hierarchical extraction, the core cell against its reference with FOUR separate tank pins
    # (the top check above cannot see a P/N swap: it asserts IP = IN and QP = QN)
    (rb / 'rbh.tcl').write_text('\n'.join([
        'crashbackups stop', 'gds flatglob *$$*', 'gds noduplicates true', f'gds read {ASM}.gds', f'load {ASM}', 'select top cell',
        'extract all', 'ext2spice lvs', f'ext2spice -o {ASM}.rbh.spice', 'quit -noprompt']) + '\n')
    le.docker_magic(rb, 'rbh.tcl')
    (rb / 'coreref.spice').write_text((cw / 'ref.spice').read_text())
    core = le.netgen_lvs(rb, f'{ASM}.rbh.spice', TOP, 'coreref.spice', TOP, out='lvs_core.txt')
    res['readback_lvs'] = dict(lvs, core_ref=str(cw / 'ref.spice'), core_lvs=core,
                               note='reference = the core LVS netlist (top<n>/ref.spice: qvco5.spice core + antenna diodes), not qvco5.spice itself')
    res['readback_lvs']['unique_match'] = bool(lvs['unique_match'] and core['unique_match'])
    (work / 'result.json').write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res['readback_lvs'], indent=1)[:1500])
    return res


def schematic():
    """qvco5.spice: schematic of record for pt_lc_qvco5 = the LVS reference of pt_lc_qvco5_core (RF strips + bank +
    aux, generated from the same parameters as the layout) + the two tank spirals (spiral.spice pt_spiral)."""
    rf = ref_netlist(split=False)
    body = [ln for ln in rf.splitlines() if ln.startswith('X')]
    ren = {'B0': 'BAND0', 'B1': 'BAND1', 'B2': 'BAND2', 'B3': 'BAND3', 'IBIAS': 'TAILG'}
    body = [' '.join(ren.get(x, x) for x in ln.split()) for ln in body]
    txt = f"""* SPDX-License-Identifier: Apache-2.0
* pt_lc_qvco5: autonomous RF LO quadrature LC VCO, r5 (LO owner, 2026-11-11).  GENERATED by
* lcvco/qvco_rf_layout.py schematic -- edit the generator, not this file.
* r5 vs r3 (qvco.spice): sized against the pessimistic tank (ss/32/3.15, L+10 % low Q, +3 ohm per MIM/varactor
* branch, +15 % parasitic C, explicit gate R) on the EXTRACTED hand-placed RF layout; NMOS pair 24x5 um, PMOS
* 32x5 um, coupling 8x5 um per side, tail 12 mA per core (r6; 1600/1 vs 1.44/1 reference, was 8 mA), no fixed MIM, band bank of
* 15 unit cells (8.4 um MIM pair + 5x5 um switch + 2 pull-downs) per core, bit k = 2^k cells, one always-off
* dummy cell; varactor 17 x 10/1 um fingers per side; PMOS header per core on CMLSEL (1 = core off, LO11 external
* LO through the passive tank) with a weak bleed; ATB: VTUNE tap (20 k + TG) and a 1/64 tail replica current.
* r6 (2026-11-12): tail gates on TAILG = IBIAS diode through {RFLT_N} x {RFLT_L} kohm ppolyf + {CFLT_N} x {CFLT_S}x{CFLT_S} um n-well MOS cap
* (bias-flicker filter, pole ~1 kHz; TAILG within 0.5 % in 1.0 ms at ss -> EN-to-ready 1.5 ms).  Ports unchanged.
.subckt pt_lc_qvco5 {' '.join(TOP_PORTS)}
XCORE {' '.join(TOP_PORTS)} {TOP}
XLI IP IN VSS pt_spiral
XLQ QP QN VSS pt_spiral
.ends
.subckt {TOP} {' '.join(TOP_PORTS)}
""" + '\n'.join(body) + f"""
XAUX EN IBIAS PRE VDDB ATB_EN ATB_VTUNE ATB_ITAIL IP IN QP QN VTUNE VDDCI VDDCQ CMLSEL VDD VSS TAILG {AUX}
.ends
""" + aux_netlist()
    (HERE / 'qvco5.spice').write_text(txt)
    print('wrote', HERE / 'qvco5.spice', len(body), 'RF devices')


if __name__ == '__main__':
    if sys.argv[1] == 'rf':
        build(sys.argv[2] if len(sys.argv) > 2 else '')
    elif sys.argv[1] == 'schematic':
        schematic()
    elif sys.argv[1] == 'asm':
        asm(*sys.argv[2:])
    elif sys.argv[1] == 'asmlvs':
        asm_lvs(*sys.argv[2:])
    elif sys.argv[1] == 'top':
        top(*sys.argv[2:])
    elif sys.argv[1] == 'aux':
        aux(sys.argv[2] if len(sys.argv) > 2 else '')
    elif sys.argv[1] == 'lvs':
        lvs_rf(sys.argv[2] if len(sys.argv) > 2 else 't')

