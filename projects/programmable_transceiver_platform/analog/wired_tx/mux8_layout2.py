"""wtx_mux8 layout, revision 2: low wiring capacitance on MAIN_P / MAIN_N / POST_P / POST_N.  NOT published.

    python3 mux8_layout2.py           # -> scratch/wired_tx/s12/layout/out2  (DRC, LVS, negative control, KLayout DRC)

Same cells, rows, routing and circuit as mux8_layout.py (imported; that file and its out/ are not touched).  Changes:
  * output buses on Metal5 only (BW um wide, BSP um apart; revision 1: Metal3 || Metal4, 0.6 um apart).  Order from the
    stack upwards MAIN_N, MAIN_P, POST_P, POST_N: no MAIN next to a POST of the opposite sign;
    the MAIN pair crosses the fingers directly, the POST pair is reached by Metal4 stubs.
    Metal5 limit used: GF180MCU DRM 14.2, 85 C: 4.5 mA/um unidirectional (Metal1-4: 2.09), as in spec/power-delivery.md
    and scratch/lo-ap4/loext3/em/em_screen.py.
  * stack drain columns: Metal1 + 0.6 um Metal2 over the finger only (revision 1: 1.1 um Metal2 running 18 um under all four
    buses); a via stack to the bus where the bus crosses the finger, else a 0.6 um Metal3 || Metal4 stub up to it.
    VSS Metal2 strips end at the finger; internal-node (S) Metal1 strips 0.4 um.
  * load clusters upside down: the RL pair sits directly above the buses (output head down), then RCM, then the header
    with its VDD rail at the top edge.  Bus -> RL is a short Metal3 || Metal4 strap that passes UNDER the buses above its
    own, between the drain columns of those buses; the cluster positions are searched for that.  The output pins are
    3 um Metal5 risers from the RL heads to the top edge (gate load only).
"""
import json
import shutil
import sys
from pathlib import Path

import mux8
import tools
import mux8_layout as L1
from mux8_layout import s, Geo, TOP, SLICE, ORDER

WORK = L1.WORK / 'rev2'
OUT = L1.WORK / 'out2'
BW, BSP = 3.5, 4.5            # Metal5 bus width / spacing
UPW = 0.6                     # Metal2 width on a drain ('up') column
BUS_ORDER = ('MAIN_N', 'MAIN_P', 'POST_P', 'POST_N')       # from the stack upwards
STUB_M = 4
STUB = 0.8                    # Metal4 stub from a drain column to a bus that does not cross the finger
RISER = 0.75                  # half width of an output pin riser (Metal5)


