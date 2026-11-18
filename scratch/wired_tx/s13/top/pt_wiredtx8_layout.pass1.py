"""pt_wiredtx8 block top layout generator (schematic = wtx8_top.top() / wtx8_top.netlist()).  NOT published.

    python3 pt_wiredtx8_layout.py            # build, GDS, checks on the GDS read back, netlists -> scratch/wired_tx/s13/top
    python3 pt_wiredtx8_layout.py build      # layout + DRC / LVS in the build directory only

Children (not rebuilt here): wtx_ser8d (generated/fast), wtx_mux8 (wtx_mux8_layout.py), wtx8_aux (wtx8_aux_layout.py).

    +--------------------------------------------- pad edge -------------------------------------------------+
    | VSS VDD |  decap rows  | aux |               wtx_mux8 (outputs on the top edge)      |  keep-free | VDD VSS |
    | bars    |              | side|                                                       |            | bars    |
    |---------+--------------+-----+-------------------------------------------------------+------------+---------|
    |  seam:  T  Metal4 supply rails (VDD above VSS) over the Metal2 tracks of the nets that only have pins above        |
    |         M  phase nets, pin -> mux: two Metal4 tracks per net (out and back: equal resistance), VSS track between nets|
    |            the eight phase pins (Metal5 pads in a row)                                                              |
    |         S  phase nets, pin -> ser8d: one Metal4 track per net, all of the same length (dummy ends), VSS between     |
    |         B  Metal4 tracks of the nets with a ser8d pin (D, F, SERQ, word clock)                                       |
    +---------------------------------------------------------------------------------------------------------------------+
    |                                         wtx_ser8d (all pins on its top edge)                                        |
    +---------------------------------------------------------------------------------------------------------------------+

Vertical wiring in the seam: Metal3 from pins above (mux / aux bottom edge), Metal5 from ser8d pins below; so a wire from
above never meets one from below.  ser8d's Metal5 supply straps run up through the seam into the rails (and, left of the
aux cell, on through the decap rows); the mux's VSS straps come down as 2.5 um necks placed clear of them.
Signal pins: Metal2 / Metal4 track ends on the left / right block edge at seam height; PH0..7: Metal5 pads in the seam;
MAIN / POST: the mux's Metal5 risers on the top edge; TAP_P / TAP_N: Metal4 on the left edge near the top; supplies: Metal5
bars on the left and right edges above ser8d.
"""
import json
import re
import shutil
import sys
from pathlib import Path

import tools
import wtx8_top as T
import wtx_mux8 as mux8
import wtx_mux8_layout as L
import wtx8_aux_layout as AX
from wtx_mux8_layout import G, Geo, RAIL_W, XRow, s

NAME = T.NAME
WORK = tools.SCRATCH / 's13' / 'top'
OUT = WORK / 'out'
FAST = L.FAST
RS, RS5 = 0.09, 0.04                 # ohm / square, Metal1-4 / Metal5 (Magic tech file)
P4, P2, PS, PM = 0.84, 0.72, 1.0, 0.9          # track pitches: zone B (Metal4), zone T (Metal2), zone S, zone M
RAIL_VSS, RAIL_VDD = 25.0, 10.0      # Metal4 supply rails in zone T
BAR = 12.0                           # Metal5 edge bars
HSTRAP = 7.5                         # Metal5 strap from a VDD bar to a header rail of the mux
NECK = 2.5                           # mux VSS strap in zone T
PH_X0, PH_PITCH = 412.0, 4.0         # phase pin row (between two ser8d strap pairs)
I_BANK, I_LOGIC = 26.0, 30.0         # mA: per bank; ser8d + logic
SER = json.loads((FAST / 'wtx_ser8d.pins.json').read_text())


def conn():
    """{cell: {port: top net}} from wtx8_top.top()."""
    ports = {'wtx_ser8d': SER['ports'], 'wtx_mux8': mux8.PORTS, 'wtx8_aux': T.AUX_PORTS}
    m = {}
    for l in T.top().splitlines():
        tk = l.split()
        if tk and tk[0][0] == 'X' and tk[-1] in ports:
            m[tk[-1]] = dict(zip(ports[tk[-1]], tk[1:-1]))
    return m


def pack(spans, gap=1.0):
    """left-edge track assignment: {net: (lo, hi)} -> {net: track}."""
    ends, out = [], {}
    for n, (lo, hi) in sorted(spans.items(), key=lambda kv: kv[1]):
        for i, e in enumerate(ends):
            if lo - gap >= e:
                ends[i], out[n] = hi, i
                break
        else:
            ends.append(hi)
            out[n] = len(ends) - 1
    return out


def set_decap(n):
    """write the finger count the layout holds into wtx8_top.DECAP (the schematic's decap instance)."""
    p = Path(T.__file__)
    t = p.read_text()
    t2 = re.sub(r"(DECAP = dict\(w=[\d.]+, l=[\d.]+, n=)\d+\)", rf"\g<1>{n})", t)
    if t2 != t:
        p.write_text(t2)
    T.DECAP['n'] = n


