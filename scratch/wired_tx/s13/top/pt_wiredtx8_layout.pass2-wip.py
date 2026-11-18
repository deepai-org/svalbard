"""pt_wiredtx8 block top layout generator, second pass (schematic = wtx8_top.top() / wtx8_top.netlist()).  NOT published.

    python3 pt_wiredtx8_layout.py            # build, GDS, checks on the GDS read back, netlists -> scratch/wired_tx/s13/top
    python3 pt_wiredtx8_layout.py build      # layout + DRC / LVS in the build directory only

Children (not rebuilt here): wtx_ser8d (generated/fast), wtx_mux8 (wtx_mux8_layout.py), wtx8_aux (wtx8_aux_layout.py).

    +----------------------------------------- pad edge ------------------------+
    | VSS VDD |  decap rows  | aux |        wtx_mux8          | VDD VSS |        (top right corner: not part of the block)
    | bars    |              | side|   outputs on the top edge | bars    |
    |---------+--------------+-----+---------------------------+---------+---------------------------------------+
    | seam: T  supply rails, Metal4 || Metal2 (VDD above VSS); Metal3 from the pins above passes between the two   |
    |       B  Metal4 tracks: PS k (phase buffer -> ser8d, a VSS track between neighbours), F k, SERQ               |
    |          under them: the eight phase buffers (one under each mux PH pin, with the block's PH k pin) and,     |
    |          left of the mux, the Metal2 tracks of the aux / mux control pins to the left edge                   |
    +--------------------------------------------------------------------------------------------------------------+
    |                 wtx_ser8d (pins on its top edge; D0..D39 and the word clock continued to the bottom edge)     |
    +--------------------------------------------------------------------------------------------------------------+

Phase nets: the ring sees, per phase, the block pin (Metal5 pad in the seam under the mux PH k pin), a Metal3 stub of the
same length up to the mux pin and the first buffer inverter beside the pad: identical geometry for all eight.
Pins: PH k as above; D0..D39, WORD_CLK40: Metal5 on the bottom edge (ser8d's own port trunks continued down); trim bits:
Metal3 pads at the bottom of the seam straight below the mux pins; aux / mux controls: Metal2 on the left edge at seam
height (ATB_AVGP / N: right edge); MAIN_BIAS / POST_BIAS: Metal4 on the top edge over the aux cell; TAP_P / TAP_N: Metal4
on the left edge near the top; MAIN / POST: the mux's risers on the top edge; supplies: Metal5 bars left of the decap and
right of the mux.
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
P4, P2 = 0.84, 0.72                  # track pitches in the seam: Metal4, Metal2
RAIL_VSS, RAIL_VDD = 12.5, 5.0       # supply rails in zone T, each Metal4 || Metal2
BAR = 12.0                           # Metal5 edge bars
HSTRAP = 7.5                         # Metal5 strap from a VDD bar to a header rail of the mux
NECK = 2.5                           # mux VSS strap in zone T
I_BANK, I_LOGIC = 26.0, 30.0         # mA: per bank; ser8d + logic
CGATE = 2.2                          # fF per um of gate width (estimate for the ring-load figure)
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


def build(work=None, bare=False):
    """bare: the top-level wiring alone, without the three children (for the wiring-C tables)."""
    work = Path(work or WORK / 'build')
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    for d in (FAST / 'wtx_ser8d_mag', L.WORK / 'build', AX.WORK / 'build'):
        for f in d.glob('*.mag'):
            shutil.copy(f, work / f.name)
    MR = json.loads((L.OUT / 'report.json').read_text())
    AR = json.loads((AX.OUT / 'report.json').read_text())
    DC = json.loads((WORK / 'serm5' / 'dcols.json').read_text())      # ser8d port trunks: lower end, Metal5 below (see ser_trunks)
    cn = conn()
    Wb, Y0 = SER['bbox'][2], SER['bbox'][3]
    ypin_s = SER['pins']['PH0'][1]
    xa0 = AR['head']['mux_origin_in_cell_x']
    XM = 242.1
    XA = s(XM - xa0)
    aux_w = AR['size_um'][0]
    g, inst = Geo(), []
    # ------------------------------------------------------------------ terminals
    top_t, bot_t = {}, {}                  # net -> x of pins above (Metal3) / below (Metal5)
    down_pins = {}                         # nets that leave ser8d on its bottom edge: net -> ser8d port
    for port, net in cn['wtx_ser8d'].items():
        if port in ('VDD', 'VSS'):
            continue
        if port in DC:
            down_pins[net] = port
        else:
            bot_t.setdefault(net, []).append(SER['pins'][port][0])
    for port, net in cn['wtx_mux8'].items():
        for layer, x, y in MR['pins'][port]:
            if layer == 'metal3' and y < 1.0:
                top_t.setdefault(net, []).append(s(XM + x))
    for port, net in cn['wtx8_aux'].items():
        if port in AR['pins'] and AR['pins'][port][2] < 1.0:
            top_t.setdefault(net, []).append(s(XA - 1.9 + AR['pins'][port][1]))
    ph, ps = [f'PH{k}' for k in range(8)], [f'PS{k}' for k in range(8)]
    special = set(ph) | set(ps) | {'MAIN_P', 'MAIN_N', 'POST_P', 'POST_N', 'TAP_P', 'TAP_N', 'VDD', 'VSS', 'MAIN_BIAS', 'POST_BIAS'}
    trim = [n for n in top_t if n.startswith('TR')]
    xm = [top_t[f'PH{k}'][0] for k in range(8)]
    xs_ = [bot_t[f'PS{k}'][0] for k in range(8)]
    # ------------------------------------------------------------------ phase buffer cell (built once, painted eight times)
    b1, b2 = T.PHBUF
    cols, bnet = [], []
    for c_, n_ in (L.g_inv('b', 'PB', 'PS', b2[0], b2[1], 3.0, 6.0), L.g_inv('a', 'PH', 'PB', b1[0], b1[1], 3.0, 6.0)):
        L.join(cols, c_)
        bnet += n_
    brow = XRow('pb', cols, 3.0, 6.0, tracks=AX.solve_tracks(cols))
    brow.build()
    bx = {n: (brow.ext[n][0] + brow.ext[n][1]) / 2 for n in ('PH', 'PS')}
    bx['PH'] = s(brow.ext['PH'][1] - 0.2)                 # the mux pin's stub lands on the right end of the PH track
    bx['PS'] = s(brow.ext['PS'][0] + 0.2)
    bx['VDD'] = s(min((x for x in [0.5 + 0.05 * i for i in range(int(brow.width / 0.05) - 10)]
                       if abs(x - bx['PH']) >= 0.9 and abs(x - bx['PS']) >= 0.9), key=lambda x: abs(x - brow.width / 2)))
    # ------------------------------------------------------------------ tracks
    m4nets = {n: (min(top_t.get(n, []) + bot_t[n]) - 0.3, max(top_t.get(n, []) + bot_t[n]) + 0.3) for n in bot_t if n not in special}
    psx = [s(xm[k] - bx['PH'] + bx['PS']) for k in range(8)]                 # x of the buffer's PS column
    psn = {f'PS{k}': (min(psx[k], xs_[k]) - 0.3, max(psx[k], xs_[k]) + 0.3) for k in range(8)}
    tF, tP = pack(m4nets), pack(psn)
    nF, nP = max(tF.values()) + 1, max(tP.values()) + 1
    m2nets = {}
    for n in top_t:
        if n in special or n in bot_t or n in trim:
            continue
        side = 'R' if min(top_t[n]) > XM + 300 else 'L'
        port = n in T.PORTS
        m2nets[n] = ((0.3 if port and side == 'L' else min(top_t[n]) - 0.3), (Wb - 0.3 if port and side == 'R' else max(top_t[n]) + 0.3), side if port else None)
    t2 = pack({n: v[:2] for n, v in m2nets.items()})
    n2 = max(t2.values()) + 1
    # ------------------------------------------------------------------ zones (y)
    yB0 = s(Y0 + 2.4)
    yP0 = s(yB0 + nF * P4 + 0.3)                           # PS sub-zone: VSS track, PS, VSS, PS, ...
    hB = max((nF + 2 * nP + 1) * P4 + 0.3, n2 * P2, brow.top + 0.6)
    yT0 = s(yB0 + hB + 1.0)
    yvs, yvd = yT0, s(yT0 + RAIL_VSS + 1.0)
    Ym = s(yvd + RAIL_VDD + 1.6)
    Yt = s(Ym + MR['size_um'][1])
    if not bare:
        inst += ['getcell wtx_ser8d child 0 0 parent 0 0', 'identify XSER', f'getcell wtx_mux8 child 0 0 parent {XM} {Ym}', 'identify XMUX',
                 f'getcell wtx8_aux child 0 0 parent {XA} {Ym}', 'identify XAUX']
    m3 = []                                # x of every Metal3 vertical that crosses zone T

    def down(x, y, lo):                    # Metal3 from a pin above to its track (Metal2: lo = 2, Metal4: lo = 4)
        g.rect('metal3', x - 0.2, y - 0.2, x + 0.2, Ym + 0.4)
        g.via(x, y, 2, 3) if lo == 2 else g.via(x, y, 3, 4)
        m3.append(x)

    def up(x, y):                          # Metal5 from a ser8d pin to its track
        g.rect('metal5', x - 0.22, ypin_s - 0.22, x + 0.22, y + 0.22)
        g.via(x, y, 4, 5)
    pins = {}
    for n, (lo, hi) in m4nets.items():
        y = s(yB0 + tF[n] * P4)
        g.rect('metal4', lo - 0.1, y - 0.2, hi + 0.1, y + 0.2)
        g.label(n, 'metal4', lo + 0.5, y)
        for x in bot_t[n]:
            up(x, y)
        for x in top_t.get(n, []):
            down(x, y, 4)
    for n, (lo, hi, side) in m2nets.items():
        y = s(yB0 + t2[n] * P2)
        g.rect('metal2', lo - 0.1, y - 0.2, hi + 0.1, y + 0.2)
        for x in top_t[n]:
            down(x, y, 2)
        if side:
            pins[n] = ('metal2', 0.6 if side == 'L' else s(Wb - 0.6), y)
        else:
            g.label(n, 'metal2', lo + 0.5, y)
    for n in trim:                         # trim bits: pins at the bottom of the seam straight below the mux pins
        x = top_t[n][0]
        g.rect('metal3', x - 0.2, Y0 + 1.2, x + 0.2, Ym + 0.4)
        m3.append(x)
        pins[n] = ('metal3', x, s(Y0 + 1.6))
    # ------------------------------------------------------------------ supplies
    em = {}
    xr0 = s(XM + MR['size_um'][0] + 2.0)                   # right-hand bars: directly right of the mux
    xbar = dict(VSS=[(0.5, 0.5 + BAR), (xr0 + BAR + 1.5, xr0 + 2 * BAR + 1.5)], VDD=[(2.0 + BAR, 2.0 + 2 * BAR), (xr0, xr0 + BAR)])
    for net, y0_, h in (('VSS', yvs, RAIL_VSS), ('VDD', yvd, RAIL_VDD)):
        for m in ('metal4', 'metal2'):
            g.rect(m, 0.5, y0_, Wb - 0.5, y0_ + h)
        for a, b in xbar[net]:
            g.rect('metal5', a, yT0, b, Yt)
            em[f'{net}_rail_bar_cuts'] = g.varr(a + 0.2, y0_ + 0.2, b - 0.2, y0_ + h - 0.2, 2, 5)
    ser_x = {'VDD': sorted(x for n, x, _ in SER['power_pins'] if n == 'VDD'), 'VSS': sorted(x for n, x, _ in SER['power_pins'] if n == 'VSS')}
    dec_x0, dec_x1 = s(2.0 + 2 * BAR + 2.0), s(XA - 1.9 - 2.0)
    dec_y1 = s(Ym + MR['size_um'][1] - HSTRAP - 2.5)
    ext = {'VSS': [], 'VDD': []}
    for net, y_end in (('VSS', yvs + RAIL_VSS - 0.2), ('VDD', yvd + RAIL_VDD - 0.2)):
        for px in ser_x[net]:
            if any(a - 1.7 < px < b + 1.7 for o, v in xbar.items() if o != net for a, b in v):
                continue                   # a strap under the other net's bar stays inside ser8d
            if min(abs(px - x) for x in xm) < 0.6 + 1.0 + 0.7:
                continue                   # ... and so does a strap that would run into a phase pin pad
            ytop = dec_y1 if dec_x0 + 1.2 < px < dec_x1 - 1.2 else y_end
            ext[net].append(px)
            g.rect('metal5', px - 1.0, ypin_s - 0.3, px + 1.0, ytop)
            y0_, h = (yvs, RAIL_VSS) if net == 'VSS' else (yvd, RAIL_VDD)
            em[f'ser_{net}_cuts'] = g.varr(px - 1.0, y0_ + 0.2, px + 1.0, y0_ + h - 0.2, 4, 5)
    X0m, Wsl = MR['control_um'][0], MR['slice_um'][0]
    vdd_dx = MR['pins']['VDD'][-1][1] - X0m
    necks = []
    for p in range(9):
        xb = XM + X0m + p * Wsl
        best = max((min(abs(xb + d - q) for q in ser_x['VDD']), -abs(d), d) for d in [i * 0.25 - 3.0 for i in range(25)])
        if best[0] < NECK / 2 + 1.0 + 0.6:
            raise RuntimeError('no place for a mux VSS neck')
        xn = s(xb + best[2])
        g.rect('metal5', xn - NECK / 2, yvs + 0.2, xn + NECK / 2, Ym + 0.6)
        em['mux_vss_neck_cuts'] = g.varr(xn - NECK / 2, yvs + 0.2, xn + NECK / 2, yvs + RAIL_VSS - 0.2, 4, 5)
        necks.append(xn)
    for p in range(8):
        xv = XM + X0m + p * Wsl + vdd_dx
        g.rect('metal5', xv - 2.5, yvd + 0.2, xv + 2.5, Ym + 0.6)
        em['mux_vdd_cuts'] = g.varr(xv - 2.5, yvd + 0.2, xv + 2.5, yvd + RAIL_VDD - 0.2, 4, 5)
    for net, xl, y0_, h in (('VSS', XA - 1.9, yvs, RAIL_VSS), ('VDD', XA + aux_w - 3.8 + 0.9, yvd, RAIL_VDD)):
        g.varr(xl, Ym + 0.4, xl + 1.0, Ym + 3.4, 2, 5)
        g.rect('metal5', xl, y0_ + 0.2, xl + 1.0, Ym + 3.4)
        g.varr(xl, y0_ + 0.2, xl + 1.0, y0_ + h - 0.2, 4, 5)
        if min(abs(xl + 0.5 - q) for v in ser_x.values() for q in v) < 0.5 + 1.0 + 0.6:
            raise RuntimeError('aux supply strap over a ser8d strap')
    hw = MR['geo']['nfh'] * 0.44 + 0.6
    (xbM, _, _, _, DM), (xbQ, _, _, _, DQ) = MR['clusters']['M'], MR['clusters']['Q']
    yh0 = s(Yt - 0.2 - HSTRAP)
    xl_end, xr_start = s(XM + xbM - DM - 0.75 - 0.7 - 0.3), s(XM + xbQ + DQ + 0.75 + 0.7 + 0.3)
    g.rect('metal5', xbar['VDD'][0][0], yh0, xl_end, Yt - 0.2)
    g.rect('metal5', xr_start, yh0, xbar['VDD'][1][1], Yt - 0.2)
    g.rect('metal5', XM + xbM + hw - 1.0, Yt - 2.8, XM + xbQ - hw + 1.0, Yt - 0.4)
    tb = AR['tap_row']['box_in_mux']
    tvdd, tvss = AR['supply_pins']['VDD'][1][2] - 0.3, AR['supply_pins']['VSS'][1][2] - 0.3
    xq = s(XM + tb[0] + 6.0)
    g.varr(xq, Ym + tvdd + 0.05, xq + 3.0, Ym + tvdd + 0.55, 2, 5)
    g.rect('metal5', xq, Ym + tvdd, xq + 3.0, yh0 + 0.5)
    xq = s(XM + tb[2] - 3.0)
    g.rect('metal1', xq, Ym + MR['slice_um'][1] - 0.8, xq + 0.6, Ym + tvss + 0.5)
    # ------------------------------------------------------------------ phase buffers, PH pins, PS nets
    by0 = s(yT0 + RAIL_W - brow.top)                       # flipped: the cell's VSS rail lies in the VSS rail (Metal2)
    fy = lambda y: s(by0 + brow.top - y)
    ypin = s(yT0 - 2.0)
    tab = {}
    for k in range(8):
        dx = s(xm[k] - bx['PH'])
        g.place(brow.geo, dx, by0, brow.top)
        for yr in (by0, by0 + brow.top - RAIL_W):          # Metal2 over the cell's rails
            g.rect('metal2', dx, yr, dx + brow.width, yr + RAIL_W)
            g.rect('via1', dx + 0.3, yr + 0.1, dx + brow.width - 0.3, yr + RAIL_W - 0.1)
        typ, tys = fy(brow.track['PH']), fy(brow.track['PS'])
        # PH: Metal3 stub from the mux pin to the PH track; the block pin (Metal5 pad) on it
        g.rect('metal3', xm[k] - 0.2, typ - 0.2, xm[k] + 0.2, Ym + 0.4)
        g.via(xm[k], typ, 2, 3)
        g.via(xm[k], ypin, 3, 5)
        g.rect('metal5', xm[k] - 0.6, ypin - 0.6, xm[k] + 0.6, ypin + 0.6)
        m3.append(xm[k])
        pins[f'PH{k}'] = ('metal5', xm[k], ypin)
        if min(abs(xm[k] - q) for v in ext.values() for q in v) < 0.6 + 1.0 + 0.6:
            raise RuntimeError('phase pin over a ser8d strap')
        # VDD: Metal3 from the cell's lower rail up into the VDD rail
        xv = s(dx + bx['VDD'])
        g.via(xv, by0 + 0.3, 2, 3)
        g.rect('metal3', xv - 0.2, by0 + 0.1, xv + 0.2, yvd + 1.2)
        g.via(xv, yvd + 1.0, 3, 4)
        m3.append(xv)
        # PS: Metal3 from the PS track down to the net's Metal4 track, Metal5 from the ser8d pin
        n = f'PS{k}'
        y = s(yP0 + (2 * tP[n] + 1) * P4)
        g.via(psx[k], tys, 2, 3)
        g.rect('metal3', psx[k] - 0.2, min(y, tys) - 0.2, psx[k] + 0.2, max(y, tys) + 0.2)
        g.via(psx[k], y, 3, 4)
        g.rect('metal4', psn[n][0] - 0.1, y - 0.2, psn[n][1] + 0.1, y + 0.2)
        g.label(n, 'metal4', psn[n][0] + 0.8, y)
        up(xs_[k], y)
        lst, lps = Ym + 0.2 - typ, abs(psx[k] - xs_[k])
        tab[f'PH{k}'] = dict(pin=[xm[k], ypin], stub_metal3_um=round(lst, 2), r_pin_to_mux_ohm=round(RS / 0.4 * (Ym + 0.2 - ypin), 2))
        tab[n] = dict(metal4_um=round(lps, 1), r_ohm=round(RS / 0.4 * (lps + abs(y - tys)) + RS5 / 0.44 * (y - ypin_s), 2), buffer_x=psx[k], ser_pin_x=xs_[k])
    lo, hi = min(v[0] for v in psn.values()) - 1.0, max(v[1] for v in psn.values()) + 1.0
    for j in range(nP + 1):                # VSS tracks between the PS tracks, tied to the ser8d VSS straps they cross
        y = s(yP0 + 2 * j * P4)
        g.rect('metal4', lo, y - 0.2, hi, y + 0.2)
        for px in ext['VSS']:
            if lo + 1.0 < px < hi - 1.0:
                g.via(px - 0.45, y, 4, 5)
                g.via(px + 0.45, y, 4, 5)
    # rails: Metal2 and Metal4 stitched at the ser8d straps that have no Metal3 vertical nearby
    nst = {'VSS': 0, 'VDD': 0}
    for net, y0_, h in (('VSS', yvs, RAIL_VSS), ('VDD', yvd, RAIL_VDD)):
        for px in ext[net]:
            if all(abs(px - x) > 1.0 + 0.2 + 0.5 for x in m3):
                g.varr(px - 1.0, y0_ + 0.3, px + 1.0, y0_ + h - 0.3, 2, 4)
                nst[net] += 1
    # ------------------------------------------------------------------ D0..D39, word clock: ser8d's port trunks continued to the bottom edge
    for net, port in down_pins.items():
        c = DC[port]
        if c['nblk']:
            raise RuntimeError(f'ser8d trunk of {port} has other Metal5 below it: Metal4 jog not implemented')
        g.rect('metal5', c['x'] - 0.22, 0.0, c['x'] + 0.22, c['lo'] + 0.6)
        pins[net] = ('metal5', c['x'], 0.5)
    # ------------------------------------------------------------------ tail biases to the top edge (over the aux cell), tap pins to the left edge
    for n in ('MAIN_BIAS', 'POST_BIAS'):
        port = next(p_ for p_, v in cn['wtx8_aux'].items() if v == n)
        x = s(XA - 1.9 + AR['pins'][port][1])
        if min(abs(AR['pins'][port][1] - q) for q in AR['m5_risers_x']) < 1.2:
            raise RuntimeError('bias riser over an aux Metal5 riser')
        g.via(x, Ym + 0.2, 3, 5)
        g.rect('metal5', x - 0.22, Ym, x + 0.22, yh0 - 1.0)
        g.via(x, yh0 - 1.2, 4, 5)
        g.rect('metal4', x - 0.2, yh0 - 1.4, x + 0.2, Yt)
        pins[n] = ('metal4', x, s(Yt - 0.5))
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
    while True:
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
        ty = s(y0_ + row.track['DCG'])
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
        port = next(p_ for p_, v in cn['wtx_mux8'].items() if v == n and p_.startswith(('MAIN', 'POST')))
        _, x, y = MR['pins'][port][0]
        pins[n] = ('metal5', s(XM + x), s(Ym + y))
        g.rect('metal5', XM + x - 0.5, Ym + y - 0.4, XM + x + 0.5, Ym + y + 0.4)
    for i, n in enumerate(T.PORTS):
        if n in ('VDD', 'VSS'):
            for a, b in xbar[n]:
                g.label(n, 'metal5', s((a + b) / 2), s(Yt - 20.0), i + 1)
        else:
            layer, x, y = pins[n]
            g.label(n, layer, x, y, i + 1)
    L.run_tcl(work, NAME, g.tcl(NAME, extra=inst))
    xk = s(xbar['VSS'][1][1] + 0.5)                        # the block's upper part ends here: the top right corner is not used
    poly = [[0, 0], [Wb, 0], [Wb, Ym], [xk, Ym], [xk, Yt], [0, Yt]]
    res = dict(size_um=[Wb, Yt], bbox_area_um2=round(Wb * Yt, 1), used_polygon=poly, used_area_um2=round(Wb * Ym + xk * (Yt - Ym), 1),
               free_corner=dict(box=[xk, Ym, Wb, Yt], area_um2=round((Wb - xk) * (Yt - Ym), 1)),
               seam_um=[Y0, Ym], zones_y=dict(B=yB0, PS=yP0, T=yT0, vss_rail=[yvs, s(yvs + RAIL_VSS)], vdd_rail=[yvd, s(yvd + RAIL_VDD)], buffers=[by0, s(by0 + brow.top)], ph_pins=ypin),
               tracks=dict(F_and_SERQ=nF, PS=nP, metal2=n2), buffer_cell_um=[round(brow.width, 2), round(brow.top, 2)], mux_origin=[XM, Ym], aux_origin=[s(XA - 1.9), Ym],
               ph=tab, decap=dict(fingers=ndec, rows=nrow, per_row=nfin, w=d['w'], l=d['l'], box=[dec_x0, s(Ym + 1.0), dec_x1, dec_y1]),
               pins={n: list(v) for n, v in pins.items()}, supply_bars=xbar, bar_y=[yT0, Yt], em_cuts=em, mux_vss_necks_x=necks, rail_stitches=nst,
               f_wires_um={n: round(m4nets[n][1] - m4nets[n][0], 1) for n in m4nets}, ser_straps_in_rails={k: len(v) for k, v in ext.items()},
               header_strap=dict(y=[yh0, s(Yt - 0.2)], left_end_x=xl_end, right_start_x=xr_start), ser_trunks={n: DC[p_]['lo'] for n, p_ in down_pins.items()})
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