class Strip2(L1.Strip):
    """revision-2 strips: drain Metal2 only over the finger, VSS Metal2 only to the finger top (the two end columns
    still reach the top tap rail), 0.4 um Metal1 on internal-node columns."""

    def build(self):
        super().build()
        if self.gate_bar:
            return self
        g, yd0, up_to = self.geo, self.yd0, self.top
        ybar = yd0 + self.wmax + 0.3
        self.upw = min(UPW, self.m2w)
        ends = (self.x[0], self.x[-1])
        out = []
        for layer, x1, y1, x2, y2 in g.r:
            xm = s((x1 + x2) / 2)
            i = self.x.index(xm) if xm in self.x else None
            c = self.cols[i] if i is not None else None
            role = self.roles.get(c[1]) if c and c[0] == 'c' else None
            if layer == 'metal2' and role == 'up' and abs(y2 - s(up_to)) < 1e-6 and abs(y1 - yd0) < 1e-6:
                out.append((layer, s(xm - self.upw / 2), y1, s(xm + self.upw / 2), s(yd0 + self.w[i])))
            elif role == 'down' and xm not in ends and self.top_rail and layer == 'metal2' and abs(y2 - s(up_to - 0.3)) < 1e-6:
                out.append((layer, x1, y1, x2, s(yd0 + self.w[i])))
            elif role == 'down' and xm not in ends and self.top_rail and layer == 'via1' and y1 > yd0 + self.wmax:
                pass
            elif layer == 'metal1' and role == 'bar' and abs(y2 - s(ybar + L1.BAR_H)) < 1e-6 and abs(x2 - x1 - 0.6) < 1e-6:
                out.append((layer, s(xm - L1.CW / 2), y1, s(xm + L1.CW / 2), y2))      # contact-wide Metal1 (less facing the drains)
            elif role == 'up' and layer in ('metal1', 'via1') and abs(y1 - yd0) < 0.11 and x2 - x1 < 0.45:
                # drain column: contact-wide Metal1, Via1 (with 0.38 um Metal1 pads) in three short groups
                if layer == 'metal1':
                    out.append((layer, s(xm - L1.CW / 2), y1, s(xm + L1.CW / 2), y2))
                else:
                    wi = self.w[i]
                    for f in ((1, 3, 5) if wi >= 6 else (1, 5) if wi >= 3.2 else (3,)):
                        yc = yd0 + wi * f / 6
                        out.append(('metal1', s(xm - 0.19), s(yc - 0.7), s(xm + 0.19), s(yc + 0.7)))
                        out.append(('via1', s(xm - 0.13), s(yc - 0.6), s(xm + 0.13), s(yc + 0.6)))
            elif role == 'down' and layer == 'metal2' and abs(x2 - x1 - 1.1) < 1e-6 and xm not in ends:
                out.append((layer, s(xm - 0.4), y1, s(xm + 0.4), s(yd0 + 1.6)))        # VSS Metal2 0.8 um, only to the finger foot
            elif role == 'down' and layer == 'via1' and abs(y1 - yd0 - 0.1) < 1e-6 and xm not in ends and x2 - x1 < 0.3:
                out.append((layer, x1, y1, x2, s(yd0 + 1.5)))                          # (Metal1 0.4 um carries the column)
            else:
                out.append((layer, x1, y1, x2, y2))
        g.r = out
        return self