def build(work=None, neg=None, bare=False):
    """bare: the top-level wiring alone, without the three children (for the wiring-C table of the phase / stream nets)."""
    work = Path(work or WORK / 'build')
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    for d in (FAST / 'wtx_ser8d_mag', L.WORK / 'build', AX.WORK / 'build'):
        for f in d.glob('*.mag'):
            shutil.copy(f, work / f.name)
    MR = json.loads((L.OUT / 'report.json').read_text())
    AR = json.loads((AX.OUT / 'report.json').read_text())
    cn = conn()
    Wb, Y0 = SER['bbox'][2], SER['bbox'][3]
    ypin_s = SER['pins']['PH0'][1]
    xa0 = AR['head']['mux_origin_in_cell_x']                       # mux origin from the aux rows' origin
    mux_ph = [MR['pins'][f'PH{k}'][0][1] for k in range(8)]
    XM = s(round((PH_X0 + 3.5 * PH_PITCH - 20.0 - sum(mux_ph) / 8) / 0.05) * 0.05)       # mux a little left of the pin row
    XA = s(XM - xa0)
    aux_w = AR['size_um'][0]
    g, inst, notes = Geo(), [], []
    # ------------------------------------------------------------------ terminals
    top_t, bot_t = {}, {}                  # net -> x of pins above (Metal3) / below (Metal5)
    for port, net in cn['wtx_ser8d'].items():
        if port not in ('VDD', 'VSS'):
            bot_t.setdefault(net, []).append(SER['pins'][port][0])
    for port, net in cn['wtx_mux8'].items():
        for layer, x, y in MR['pins'][port]:
            if layer == 'metal3' and y < 1.0:
                top_t.setdefault(net, []).append(s(XM + x))
    for port, net in cn['wtx8_aux'].items():
        if port in AR['pins'] and AR['pins'][port][2] < 1.0:
            top_t.setdefault(net, []).append(s(XA - 1.9 + AR['pins'][port][1]))
    if neg:                                # negative controls: swap terminals in the LAYOUT (LVS must fail)
        neg(top_t, bot_t)
    ph = [f'PH{k}' for k in range(8)]
    special = set(ph) | {'MAIN_P', 'MAIN_N', 'POST_P', 'POST_N', 'TAP_P', 'TAP_N', 'VDD', 'VSS'}
    exits = {n: ('L' if sum(top_t.get(n, []) + bot_t.get(n, [])) / len(top_t.get(n, []) + bot_t.get(n, [])) < Wb / 2 else 'R')
             for n in T.PORTS if n not in special}
    span = lambda n: (0.3 if exits.get(n) == 'L' else min(top_t.get(n, []) + bot_t.get(n, [])) - 0.3,
                      Wb - 0.3 if exits.get(n) == 'R' else max(top_t.get(n, []) + bot_t.get(n, [])) + 0.3)
    netsB = {n: span(n) for n in bot_t if n not in special}
    netsT = {n: span(n) for n in top_t if n not in special and n not in bot_t}
    tB, tT = pack(netsB), pack(netsT)
    nB, nT = max(tB.values()) + 1, max(tT.values()) + 1
    # ------------------------------------------------------------------ zones (y)
    yB0 = s(Y0 + 2.4)
    yS0 = s(yB0 + nB * P4 + 1.2)                           # shields at yS0 + 2 j PS, PH k at yS0 + (2 k + 1) PS
    ypin = s(yS0 + 17 * PS + 1.4)
    yM0 = s(ypin + 2.2)                                    # shield, A0, shield, B0, shield, A1, ...: every leg between two VSS tracks
    yT0 = s(yM0 + 33 * PM + 1.0)
    hT = max(RAIL_VSS + 1.0 + RAIL_VDD, nT * P2 + 0.6)
    yvs, yvd = yT0, s(yT0 + hT - RAIL_VDD)                 # lower edges of the VSS rail (below) and the VDD rail
    Ym = s(yT0 + hT + 1.6)                                 # mux / aux bottom edge
    Yt = s(Ym + MR['size_um'][1])
    inst += [] if bare else ['getcell wtx_ser8d child 0 0 parent 0 0', 'identify XSER', f'getcell wtx_mux8 child 0 0 parent {XM} {Ym}', 'identify XMUX',
             f'getcell wtx8_aux child 0 0 parent {XA} {Ym}', 'identify XAUX']
    m3 = []                                # (x, y1, y2, net) Metal3 verticals in the seam, for the clearance check

    def down(x, y, net, lo):               # Metal3 from a pin above to its track
        g.rect('metal3', x - 0.2, y - 0.2, x + 0.2, Ym + 0.4)
        g.via(x, y, lo, 3) if lo == 2 else g.via(x, y, 3, 4)
        m3.append((x, y, Ym, net))

    def up(x, y):                          # Metal5 from a ser8d pin to its track
        g.rect('metal5', x - 0.22, ypin_s - 0.22, x + 0.22, y + 0.22)
        g.via(x, y, 4, 5)
    pins = {}
    for n, (lo, hi) in netsB.items():
        y = s(yB0 + tB[n] * P4)
        g.rect('metal4', lo - 0.1, y - 0.2, hi + 0.1, y + 0.2)
        for x in bot_t[n]:
            up(x, y)
        for x in top_t.get(n, []):
            down(x, y, n, 4)
        if n in exits:
            pins[n] = ('metal4', 0.6 if exits[n] == 'L' else s(Wb - 0.6), y)
        else:
            g.label(n, 'metal4', lo + 0.5, y)
    for n, (lo, hi) in netsT.items():
        y = s(yT0 + 0.5 + tT[n] * P2)
        g.rect('metal2', lo - 0.1, y - 0.2, hi + 0.1, y + 0.2)
        for x in top_t[n]:
            down(x, y, n, 2)
        if n in exits:
            pins[n] = ('metal2', 0.6 if exits[n] == 'L' else s(Wb - 0.6), y)
        else:
            g.label(n, 'metal2', lo + 0.5, y)
    # ------------------------------------------------------------------ supplies
    em = {}
    xbar = dict(VSS=[(0.5, 0.5 + BAR), (Wb - 0.5 - BAR, Wb - 0.5)], VDD=[(2.0 + BAR, 2.0 + 2 * BAR), (Wb - 2.0 - 2 * BAR, Wb - 2.0 - BAR)])
    for net, y0_, h in (('VSS', yvs, RAIL_VSS), ('VDD', yvd, RAIL_VDD)):
        g.rect('metal4', 0.5, y0_, Wb - 0.5, y0_ + h)
        for a, b in xbar[net]:
            g.rect('metal5', a, yT0, b, Yt)                # bars start at the rails: ser8d pins near the edges rise below them
            em[f'{net}_rail_bar_cuts'] = g.varr(a + 0.2, y0_ + 0.2, b - 0.2, y0_ + h - 0.2, 4, 5)
    ser_x = {'VDD': sorted(x for n, x, _ in SER['power_pins'] if n == 'VDD'), 'VSS': sorted(x for n, x, _ in SER['power_pins'] if n == 'VSS')}
    dec_x0, dec_x1 = s(2.0 + 2 * BAR + 2.0), s(XA - 1.9 - 2.0)             # decap region (x)
    dec_y1 = s(Ym + MR['size_um'][1] - HSTRAP - 2.5)
    ext = {'VSS': [], 'VDD': []}           # ser8d straps that are continued into the rails
    for net, y_end in (('VSS', yvs + RAIL_VSS - 0.2), ('VDD', yvd + RAIL_VDD - 0.2)):
        for px in ser_x[net]:
            if any(a - 1.7 < px < b + 1.7 for o, v in xbar.items() if o != net for a, b in v):
                continue                   # a strap under the other net's edge bar stays inside ser8d
            ytop = dec_y1 if dec_x0 + 1.2 < px < dec_x1 - 1.2 else y_end
            ext[net].append(px)
            g.rect('metal5', px - 1.0, ypin_s - 0.3, px + 1.0, ytop)
            y0_, h = (yvs, RAIL_VSS) if net == 'VSS' else (yvd, RAIL_VDD)
            em[f'ser_{net}_cuts'] = g.varr(px - 1.0, y0_ + 0.2, px + 1.0, y0_ + h - 0.2, 4, 5)
    X0m, Wsl = MR['control_um'][0], MR['slice_um'][0]
    vdd_dx = MR['pins']['VDD'][-1][1] - X0m
    necks = []
    for p in range(9):                     # mux VSS straps: a neck clear of ser8d's VDD straps
        xb = XM + X0m + p * Wsl
        best = max((min(abs(xb + d - q) for q in ser_x['VDD']), -abs(d), d) for d in [i * 0.25 - 3.0 for i in range(25)])
        if best[0] < NECK / 2 + 1.0 + 0.6:
            raise RuntimeError('no place for a mux VSS neck')
        xn = s(xb + best[2])
        g.rect('metal5', xn - NECK / 2, yvs + 0.2, xn + NECK / 2, Ym + 0.6)
        em['mux_vss_neck_cuts'] = g.varr(xn - NECK / 2, yvs + 0.2, xn + NECK / 2, yvs + RAIL_VSS - 0.2, 4, 5)
        necks.append(xn)
    for p in range(8):                     # mux logic VDD straps: straight into the VDD rail
        xv = XM + X0m + p * Wsl + vdd_dx
        if min(abs(xv - q) for q in ser_x['VSS']) < 2.5 + 1.0 + 0.6 and False:
            raise RuntimeError('mux VDD strap over a ser8d VSS strap')
        g.rect('metal5', xv - 2.5, yvd + 0.2, xv + 2.5, Ym + 0.6)
        em['mux_vdd_cuts'] = g.varr(xv - 2.5, yvd + 0.2, xv + 2.5, yvd + RAIL_VDD - 0.2, 4, 5)
    # aux side cell: its edge bars (Metal1 || Metal2) -> rails
    for net, xl, y0_, h in (('VSS', XA - 1.9, yvs, RAIL_VSS), ('VDD', XA + aux_w - 3.8 + 0.9, yvd, RAIL_VDD)):
        g.varr(xl, Ym + 0.4, xl + 1.0, Ym + 3.4, 2, 5)
        g.rect('metal5', xl, y0_ + 0.2, xl + 1.0, Ym + 3.4)
        g.varr(xl, y0_ + 0.2, xl + 1.0, y0_ + h - 0.2, 4, 5)
        if min(abs(xl + 0.5 - q) for v in ser_x.values() for q in v) < 0.5 + 1.0 + 0.6:
            raise RuntimeError('aux supply strap over a ser8d strap')
    # mux header rails (VDD islands 2 and 3) -> VDD bars: Metal5 straps along the top edge; bridge between the two headers
    hw = MR['geo']['nfh'] * 0.44 + 0.6
    (xbM, _, _, _, DM), (xbQ, _, _, _, DQ) = MR['clusters']['M'], MR['clusters']['Q']
    yh0 = s(Yt - 0.2 - HSTRAP)
    xl_end, xr_start = s(XM + xbM - DM - 0.75 - 0.7 - 0.3), s(XM + xbQ + DQ + 0.75 + 0.7 + 0.3)
    g.rect('metal5', xbar['VDD'][0][0], yh0, xl_end, Yt - 0.2)
    g.rect('metal5', xr_start, yh0, xbar['VDD'][1][1], Yt - 0.2)
    g.rect('metal5', XM + xbM + hw - 1.0, Yt - 2.8, XM + xbQ - hw + 1.0, Yt - 0.4)
    # aux tap row: VDD rail up into the header strap, VSS rail down onto the mux's stack rail (Metal1)
    tb = AR['tap_row']['box_in_mux']
    tvdd, tvss = AR['supply_pins']['VDD'][1][2] - 0.3, AR['supply_pins']['VSS'][1][2] - 0.3
    xq = s(XM + tb[0] + 6.0)
    g.varr(xq, Ym + tvdd + 0.05, xq + 3.0, Ym + tvdd + 0.55, 2, 5)
    g.rect('metal5', xq, Ym + tvdd, xq + 3.0, yh0 + 0.5)
    xq = s(XM + tb[2] - 3.0)
    g.rect('metal1', xq, Ym + MR['slice_um'][1] - 0.8, xq + 0.6, Ym + tvss + 0.5)
    # ------------------------------------------------------------------ phase nets
    xp = [s(PH_X0 + PH_PITCH * k) for k in range(8)]
    xs_ = [SER['pins'][p][0] for p in SER['ports'] if p.startswith('PH')]
    xm = [top_t[f'PH{k}'][0] for k in range(8)]
    for k in range(8):
        if min(abs(xp[k] - q) for v in ser_x.values() for q in v) < 1.0 + 0.5 + 0.6:
            raise RuntimeError('phase pin over a ser8d strap')
    r4, r5 = RS / 0.4, RS5 / 0.44                          # ohm / um: Metal3 / Metal4 0.4 um wide, Metal5 0.44 um wide
    yS = [s(yS0 + (2 * k + 1) * PS) for k in range(8)]
    yA = [s(yM0 + (4 * k + 1) * PM) for k in range(8)]
    yBk = [s(yM0 + (4 * k + 3) * PM) for k in range(8)]
    fixed = [r5 * (yA[k] - ypin) + r4 * (abs(xm[k] - xp[k]) + 2 * PM + (Ym + 0.2 - yBk[k])) for k in range(8)]
    rtar = max(fixed) + r4 * 2 * 1.0
    lmax = max(abs(xp[k] - xs_[k]) for k in range(8))
    others = [(x, y1, y2) for x, y1, y2, n in m3]
    tab = {}
    lo_s, hi_s, lo_m, hi_m = [], [], [], []
    for k in range(8):
        n = f'PH{k}'
        # pin: Metal5 pad, Metal5 down to the S track and up to the A track
        g.rect('metal5', xp[k] - 0.6, ypin - 0.6, xp[k] + 0.6, ypin + 0.6)
        g.rect('metal5', xp[k] - 0.22, yS[k] - 0.22, xp[k] + 0.22, yA[k] + 0.22)
        g.via(xp[k], yS[k], 4, 5)
        g.via(xp[k], yA[k], 4, 5)
        pins[n] = ('metal5', xp[k], ypin)
        # S branch: track from the pin to the ser8d pin, lengthened beyond the pin to lmax
        sg = 1 if xs_[k] > xp[k] else -1
        xd = s(xp[k] - sg * (lmax - abs(xs_[k] - xp[k])))
        g.rect('metal4', min(xd, xs_[k]) - 0.2, yS[k] - 0.2, max(xd, xs_[k]) + 0.2, yS[k] + 0.2)
        up(xs_[k], yS[k])
        lo_s.append(min(xd, xs_[k]))
        hi_s.append(max(xd, xs_[k]))
        # M branch: out on track A, back on track B (equal resistance pin -> mux pin for all eight)
        sg = 1 if xm[k] >= xp[k] else -1
        e = (rtar - fixed[k]) / r4 / 2
        xu = s(round((xp[k] - sg * e) / 0.05) * 0.05)
        while any(abs(xu - x) < 0.8 and y1 < yBk[k] + 0.5 and y2 > yA[k] - 0.5 for x, y1, y2 in others):
            xu = s(xu - sg * 0.4)
        e = abs(xp[k] - xu)
        g.rect('metal4', min(xu, xp[k]) - 0.2, yA[k] - 0.2, max(xu, xp[k]) + 0.2, yA[k] + 0.2)
        g.rect('metal4', min(xu, xm[k]) - 0.2, yBk[k] - 0.2, max(xu, xm[k]) + 0.2, yBk[k] + 0.2)
        g.rect('metal3', xu - 0.2, yA[k] - 0.2, xu + 0.2, yBk[k] + 0.2)
        g.via(xu, yA[k], 3, 4)
        g.via(xu, yBk[k], 3, 4)
        others.append((xu, yA[k], yBk[k]))
        down(xm[k], yBk[k], n, 4)
        lo_m.append(min(xu, xm[k], xp[k]))
        hi_m.append(max(xu, xm[k], xp[k]))
        tab[n] = dict(pin=[xp[k], ypin], r_pin_to_mux_ohm=round(r5 * (yA[k] - ypin) + r4 * (2 * e + abs(xm[k] - xp[k]) + 2 * PM + Ym + 0.2 - yBk[k]), 2),
                      r_pin_to_ser_ohm=round(r5 * (ypin - ypin_s) + r4 * abs(xs_[k] - xp[k]), 2),
                      metal4_um=dict(to_mux=round(2 * e + abs(xm[k] - xp[k]), 1), to_ser=round(lmax, 1), of_which_dummy=round(lmax - abs(xs_[k] - xp[k]), 1)),
                      mux_pin_x=xm[k], ser_pin_x=xs_[k])
    for ys_list, lo, hi, step, cnt in ((yS0, min(lo_s) - 1.0, max(hi_s) + 1.0, 2 * PS, 9), (yM0, min(lo_m) - 1.0, max(hi_m) + 1.0, 2 * PM, 17)):
        for j in range(cnt):               # VSS shield tracks, tied to every ser8d VSS strap they cross
            y = s(ys_list + j * step)
            g.rect('metal4', lo, y - 0.2, hi, y + 0.2)
            nv = 0
            for px in ext['VSS']:
                if lo + 1.0 < px < hi - 1.0:
                    g.via(px - 0.45, y, 4, 5)
                    g.via(px + 0.45, y, 4, 5)
                    nv += 1
            if not nv:
                raise RuntimeError('shield track without a VSS strap')
    # ------------------------------------------------------------------ tap pins: Metal4 to the left edge above the tap row's wires
    for i, n in enumerate(('TAP_P', 'TAP_N')):
        _, px, py = AR['pins'][n]
        x, y, yt = s(XA - 1.9 + px), s(Ym + py), s(Ym + 151.0 + 0.9 * i)
        g.rect('metal3', x - 0.2, y - 0.2, x + 0.2, yt + 0.2)
        g.via(x, yt, 3, 4)
        g.rect('metal4', 0.3, yt - 0.2, x + 0.2, yt + 0.2)
        pins[n] = ('metal4', 0.6, yt)
    # ------------------------------------------------------------------ decap rows (left of the aux cell)
    d = T.DECAP
    nfin = int((dec_x1 - dec_x0 - 1.2) / (2 * (0.44 + (d['l'] - L.L0) / 2))) + 1
    while True:                            # as many fingers as the region's width takes (the built row tells)
        nfin -= 1
        cols = [dict(k='c', n='VSS', p='-')]
        for _ in range(nfin):
            cols += [G('DCG', d['w'], None, p=False, l=d['l']), dict(k='c', n='VSS', p='-')]
        row = XRow('dc', cols, d['w'], d['w'], through=['DCG'], tracks={'DCG': 0}, nonly=True)
        row.build()
        if row.width <= dec_x1 - dec_x0:
            break
    nrow = int((dec_y1 - 1.0 - (Ym + 1.0)) / (row.top + 0.4))
    for i in range(nrow):
        y0_ = s(Ym + 1.0 + i * (row.top + 0.4))
        g.place(row.geo, dec_x0, y0_)
        g.rect('metal2', dec_x0, y0_, dec_x1, y0_ + RAIL_W)
        g.rect('metal1', dec_x0, y0_, dec_x1, y0_ + RAIL_W)
        g.rect('via1', dec_x0 + 0.3, y0_ + 0.1, dec_x0 + row.width - 0.3, y0_ + RAIL_W - 0.1)
        ty = s(y0_ + row.track['DCG'])        # the gate track (VDD by the straps)
        for px in ser_x['VSS']:
            if dec_x0 + 1.2 < px < dec_x1 - 1.2:
                g.rect('metal2', px - 0.9, y0_, px + 0.9, y0_ + RAIL_W)
                g.varr(px - 0.9, y0_ + 0.05, px + 0.9, y0_ + 0.55, 2, 5)
        for px in ser_x['VDD']:
            if dec_x0 + 1.2 < px < dec_x0 + row.width - 1.2:
                g.via(px - 0.45, ty, 2, 5)
                g.via(px + 0.45, ty, 2, 5)
    ndec = nfin * nrow
    # ------------------------------------------------------------------ labels
    for n in ('MAIN_P', 'MAIN_N', 'POST_P', 'POST_N'):
        port = next(p for p, v in cn['wtx_mux8'].items() if v == n and p.startswith(('MAIN', 'POST')))
        _, x, y = MR['pins'][port][0]
        pins[n] = ('metal5', s(XM + x), s(Ym + y))
        g.rect('metal5', XM + x - 0.5, Ym + y - 0.4, XM + x + 0.5, Ym + y + 0.4)      # top-level metal under the label, on the riser
    for i, n in enumerate(T.PORTS):
        if n in ('VDD', 'VSS'):
            for a, b in xbar[n]:
                g.label(n, 'metal5', s((a + b) / 2), s(Yt - 20.0), i + 1)
        else:
            layer, x, y = pins[n]
            g.label(n, layer, x, y, i + 1)
    L.run_tcl(work, NAME, g.tcl(NAME, extra=inst))
    free = [s(XM + MR['size_um'][0] + 2.0), s(Ym + 0.5), s(xbar['VDD'][1][0] - 2.0), s(yh0 - 1.5)]
    res = dict(bar_y0=yT0, size_um=[Wb, Yt], area_um2=round(Wb * Yt, 1), seam_um=[Y0, Ym], zones_y=dict(B=yB0, S=yS0, pins=ypin, M=yM0, T=yT0, vss_rail=[yvs, yvs + RAIL_VSS], vdd_rail=[yvd, yvd + RAIL_VDD]),
               tracks=dict(B=nB, T=nT), mux_origin=[XM, Ym], aux_origin=[s(XA - 1.9), Ym], ph=tab, ph_r_target_ohm=round(rtar, 2), ph_lmax_um=round(lmax, 1),
               decap=dict(fingers=ndec, rows=nrow, per_row=nfin, w=d['w'], l=d['l'], box=[dec_x0, s(Ym + 1.0), dec_x1, dec_y1]),
               keep_free=dict(box=free, area_um2=round((free[2] - free[0]) * (free[3] - free[1]), 1)),
               pins={n: list(v) for n, v in pins.items()}, supply_bars=xbar, bar_y=[yT0, Yt], em_cuts=em, mux_vss_necks_x=necks,
               f_wires_um={n: round(netsB[n][1] - netsB[n][0], 1) for n in netsB if re.match(r'F\d$', n)},
               ser_straps_in_rails={k: len(v) for k, v in ext.items()}, header_strap=dict(y=[yh0, s(Yt - 0.2)], left_end_x=xl_end, right_start_x=xr_start), exits=exits)
    (work / 'geom.json').write_text(json.dumps(res, indent=1))
    return res


def reference():
    return '* reference: wtx8_top.netlist()\n' + T.netlist()


def negatives(sch):
    """references that must NOT match: two phases swapped at the mux, stream rotation off by one, OVP / OVN swapped at the mux."""
    xm = next(l for l in sch.splitlines() if l.startswith('XMUX '))
    tk = xm.split()
    a = list(tk)
    a[1], a[2] = a[2], a[1]
    b = list(tk)
    b[9:17] = b[10:17] + b[9:10]
    c = list(tk)
    io, jn = mux8.PORTS.index('OVP') + 1, mux8.PORTS.index('OVN') + 1
    c[io], c[jn] = c[jn], c[io]
    return {'neg_ph0_ph1_swapped_at_mux': sch.replace(xm, ' '.join(a)), 'neg_stream_rotation_plus_one': sch.replace(xm, ' '.join(b)),
            'neg_ovp_ovn_swapped_at_mux': sch.replace(xm, ' '.join(c))}


def cval(x):
    u = {'f': 1.0, 'p': 1e3, 'a': 1e-3, 'n': 1e6}.get(x[-1])
    return float(x[:-1]) * u if u else float(x) * 1e15


def net_caps(text, nets):
    """{net: {partner group: fF}} from a flat netlist; groups: VSS, VDD, the other listed nets, mux, ser8d, aux, other."""
    out = {n: {} for n in nets}
    for l in text.splitlines():
        if l.startswith('C'):
            tk = l.split()
            for a, b in ((tk[1], tk[2]), (tk[2], tk[1])):
                if a in out:
                    k = b if b in ('VSS', 'VDD') or b in out else 'mux' if b.startswith('XMUX') else 'ser8d' if b.startswith('XSER') else 'aux' if b.startswith('XAUX') else 'other'
                    out[a][k] = out[a].get(k, 0.0) + cval(tk[3])
    return {n: dict(total=round(sum(v.values()), 1), **{k: round(x, 2) for k, x in sorted(v.items(), key=lambda kv: -kv[1])}) for n, v in out.items()}