def stack2(P, min_width=0.0, bw=BW):
    nfb = 4 * max(1, round(P['wb'] / 35.0))
    wbf, wtf = P['wb'] / nfb, P['wt'] / (nfb // 2)
    for v in (wbf, wtf):
        if abs(round(v * 200) - v * 200) > 1e-6:
            raise ValueError(f'stack finger width {v} off grid')
    cols, roles = [('c', 'VSS')], dict(VSS='down')
    gt = dict(BMI=0, BQI=1, APM=2, ANM=3, APQ=4, ANQ=5)
    for t, (op, on) in (('M', ('MAIN_P', 'MAIN_N')), ('Q', ('POST_P', 'POST_N'))):
        b_, ap, an, sn = f'B{t}I', f'AP{t}', f'AN{t}', f'S{t}'
        roles.update({sn: 'bar', op: 'up', on: 'up'})
        for d in range(nfb // 4):
            for a, o in ((ap, on), (an, op)):
                cols += [('g', b_, wbf), ('c', sn), ('g', a, wtf), ('c', o), ('g', a, wtf), ('c', sn), ('g', b_, wbf), ('c', 'VSS')]
    st = Strip2('n', cols, gt, roles, min_width=min_width, top_rail=True)
    st.build()
    st.up_to = s(st.yd0 + 0.3 + 4 * bw + 3 * BSP + 0.3)
    st.build()
    st.bw = bw
    st.bus = {n: s(st.yd0 + 0.3 + i * (bw + BSP)) for i, n in enumerate(BUS_ORDER)}
    st.nfb = nfb
    return st, st.devices('mk')


def bus_vias2(self, key):
    """drain columns -> Metal5 bus: via stack where the bus crosses the finger, else a Metal3 || Metal4 stub."""
    st, x0, y0 = self.strips[key]
    for n, yb in self.bus.items():
        for xx in st.col_x.get(n, []):
            i = st.x.index(xx)
            ydt, b0, b1, xc, h = y0 + st.yd0 + st.w[i], y0 + yb, y0 + yb + self.bw, x0 + xx, st.upw / 2
            if min(b1, ydt) - b0 >= 1.5:
                self.g.varr(xc - h, b0 + 0.1, xc + h, min(b1, ydt) - 0.1, 2, 5)
            else:
                ya = max(y0 + st.yd0 + 0.1, ydt - 2.2)
                self.g.varr(xc - h, ya, xc + h, ydt - 0.1, 2, 4)
                self.g.rect(f'metal{STUB_M}', xc - STUB / 2, ya, xc + STUB / 2, b1 - 0.1)       # stub on one layer
                if STUB_M == 3:
                    self.g.varr(xc - STUB / 2, b0 + 0.1, xc + STUB / 2, b1 - 0.1, 3, 4)
                self.g.varr(xc - STUB / 2, b0 + 0.1, xc + STUB / 2, b1 - 0.1, 4, 5)


def m5_bus(blk, ys, W):
    """replace the revision-1 Metal3 || Metal4 bus rectangles of a block by Metal5."""
    ys_ = {s(ys + yb) for yb in blk.bus.values()}
    blk.g.r = [r for r in blk.g.r if not (r[0] in ('metal3', 'metal4') and r[1] == 0 and abs(r[3] - W) < 1e-6 and r[2] in ys_)]
    for yb in blk.bus.values():
        blk.g.rect('metal5', 0, ys + yb, W, ys + yb + blk.bw)


class Slice2(L1.Slice):
    def make(self, P):
        super().make(P)
        m5_bus(self, self.ys, self.W)
        st = self.st
        for n in ('SM', 'SQ'):
            self.g.label(n, 'metal1', st.col_x[n][0], self.ys + st.yd0 + 1.0)

    def route(self):
        # Metal3 columns that pass the bus band (header-gate feeds) keep clear of the drain columns' stubs
        st = self.st
        for n, v in st.col_x.items():
            if st.roles[n] == 'up':
                self.excl += [(xx - STUB / 2 - 0.1, xx + STUB / 2 + 0.1, self.ys + st.yd0 - 0.2, self.H) for xx in v]
        super().route()
        for n in ('ENBM', 'ENBQ'):                       # the top extends a feed through the bus band (in two slices only): must be free
            x, lo, hi = self.pin[n]
            if not self.free_above(x, hi, self.H - 0.2):
                self.cols3 = [c for c in self.cols3 if c[3] != n]
                self.g.r = [r for r in self.g.r if not (r[0] == 'metal3' and abs(r[1] - (x - 0.2)) < 1e-6 and abs(r[4] - hi) < 1e-6)]
                raise RuntimeError(f'feed {n} blocked')

    def free_above(self, x, lo, hi):
        if any(x + 0.5 > a and x - 0.5 < b and hi + 0.3 > c and lo - 0.3 < d for a, b, c, d in self.excl):
            return False
        return not any(abs(cx - x) < 0.72 and cx != x and lo - 0.5 < b and a - 0.5 < hi for cx, a, b, _ in self.cols3)


def patch():
    L1.Strip = Strip2
    L1.stack = stack2
    L1.Block.bus_vias = bus_vias2


def place_clusters(sl, X0, hw, cx):
    """cluster centre, RLP side and strap half width per bank such that every bus -> RL strap (Metal3 || Metal4, under
    the buses above its own) clears the drain columns of those buses; taps as close to the array centre as possible."""
    W, st = sl.W, sl.st
    xc = X0 + 4 * W
    above = {n: BUS_ORDER[i + 1:] for i, n in enumerate(BUS_ORDER)}
    colx = {n: [X0 + p * W + x for p in range(8) for x in st.col_x[n]] for n in BUS_ORDER}

    def half(n, x):
        for sw in (3.0,):          # 6 um of Metal3 || Metal4: 0.83 mA/um random, 1.67 static
            if all(abs(x - c) >= sw + STUB / 2 + 0.35 for m in above[n] for c in colx[m]):
                return sw
        return None
    cand = {}
    for tag, op, on in (('M', 'MAIN_P', 'MAIN_N'), ('Q', 'POST_P', 'POST_N')):
        cand[tag] = []
        for k in range(int((8 * W - 2 * hw) / 0.05)):
            xb = s(X0 + hw + 1.0 + k * 0.05)
            for sd in (-1, 1):
                a, b = half(op, xb + sd * 10.0), half(on, xb - sd * 10.0)
                if a and b:
                    cand[tag].append((xb, sd, a, b))
    best = None
    for m in cand['M']:
        for q in cand['Q']:
            if q[0] - m[0] < 2 * cx:
                continue
            cost = max(abs(m[0] - 10 - xc), abs(m[0] + 10 - xc), abs(q[0] - 10 - xc), abs(q[0] + 10 - xc)) - 0.01 * (m[2] + m[3] + q[2] + q[3])
            if best is None or cost < best[0]:
                best = (cost, m, q)
    if best is None:
        raise RuntimeError('no load cluster position clears the drain columns')
    return best[1], best[2]


def build_top(P=None, neg=True, kl=True, work=None, out=True):
    patch()
    P = dict(mux8.P, **(P or {}))
    work = Path(work or WORK)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    sl = Slice2(P)
    L1.run_tcl(work, SLICE, sl.g.tcl(SLICE))
    ri = L1.gen_res(work, P)
    cap = L1.Cap(P, sl)
    m5_bus(cap, cap.ys, cap.W)
    X0, W, H, ys, st = cap.W, sl.W, sl.H, sl.ys, sl.st
    xs = lambda p_: s(X0 + p_ * W)
    g = Geo()
    g.place(cap.g)
    inst = []
    for p_, k in enumerate(ORDER):
        inst += [f'getcell {SLICE} child 0 0 parent {xs(p_)} 0', f'identify XS{k}']
    em = {}
    for name, po, pi in (('BM', 'BMO', 'BMI'), ('BQ', 'BQO', 'BQI'), ('UP', 'UPI', 'UPO'), ('VP', 'VPI', 'VPO')):
        xa, xb = sl.pin[po][0], sl.pin[pi][0]
        for k, d, r, lo, hi, tr in L1.ring_plan():
            y = s(sl.ring_y[name] + tr * L1.RT_P[name])
            g.rect('metal4', xs(lo) + min(xa, xb) - 0.2, y - 0.2, xs(hi) + max(xa, xb) + 0.2, y + 0.2)
            g.via(xs(d) + xa, y, 3, 4)
            g.via(xs(r) + xb, y, 3, 4)
            g.label(f'{name}{(k - 1) % 8}', 'metal4', xs(lo) + min(xa, xb) + 0.5, y)
    y_vdd = [sl.rows['in'][1], sl.rows['preQ'][1]]
    y_vss = [0.0, sl.rows['preM'][1]]
    for p_ in range(9):
        xb = xs(p_)
        g.rect('metal5', xb - L1.VSS_W / 2, 0, xb + L1.VSS_W / 2, ys + st.rail_h)
        for yr in y_vss:
            g.varr(xb - L1.VSS_S, yr + 0.05, xb + L1.VSS_S, yr + 0.55, 2, 5)
        em['vss_strap_cuts'] = g.varr(xb - L1.VSS_W / 2 + 0.2, ys + 0.2, xb + L1.VSS_W / 2 - 0.2, ys + st.rail_h - 0.2, 2, 5)
    for p_ in range(8):
        xv = xs(p_) + sl.vdd_x
        g.rect('metal5', xv - L1.VDD_W / 2, 0, xv + L1.VDD_W / 2, y_vdd[1] + 0.9)
        for yr in y_vdd:
            g.varr(xv - L1.VDD_S, yr + 0.05, xv + L1.VDD_S, yr + 0.55, 2, 5)
    # ---- loads, upside down: RL pair (output head down) / TOP plate / RCM / TOP2 plate / header (VDD rail at the top edge)
    xc = X0 + 4 * W
    nfh = L1.nfing(P['hdr'], 3.2)
    while nfh % 2 or abs(round(P['hdr'] / nfh * 200) - P['hdr'] / nfh * 200) > 1e-6:
        nfh += 1
    wh = P['hdr'] / nfh
    hw = s(nfh * 0.44 + 0.6)
    cx = s(hw + 1.9)
    pm, pq = place_clusters(sl, X0, hw, cx)
    net = list(cap.net)
    ports, taps, straps = {}, {}, []
    rl, rc = ri['wtx_mx_rl'], ri['wtx_mx_rcm']
    yA = s(H + 2.4)                                     # lower edge of the RL output pads
    yl = s(yA + 2.0 + rl['py'])                         # RL centre
    yw0 = s(yl + rl['py'] + 0.3)
    yr = s(yw0 + 2.3 + rc['py'])                        # RCM centre
    yh = s(yr + rc['py'] + 1.3)                         # header: ends of its drain strips
    feeds = []
    for bi, (tag, (xb, sd, swp, swn), enb, op, on) in enumerate((('M', pm, 'ENBM', 'MAIN_P', 'MAIN_N'), ('Q', pq, 'ENBQ', 'POST_P', 'POST_N'))):
        top2, topn = f'TOP2{tag}', f'TOP{tag}'
        cols = [('c', 'VDD')]
        for f in range(nfh):
            cols += [('g', enb, wh), ('c', top2 if f % 2 == 0 else 'VDD')]
        hs = L1.Strip('p', cols, {}, {'VDD': 'down', top2: 'up'}, rail_h=3.0, gate_bar=True)
        hs.build()
        hx0 = s(xb - (hs.x[0] + hs.x[-1]) / 2)
        g.place(hs.geo, hx0, yh, hs.top)
        ytop = s(yh + hs.top)
        net += hs.devices(f'hp{tag}')
        inst += [f'getcell wtx_mx_rcm child 0 0 parent {s(xb)} {yr}', f'identify XRCM{tag}']
        xu = hs.col_x[top2]
        for m in (1, 2):                                # TOP2 plate: RCM upper head -> header drains
            g.rect(f'metal{m}', xb - rc['hx'], yr + rc['c1'][0] - 0.1, xb + rc['hx'], yh - 1.0)
            g.rect(f'metal{m}', hx0 + xu[0] - 0.3, yh - 1.0, hx0 + xu[-1] + 0.3, yh + 0.2)
        g.rect('via1', hx0 + xu[0], yh - 0.9, hx0 + xu[-1], yh - 0.1)
        for m in (1, 2):                                # TOP plate: RL upper heads -> RCM lower head
            g.rect(f'metal{m}', xb - rc['hx'], yw0, xb + rc['hx'], yr + rc['c0'][1] + 0.1)
        g.rect('via1', xb - rc['hx'] + 0.1, yw0 + 0.1, xb + rc['hx'] - 0.1, yw0 + 1.9)
        g.label(topn, 'metal1', xb, yw0 + 1.0)
        g.label(top2, 'metal1', xb, yh - 0.5)
        for o, xr, sw in ((op, s(xb + sd * 10.0), swp), (on, s(xb - sd * 10.0), swn)):
            inst += [f'getcell wtx_mx_rl child 0 0 parent {xr} {yl}', f'identify XRL{o[-1]}{tag}']
            for m in (1, 2):
                g.rect(f'metal{m}', xr - rl['hx'], yl + rl['c1'][0] - 0.1, xr + rl['hx'], yw0)
            # output pad under the lower head (Metal1 .. Metal4), strap Metal3 || Metal4 down to the bus, Via4 onto it
            g.rect('metal1', xr - rl['hx'], yA, xr + rl['hx'], yl + rl['c0'][1] + 0.1)
            g.varr(xr - rl['hx'], yA, xr + rl['hx'], yl - rl['py'] - 0.3, 1, 2)
            em['rl_pad_cuts'] = g.varr(xr - sw, yA, xr + sw, yl - rl['py'] - 0.3, 2, 4)
            yb = ys + sl.bus[o]
            for m in (3, 4):
                g.rect(f'metal{m}', xr - sw, yb + 0.1, xr + sw, yA + 0.5)
            own = sorted(c for c in [xs(p_) + x for p_ in range(8) for x in st.col_x[o]] if xr - sw - 0.5 < c < xr + sw + 0.5)
            edges = [xr - sw] + [v for c in own for v in (c - 0.5, c + 0.5)] + [xr + sw]      # Via4 between the net's own column stacks
            em['bus_tap_cuts'] = sum(g.varr(max(a_, xr - sw), yb + 0.1, min(b_, xr + sw), yb + sl.bw - 0.1, 4, 5)
                                     for a_, b_ in zip(edges[::2], edges[1::2]) if min(b_, xr + sw) - max(a_, xr - sw) > 0.6)
            # pin: Metal5 riser from the pad to the top edge
            g.varr(xr - RISER, yA + 0.1, xr + RISER, yA + 1.5, 4, 5)
            g.rect('metal5', xr - RISER, yA + 0.1, xr + RISER, ytop)
            ports[o] = ('metal5', xr, ytop - 0.5)
            taps[o] = (xr, sw)
            straps.append((xr - sw - 0.7, xr + sw + 0.7))
        net += [f'XRCM{tag} {top2} {topn} VSS ppolyf_u r_width={P["rcm"][0]}u r_length={P["rcm"][1]}u',
                f'XRLP{tag} {topn} {op} VSS ppolyf_u r_width={P["rl"][0]}u r_length={P["rl"][1]}u',
                f'XRLN{tag} {topn} {on} VSS ppolyf_u r_width={P["rl"][0]}u r_length={P["rl"][1]}u']
        # header VDD: Metal3 .. Metal5 on the rail (top edge), open where the two output risers pass
        cuts = sorted([xb - 10.0 - RISER - 0.7, xb - 10.0 + RISER + 0.7, xb + 10.0 - RISER - 0.7, xb + 10.0 + RISER + 0.7])
        for a, b in ((hx0, cuts[0]), (cuts[1], cuts[2]), (cuts[3], hx0 + hs.width)):
            g.varr(a + 0.2, ytop - hs.rail_h + 0.2, b - 0.2, ytop - 0.2, 2, 5)
            ports.setdefault('VDD', []).append(('metal5', s((a + b) / 2), ytop - 1.5))
        for xt in [s(xb - hw - 1.3)] + ([s(xb + hw + 2.5)] if tag == 'Q' else []):
            g.rect('psubdiff', xt - 0.25, H + 0.5, xt + 0.25, ytop)
            g.rect('psubdiffcont', xt - 0.115, H + 0.635, xt + 0.115, ytop - 0.135)
            g.rect('metal1', xt - 0.2, H - 1.0, xt + 0.2, ytop)
        feeds.append((bi, enb, s(hx0 + hs.pad[0]), s(yh + hs.top - hs.pad[1])))
        em[f'hdr_{tag}'] = dict(fingers=nfh, w=wh)
    for bi, enb, px, py in feeds:       # header gate: slice feed column (Metal3 through the bus band) -> Metal2 jog -> poly pad
        fx = sl.pin[enb][0]
        cand = [xs(p_) + fx for p_ in range(8) if not any(a < xs(p_) + fx < b for a, b in straps)]
        xf = min(cand, key=lambda v: abs(v - px))
        yj = s(H + 0.6 + 0.8 * bi)
        g.rect('metal3', xf - 0.2, sl.pin[enb][2] - 0.4, xf + 0.2, yj + 0.2)
        g.via(xf, yj, 2, 3)
        g.rect('metal2', min(xf, px) - 0.2, yj - 0.2, max(xf, px) + 0.2, yj + 0.2)
        g.rect('metal2', px - 0.2, yj - 0.2, px + 0.2, py + 0.2)
        g.via(px, py, 1, 2)
    Htop = ytop
    for p_, k in enumerate(ORDER):
        for n, name in [('PH', f'PH{k}'), ('F', f'F{k}')] + [(f'TR{b}', f'TR{k}_{b}') for b in range(3)]:
            ports[name] = ('metal3', xs(p_) + sl.pin[n][0], 0.2)
    for n in ('ENM', 'ENP', 'POL', 'EN_MAIN', 'EN_POST'):
        ports[n] = ('metal3', cap.pin[n][0], 0.2)
    ports['VDD'].append(('metal5', xs(0) + sl.vdd_x, 1.0))
    ports['VSS'] = ('metal5', xs(1), 1.0)
    for i, n in enumerate(mux8.PORTS):
        for layer, x, y in (ports[n] if isinstance(ports[n], list) else [ports[n]]):
            g.rect(layer, x - 0.2, y - 0.2, x + 0.2, y + 0.2)
            g.label(n, layer, x, y, i + 1)
    L1.run_tcl(work, TOP, g.tcl(TOP, extra=inst))
    sch = '* reference: mux8.netlist()\n' + mux8.netlist(P)
    res = L1.check(work, TOP, sch)
    res.update(size_um=[s(xs(8) + L1.VSS_W / 2), s(Htop)], area_um2=round((xs(8) + L1.VSS_W / 2) * Htop, 1),
               slice_um=[W, H], cap_um=[X0, H], loads_um=[s(pq[0] - pm[0] + 2 * hw + 0.6), s(Htop - H)],
               clusters=dict(M=pm, Q=pq))
    res['wire_c_fF'] = caps(work / f'{TOP}.ext.spice')
    nfb, bw = st.nfb, sl.bw
    row = lambda i, w_, lim=2.09: dict(mA=round(i, 3), metal_um=round(w_, 2), mA_per_um=round(i / w_, 2),
                                         static_ones_mA_per_um=round(2 * i / w_, 2), drm_limit=lim)
    frac = lambda xt: max((xt - X0) / W, 8 - (xt - X0) / W) * 20.0 / 16
    t = {f'{n} bus worst segment (Metal5 {bw} um)': row(frac(taps[n][0]), bw, 4.5) for n in BUS_ORDER}
    t.update({f'{n} bus -> RL strap (Metal3+4)': row(10.0, 4 * taps[n][1]) for n in BUS_ORDER})
    t.update({'drain column (Metal2 0.6 over contact-wide Metal1, 2 fingers)': row(2 * 20.0 / (nfb // 2) / 16, UPW),
              'drain stub to an upper bus (Metal4)': row(2 * 20.0 / (nfb // 2) / 16, STUB),
              'S column (Metal1 0.23)': dict(mA=round(20.0 / nfb / 8, 3), metal_um=0.23, mA_per_um=round(20.0 / nfb / 8 / 0.23, 2)),
              'stack VSS column (Metal1 0.4 over the finger, Metal2 0.8 below)': dict(mA=round(2 * 2.5 / nfb, 3), metal_um=0.4, mA_per_um=round(2 * 2.5 / nfb / 0.4, 2)),
              'RL output pad (Metal1+2 tongue)': row(10.0, 2 * 2 * rl['hx']),
              'header VDD (Metal5 on the rail, top edge)': dict(mA=20.0, metal_um=round(2 * hw - 2 * (2 * RISER + 1.4), 1)),
              'unchanged from revision 1': 'stack VSS column / rail / Metal5 straps, S bar, TOP / TOP2 plates, header columns, logic rails',
              'cuts': dict(rl_pad_stack=em['rl_pad_cuts'], bus_tap_via4=em['bus_tap_cuts'], vss_strap_stack=em['vss_strap_cuts'])})
    res['em_table'] = t
    if neg:
        bad = '\n'.join(l.replace(' F0 ', ' F1 ') if l.startswith('XGF_0') else l for l in sch.splitlines()) + '\n'
        (work / 'neg.sch.spice').write_text(bad)
        res['lvs_negative_control'] = L1.netgen(work, f'{TOP}.lvs.spice', TOP, 'neg.sch.spice', TOP, out=f'{TOP}-lvs-neg.txt')
    if kl:
        res['klayout_drc'] = tools.klayout_drc(work, tools.gds_export_analog(work, TOP), TOP)
    (work / 'report.json').write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))
    if out:
        OUT.mkdir(parents=True, exist_ok=True)
        for f in [f'{TOP}.mag', f'{SLICE}.mag', 'wtx_mx_rl.mag', 'wtx_mx_rcm.mag', f'{TOP}.gds', f'{TOP}.ext.spice', f'{TOP}.lvs.spice',
                  f'{TOP}.sch.spice', f'{TOP}-lvs.txt', f'{TOP}-lvs-neg.txt', 'drc-count.txt', 'drc-details.txt', 'report.json']:
            if (work / f).exists():
                shutil.copy(work / f, OUT / f)
    return res


def caps(path):
    """wiring capacitance (fF, ground + coupling, no device capacitance) from the flat Magic netlist: totals of the
    output nets with their largest partners, S / TOP nets, and the per-phase values of the phase-path nets."""
    tot, pair = {}, {}
    for l in Path(path).read_text().splitlines():
        if l.startswith('C'):
            tk = l.split()
            u = {'f': 1.0, 'p': 1e3, 'a': 1e-3, 'n': 1e6}.get(tk[3][-1])
            v = float(tk[3][:-1]) * u if u else float(tk[3]) * 1e15
            for a, b in ((tk[1], tk[2]), (tk[2], tk[1])):
                tot[a] = tot.get(a, 0.0) + v
                if a in BUS_ORDER:
                    key = b if b in BUS_ORDER + ('VSS', 'VDD') else 'slice S nodes' if b.endswith(('/SM', '/SQ')) else 'other'
                    pair.setdefault(a, {})[key] = pair.setdefault(a, {}).get(key, 0.0) + v
    out = {n: dict(total=round(tot.get(n, 0.0), 1), to={k: round(v, 1) for k, v in sorted(pair.get(n, {}).items(), key=lambda kv: -kv[1])})
           for n in BUS_ORDER}
    for n in ('TOPM', 'TOPQ', 'TOP2M', 'TOP2Q'):
        out[n] = round(tot.get(n, 0.0), 1)
    for n in ('SM', 'SQ', 'Y', 'Z', 'X', 'XTM', 'XTQ', 'APM', 'ANM', 'APQ', 'ANQ', 'EM', 'EQ'):
        out[n] = [round(tot.get(f'XS{k}/{n}', 0.0), 2) for k in range(8)]
    for n in ('BM', 'BQ', 'UP', 'VP'):
        out[n] = [round(tot.get(f'{n}{k}', 0.0), 2) for k in range(8)]
    return out


if __name__ == '__main__':
    if 'var' in sys.argv:
        build_top(dict(wb=80.0, wt=40.0, nor=(4, 40), i1=(24, 48), i3=(32, 12), hdr=176.0, tg=(8, 20)), work=WORK.parent / 'var2', out=False,
                  kl=False, neg=False)
    else:
        build_top()