def em_table(res, mr):
    """supply straps of the block top for 2 x I_BANK (banks) + I_LOGIC (ser8d and logic), mA DC at 85 C; limits as wtx_mux8_layout."""
    rows = {}

    def row(name, i, w, lim):
        rows[name] = dict(mA=round(i, 2), um=round(w, 2), mA_per_um=round(i / w, 2), limit=lim, margin_pct=round(100 * (1 - i / w / lim), 1))

    def cut(name, i, n):
        rows[name] = dict(mA=round(i, 2), cuts=n, mA_per_cut=round(i / n, 3), limit=L.CUT, margin_pct=round(100 * (1 - i / n / L.CUT), 1))
    c, half = res['em_cuts'], (2 * I_BANK + I_LOGIC) / 2
    row('VSS edge bar (Metal5; half of 2 banks + logic per side)', half, BAR, L.LIM5)
    row('VDD edge bar (Metal5; one header + half of the logic per side)', I_BANK + I_LOGIC / 2, BAR, L.LIM5)
    row('VSS rail (Metal4), at a bar', half, RAIL_VSS, L.LIM14)
    row('VDD rail (Metal4), at a bar', I_LOGIC / 2, RAIL_VDD, L.LIM14)
    cut('VSS rail -> bar Via4', half, c['VSS_rail_bar_cuts'])
    cut('VDD rail -> bar Via4', I_LOGIC / 2, c['VDD_rail_bar_cuts'])
    row('header strap bar -> MAIN / POST header (Metal5; the whole bank through one strap)', I_BANK, HSTRAP, L.LIM5)
    ivss = I_BANK / 4 + 3.0
    row('mux VSS strap neck in the rails (Metal5; two banks of two slices + 3 mA logic, as the mux table)', ivss, NECK, L.LIM5)
    cut('mux VSS neck -> rail Via4', ivss, c['mux_vss_neck_cuts'])
    row('mux logic VDD strap (Metal5, ~3 mA estimate)', 3.0, 5.0, L.LIM5)
    ns = res['ser_straps_in_rails']
    row(f'ser8d VSS strap (Metal5 2 um; {I_LOGIC:g} mA over {ns["VSS"]} straps)', I_LOGIC / ns['VSS'], 2.0, L.LIM5)
    row(f'ser8d VDD strap (Metal5 2 um; {I_LOGIC:g} mA over {ns["VDD"]} straps)', I_LOGIC / ns['VDD'], 2.0, L.LIM5)
    cut('ser8d strap -> rail Via4', I_LOGIC / min(ns.values()), min(c['ser_VSS_cuts'], c['ser_VDD_cuts']))
    worst = min(rows.items(), key=lambda kv: kv[1]['margin_pct'])
    return dict(rows=rows, worst=[worst[0], worst[1]['margin_pct']],
                note='The middle segment of each header rail (between its two output risers) is reached only through the rail\'s own Metal1 + Metal2 under the '
                     'risers (6 um: 12.5 mA) unless the pad feeds the mux\'s top-edge VDD pins: see REPORT.')


def add_top_r(text, res):
    """documented post-process: pt_wiredtx8.rc.spice = the flat C netlist + the DRAWN resistance of the top-level wiring:
      PH k   pin node PH k; the mux's devices move to PH k#m behind the pin -> mux resistance, ser8d's to PH k#s behind the
             pin -> ser8d resistance (table res['ph']); capacitors to mux / ser8d nets follow their side, the others are split
             by Metal4 length (to_mux : to_ser);
      F k    ser8d's devices move to F k#s behind the track resistance (Metal4 0.4 um, length = track span);
      VDD / VSS  the children hang on VDD#mux, VDD#ser, VDD#aux (VSS likewise) behind one lumped resistor each: rail from both
             bars to the block centre (distributed: 1/8 of the end-to-end value) plus the child's straps in parallel.
    A device belongs to the child whose instance prefix (XMUX / XSER / XAUX) its other nets carry."""
    r4 = RS / 0.4
    rr = {}
    for k in range(8):
        rr[f'PH{k}'] = dict(m=res['ph'][f'PH{k}']['r_pin_to_mux_ohm'], s=res['ph'][f'PH{k}']['r_pin_to_ser_ohm'])
    fw = res['f_wires_um']
    Wb = res['size_um'][0]
    rail = lambda w: RS * Wb / w / 8
    sup = dict(VSS=dict(mux=round(rail(RAIL_VSS) + RS5 * 30.0 / NECK / 9, 3), ser=round(rail(RAIL_VSS) + RS5 * 100.0 / 2.0 / res['ser_straps_in_rails']['VSS'], 3),
                        aux=round(rail(RAIL_VSS) + RS5 * 30.0 / 1.0, 3)),
               VDD=dict(mux=round(rail(RAIL_VDD) + RS5 * 12.0 / 5.0 / 8, 3), ser=round(rail(RAIL_VDD) + RS5 * 100.0 / 2.0 / res['ser_straps_in_rails']['VDD'], 3),
                        aux=round(rail(RAIL_VDD) + RS5 * 12.0 / 1.0, 3)))
    side = lambda toks: next((c for p_, c in (('XMUX', 'mux'), ('XSER', 'ser'), ('XAUX', 'aux')) if any(x.startswith(p_) for x in toks)), None)
    out, extra = [], []
    for l in text.splitlines():
        tk = l.split()
        if not tk or l[0] in '.*+':
            out.append(l)
            continue
        if tk[0][0] == 'X':
            nmod = next(i for i, x in enumerate(tk) if '=' in x) - 1 if any('=' in x for x in tk) else len(tk) - 1
            nodes = tk[1:nmod]
            sd = side(nodes)
            new = []
            for x in nodes:
                if x in rr and sd in ('mux', 'ser'):
                    x = f'{x}#{sd[0]}'
                elif x in fw and sd == 'ser':
                    x = f'{x}#s'
                elif x in sup and sd:
                    x = f'{x}#{sd}'
                new.append(x)
            out.append(' '.join([tk[0]] + new + tk[nmod:]))
        elif tk[0][0] == 'C':
            a, b = tk[1], tk[2]
            if b in rr and a not in rr:
                a, b = b, a
            if a in rr:
                sd = side([b])
                if sd in ('mux', 'ser'):
                    out.append(f'{tk[0]} {a}#{sd[0]} {b} {tk[3]}')
                else:
                    lm, ls = res['ph'][a]['metal4_um']['to_mux'], res['ph'][a]['metal4_um']['to_ser']
                    v = cval(tk[3]) * 1e-15
                    b2 = lambda s_: (b + '#' + s_) if b in rr else b
                    out += [f'{tk[0]}_m {a}#m {b2("m")} {v * lm / (lm + ls):.4g}', f'{tk[0]}_s {a}#s {b2("s")} {v * ls / (lm + ls):.4g}']
            else:
                out.append(l)
        else:
            out.append(l)
    n = 0
    for k, v in rr.items():
        extra += [f'RTP{n} {k} {k}#m {v["m"]}', f'RTP{n + 1} {k} {k}#s {v["s"]}']
        n += 2
    rf = {}
    for k, w in fw.items():
        rf[k] = round(r4 * w, 2)
        extra.append(f'RTF{n} {k} {k}#s {rf[k]}')
        n += 1
    for net, v in sup.items():
        for c, r in v.items():
            extra.append(f'RTS{n} {net} {net}#{c} {r}')
            n += 1
    i = max(k for k, l in enumerate(out) if l.startswith('.ends'))
    out = out[:i] + ['* drawn top-level wire resistance added by pt_wiredtx8_layout.add_top_r'] + extra + out[i:]
    return '\n'.join(out) + '\n', dict(ph=rr, f_ohm=rf, supply_ohm=sup, resistors_added=len(extra))


def run_all():
    res = build()
    if T.DECAP['n'] != res['decap']['fingers']:
        set_decap(res['decap']['fingers'])
    b = WORK / 'build'
    sch = reference()
    res['build_check'] = L.check(b, NAME, sch)
    gds = L.export_gds(b, NAME)
    v = L.verify(gds, WORK / 'verify', NAME, sch, negatives(sch))
    res['verify_from_disk'] = v
    f = WORK / 'verify' / f'{NAME}.ext.spice'
    raw = f.read_text()
    fixed, nfix = L.fix_vsubs(raw, NAME)
    res['c_netlist'] = dict(vsubs_lines_fixed=nfix, ports_ok=L.ports_of(fixed, NAME) == list(T.PORTS),
                            devices={k: sum(1 for l in fixed.splitlines() if l.startswith('X') and k in l) for k in ('nfet_03v3', 'pfet_03v3', 'ppolyf_u', 'diode')},
                            floating_vsubs_left=sum(1 for l in fixed.splitlines() if 'VSUBS' in l))
    f.unlink()
    f.write_text(fixed)
    nets = [f'PH{k}' for k in range(8)] + [f'F{k}' for k in range(8)] + ['MAIN_P', 'MAIN_N', 'POST_P', 'POST_N']
    res['wire_c_fF'] = net_caps(fixed, nets)
    build(WORK / 'bare', bare=True)                        # the top-level wiring alone
    L.check(WORK / 'bare', NAME, '', lvs=False)
    res['wire_c_top_only_fF'] = net_caps(L.fix_vsubs((WORK / 'bare' / f'{NAME}.ext.spice').read_text(), NAME)[0], nets[:16])
    shutil.rmtree(WORK / 'bare')
    rc, res['rc_netlist'] = add_top_r(fixed, res)
    (WORK / 'verify' / f'{NAME}.rc.spice').write_text(rc)
    mr = json.loads((L.OUT / 'report.json').read_text())
    res['em_table'] = em_table(res, mr)
    cdec = T.DECAP['n'] * T.DECAP['w'] * T.DECAP['l']
    res['decap']['gate_area_um2'] = cdec
    OUT.mkdir(parents=True, exist_ok=True)
    res['sha256'] = {}
    for src, name in ((gds, f'{NAME}.gds'), (f, f'{NAME}.ext.spice'), (WORK / 'verify' / f'{NAME}.rc.spice', f'{NAME}.rc.spice'),
                      (WORK / 'verify' / f'{NAME}.lvs.spice', f'{NAME}.lvs.spice')):
        shutil.copy(src, OUT / name)
        shutil.copy(src, FAST / name)
        res['sha256'][name] = tools.sha(OUT / name)
    for x in ('lvs.txt', 'antenna.txt', 'verify.json'):
        if (WORK / 'verify' / x).exists():
            shutil.copy(WORK / 'verify' / x, OUT / f'{NAME}-{x}')
    (OUT / 'report.json').write_text(json.dumps(res, indent=1))
    return res


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'build':
        r = build()
        if T.DECAP['n'] != r['decap']['fingers']:
            set_decap(r['decap']['fingers'])
        print(json.dumps(dict(size=r['size_um'], check=L.check(WORK / 'build', NAME, reference())), indent=1))
    else:
        r = run_all()
        v = r['verify_from_disk']
        print(json.dumps(dict(size=r['size_um'], area=r['area_um2'], magic_drc=v['magic_drc'], klayout=v['klayout_drc'].get('violations'), lvs=v['lvs'],
                              negatives={k: x['fails_as_required'] for k, x in v['negative_controls'].items()}, antenna=v['antenna_magic'],
                              c_netlist=r['c_netlist'], ph={k: r['wire_c_fF'][k] for k in r['wire_c_fF'] if k.startswith('PH')}, em_worst=r['em_table']['worst'],
                              sha=r['sha256']), indent=1))
