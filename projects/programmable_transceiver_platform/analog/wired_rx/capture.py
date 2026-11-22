"""pt_wrx_cap: wired-RX fast 1:N capture front end (slot demultiplexer), built from compact rows.

Rows are compiled with wrx_compact (a copy of analog/timing/compact.py with gap-track sharing); the
TSPC flop, NAND and helper column patterns are timing's (fastcells._tspc_cols).

Function (one ring cycle = CKP0 period T; CK = CKP0 gated by EN, CKN = !CK, low when disabled):
  * front (wc_front): sampler output S_j (latched by pt_slicer at phase j, valid one period) is first
    captured by the opposite ring phase CKP(j+4) (half a period after its own sampling clock, so the
    capture is independent of the slicer delay), then aligned:
        j=0     : CK rise -> CK rise          j=1..4: CK fall -> CK rise          j=5..7: CK rise
    so the octet O0..O7 of ring cycle m is valid for one period from the CK rise two cycles later.
  * lanes (wc_lane): DL0..3 / EL0..3 by mode (one-hot BQ/BH/BF):
        quarter: DLj = O(2j), ELj = O(2j+1)
        half   : DL0=DL2=O0, DL1=DL3=O4; EL0=EL2=O2, EL1=EL3=O6
        full   : every DLj = O[psel], ELj = O[psel+4]  (psel one-hot PS0..7, shadowed at the word load)
  * word restart (wc_cnt): LDE re-registered twice on CK (INJ).
  * slots (wc_slot0/1 one-hot enable chain, wc_pair x20): bit pair i (DW_i, EW_i) takes lane i mod 4;
    its slot enable ELQ_i is its predecessor's (i-4 quarter, i-2 half, i-1 full; INJ for slot 0)
    registered on CK rise, and gates CKN (GCK_i), so the two slot flops R clock once per word.
    (r2, 2026-11-09: replaces r1's binary /5,/10,/20 counter and global slot decode, too slow
    extracted above 480 MHz.)
  * word: pair 19 is in the last slot in every mode; its enable ELQ19, through a latch transparent
    while CK is low (ELW), gates CK (GW): the word flops W take all R at the CK rise after the last
    slot, half a period before slot 0 of the next word.  DW/EW are buffered W outputs, stable for one word.
  * slip (full rate): SLIPP/SLIPM and the one-hot phase select are shadowed at GW; the slip of the
    word being captured is presented as SLP/SLM with that word at the next GW.
EN=0: CK/CKN low, every flop reset (outputs 0), inputs only see gate loads.
"""
from pathlib import Path
import json
import shutil
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'timing'))
sys.path.insert(0, str(HERE))
import wrx_compact as compact                     # noqa: E402
import layout_engine as le                        # noqa: E402
import fastcells as fc                            # noqa: E402

C, G, BRK, fet = fc.C, fc.G, fc.BRK, fc.fet
S_ = C('VSS', 'VDD', same=False)
FAST = HERE / 'generated' / 'fast'
GEN = HERE / 'generated'          # r7: staging drivers point FAST/SCRATCH/GEN at scratch and publish only when clean
SCRATCH = HERE.parents[3] / 'scratch' / 'wired_rx' / 'cap'


class Cell:
    def __init__(self, name):
        self.name, self.cols, self.net, self.k = name, [], [], 0

    def _add(self, cols, net):
        if self.cols:
            self.cols.append(BRK)
        self.cols += cols
        self.net += net
        self.groups = getattr(self, 'groups', []) + [(list(cols), list(net))]

    def pre(self):
        self.k += 1
        return f'u{self.k}_'

    def inv(self, a, y, wn=2, wp=4):
        p = self.pre()
        self._add([S_, G(a, wn, wp), C(y)], [fet(p + 'n', y, a, 'VSS', 'VSS', wn), fet(p + 'p', y, a, 'VDD', 'VDD', wp, 'p')])

    def buf(self, a, y, mid=None):
        mid = mid or f'{y}_b'
        self.inv(a, mid, 1, 2)
        self.inv(mid, y, 2, 4)

    def bufx(self, a, y):
        """Strong buffer for a long routed net (2/4 -> 2 x 4/8)."""
        mid = f'{y}_x'
        self.inv(a, mid, 2, 4)
        self.inv(mid, y, 4, 8)
        self.inv(mid, y, 4, 8)

    def nand(self, ins, y, wn=None, wp=2):
        p = self.pre()
        n = len(ins)
        wn = wn or {1: 2, 2: 2, 3: 3, 4: 4}[n]
        cols = [S_]
        net = []
        for k, a in enumerate(ins):
            cols.append(G(a, wn, wp))
            last = k == n - 1
            pnet = 'VDD' if k % 2 else y
            if last:
                cols.append(C(y, 'VDD' if (k + 1) % 2 == 0 else y, same=False))
            else:
                cols.append(dict(k='c', n=None, p=pnet))
            d = y if last else f'{p}m{k}'
            s = 'VSS' if k == 0 else f'{p}m{k - 1}'
            net += [fet(f'{p}n{k}', d, a, s, 'VSS', wn), fet(f'{p}p{k}', y, a, 'VDD', 'VDD', wp, 'p')]
        self._add(cols, net)

    def nor2(self, a, b, y, wn=2, wp=4):
        p = self.pre()
        cols = [S_, G(a, wn, wp), dict(k='c', n=y, p=None), G(b, wn, wp), C('VSS', y, same=False)]
        net = [fet(p + 'n1', y, a, 'VSS', 'VSS', wn), fet(p + 'n2', y, b, 'VSS', 'VSS', wn),
               fet(p + 'p1', p + 'm', a, 'VDD', 'VDD', wp, 'p'), fet(p + 'p2', y, b, p + 'm', 'VDD', wp, 'p')]
        self._add(cols, net)

    def ff(self, ck, d, q, keep=False):
        """TSPC D flip-flop (rising ck), Q = NOR(QB, ENB) (timing's ct_tspcd pattern).
        keep: weak (1/1 um) keeper QB = NOR(Q, ENB), so QB is held statically while ck is low.  For
        flops clocked once per word (r2e): their QB otherwise floats for 5..20 periods, and extracted
        at ss it drifted to mid-rail (EW16 near VDD/2 mid-word).  NOR with ENB (not an inverter) so
        the keeper agrees with the reset NMOS when EN=0 (an inverter would fight it statically)."""
        p = self.pre()
        cols, net = fc._tspc_cols(ck, d, q, p + 'QB', p + 'X', p + 'Y', p)
        self._add(cols, net)
        if keep:
            self.nor2(q, 'ENB', p + 'QB', 1, 1)

    def diode(self, net, k=1):
        """r6 (antenna, KLayout ANT.16_i_ANT.3 = M2): k contact columns of bare N+ diffusion on `net` (an N+/Psub
        protection diode; no device, so LVS is unchanged).  For gate-only input ports with long in-cell M2."""
        self._add([dict(k='c', n=net, p='-') for _ in range(k)], [])

    def aoi3(self, pairs, y):
        """y = a0&b0 | a1&b1 | a2&b2 (NAND2 x3 -> NAND3)."""
        zs = []
        for a, b in pairs:
            z = f'{y}_z{len(zs)}'
            self.nand([a, b], z)
            zs.append(z)
        self.nand(zs, y)

    def reverse_groups(self):
        """Mirror the placement order of the gate groups (each group keeps its own column order)."""
        groups, cur = [], []
        for col in self.cols:
            if col is BRK:
                groups.append(cur)
                cur = []
            else:
                cur.append(col)
        groups.append(cur)
        self.cols = []
        for g_ in reversed(groups):
            if self.cols:
                self.cols.append(BRK)
            self.cols += g_
        self.groups = list(reversed(getattr(self, 'groups', [])))

    def row(self, ports, track_order=None):
        r = compact.Row(self.name, self.cols, ports=ports, wn=2, wp=4)
        if track_order:
            r.track_order = track_order
        r._cell = self
        return r, ports + ['VDD', 'VSS'], self.net


# ----------------------------------------------------------------------------------------- cells
# ======================================================================================== r7f (r12, 2026-11-20)
# Timing rules of r7f (scratch/wired_rx/r12/cap, review scratch/wired_rx/r11/review/capture/REVIEW.md):
#   * one capture-side clock edge per domain: front = ring phases (EN-gated local leaves), back end = CK RISING only (no
#     CKN-edge flops, no half-period hand-offs).  Gated clocks are latch-based (ICG: enable latched while CK is low).
#   * every flop-to-flop hop is clk->q + at most ~2 gate stages + local wire (TSPC clk->q 222 ps ff .. 409 ps pessimistic ss;
#     AOI3 187 .. 345 ps; char/ in r12/cap): fits one ring period at 810 MHz pessimistic with >= 10 % slack.  Long routes get a
#     buffer and no logic in that hop.  Same-edge hops without logic get an inverter pair (hold >= 10 % of 480 MHz at ff).
#   * front retiming by ring-phase hops of 6/8 or 7/8 period only (r7e had 4/8 hops: B->Z, F4->B4, F0->A0) or 8/8 + pad.
XPAD = 1      # inverter pairs on the O -> OC crossing (lane), tuned on the extracted hop measurement
LPAD = 2      # inverter pairs after the lane flops (DL/EL -> pair R hold)


def _pad(c, a, y, n=1):
    """n inverter pairs (2/4) a -> y (hold padding)."""
    prev = a
    for k in range(n):
        nxt = y if k == n - 1 else f'{y}_p{k}'
        c.inv(prev, f'{y}_i{k}', 2, 4)
        c.inv(f'{y}_i{k}', nxt, 2, 4)
        prev = nxt
    return y if n else a


def _latch(c, d, ck, ckn, q):
    """Static latch, transparent while ck is low (ckn high), holds while ck is high (r2b's ELW latch + consensus term)."""
    c.nand([d, ckn], f'{q}_l1')
    c.nand([q, ck], f'{q}_l2')
    c.nand([d, q], f'{q}_l3')
    c.nand([f'{q}_l1', f'{q}_l2', f'{q}_l3'], q)


def _icg(c, en, ck, ckn, y, strong=True):
    """Latch-based clock gate: y = ck & (en latched while ck low).  en must be a CK-rise flop output (padded)."""
    _latch(c, en, ck, ckn, f'{y}L')
    c.nand([ck, f'{y}L'], f'{y}B', 4, 4)
    c.inv(f'{y}B', y, 4, 8)
    if strong:
        c.inv(f'{y}B', y, 4, 8)


def _leaf(c, ck, y):
    """CK leaf buffer (2/4 -> 2 x 4/8), the same in every back-end cell."""
    c.bufx(ck, y)


def pair():
    """Bit pair i: slot flops R on the gated clock GCK (one CK-rise pulse per word, from wc_slot), word flops W on GW.
    r7f: R keeps (clocked once per word); R -> W through an inverter pair (W loads on the same edge on which slot 0 of the
    next word rewrites R0..3)."""
    c = Cell('wc_pair')
    c.diode('GCK')
    c.buf('GCK', 'GCL')
    c.ff('GCL', 'DLN', 'RD', keep=True)
    c.ff('GCL', 'ELN', 'RE', keep=True)
    _pad(c, 'RD', 'RDp')
    _pad(c, 'RE', 'REp')
    c.buf('GW', 'GWL')
    c.ff('GWL', 'RDp', 'DWq', keep=True)
    c.ff('GWL', 'REp', 'EWq', keep=True)
    c.bufx('DWq', 'DW')
    c.bufx('EWq', 'EW')
    return c.row(['GCK', 'GW', 'DLN', 'ELN', 'ENB', 'DW', 'EW'])


def cnt():
    """Word restart (r7d edge detect kept): INJ = registered rising edge of the EN-gated, stretched LDE.  r7f: inverter pair
    on the INJ1 -> INJ2 shift and on INJ2 into the edge NOR (hold)."""
    c = Cell('wc_cnt')
    _leaf(c, 'CK', 'CKM')
    c.inv('ENB', 'ENC', 1, 2)
    c.nand(['LDE', 'ENC'], 'LDGB')
    c.inv('LDGB', 'LDS1', 1, 2)
    c.inv('LDS1', 'LDS2', 1, 2)
    c.inv('LDS2', 'LDS3', 1, 2)
    c.inv('LDS3', 'LDGD', 1, 2)
    c.nand(['LDGB', 'LDGD'], 'LDG')
    c.ff('CKM', 'LDG', 'INJ1')
    _pad(c, 'INJ1', 'INJ1p')
    c.ff('CKM', 'INJ1p', 'INJ2')
    _pad(c, 'INJ2', 'INJ2p')
    c.inv('INJ1', 'INJ1B', 1, 2)
    c.nor2('INJ1B', 'INJ2p', 'INJD')
    c.ff('CKM', 'INJD', 'INJQ')
    c.bufx('INJQ', 'INJ')
    return c.row(['CK', 'ENB', 'LDE', 'INJ'])


def _pred(i):
    """Predecessor enables of pair i (quarter, half, full): the pair one slot earlier, INJS for slot 0."""
    return tuple(f'ELQ{i - k}' if i >= k else 'INJS' for k in (4, 2, 1))


def slot(half):
    """One-hot slot-enable chain (CK rise) + latch clock gates.  ELQ_i <= BQ&ELQ_(i-4) | BH&ELQ_(i-2) | BF&ELQ_(i-1) (INJS for
    slot 0, INJS = INJ re-registered here).  Hop: flop -> AOI3 -> flop, unbuffered, neighbours only.  GCK_i = CK & latched
    ELQ_i: pair i's R flops load on the CK rise one period after ELQ_i rises.
    slot1 also: ELQ20 (= ELQ19 one cycle later) -> GW (word load, the CK rise on which slot 0 of the next word loads);
    GP = CK & latched ELQ15: phase-select / slip shadow (full rate: the new PS reaches the lane mux exactly at slot 0 of the
    next word: PS (GP) -> PS2 (lane, every cycle) -> DFa -> DFr -> DLr -> R); SLP/SLM with the word on GW."""
    c = Cell(f'wc_slot{half}')
    lo = 10 * half
    if half == 0:
        _leaf(c, 'CK', 'CKS')
        c.ff('CKS', 'INJ', 'INJS')
    for i in range(lo, lo + 10):
        if i % 5 == 0:
            _leaf(c, 'CK', f'CKL{i // 5}')
            c.buf('CKN', f'CNL{i // 5}')
        ck, cn = f'CKL{i // 5}', f'CNL{i // 5}'
        q, h, f_ = _pred(i)
        if i == 0:
            d = _pad(c, 'INJS', 'INJSp')     # r7f: hold (ff 480: 138 ps without)
        else:
            c.aoi3([('BQ', q), ('BH', h), ('BF', f_)], f'E{i}')
            d = f'E{i}'
        c.ff(ck, d, f'ELQ{i}')
        _pad(c, f'ELQ{i}', f'ELP{i}')
        _icg(c, f'ELP{i}', ck, cn, f'GCK{i}')
    xin = ['ELQ6', 'ELQ7', 'ELQ8', 'ELQ9']
    extra_in, extra_out = [], []
    if half:
        for n in xin:
            c.diode(n)
        _leaf(c, 'CK', 'CKW')
        c.buf('CKN', 'CNW')
        _pad(c, 'ELQ19', 'ELQ19p')
        c.ff('CKW', 'ELQ19p', 'ELQ20')
        _pad(c, 'ELQ20', 'ELP20')
        _latch(c, 'ELP20', 'CKW', 'CNW', 'ELW')
        c.nand(['CKW', 'ELW'], 'GWB', 4, 4)
        c.inv('GWB', 'GWX', 4, 8)
        c.inv('GWB', 'GWX', 4, 8)
        for _ in range(4):
            c.inv('GWX', 'GWY', 4, 8)       # inverting stage pair keeps GW = CK & ELW polarity
        for _ in range(4):
            c.inv('GWY', 'GW', 4, 8)
        c.inv('GWY', 'GWT', 4, 8)
        c.buf('GW', 'GWL')
        _icg(c, 'ELP15', 'CKW', 'CNW', 'GP', strong=False)
        extra_out = ['GW', 'GWT', 'GP']
    if half:          # r7f floorplan: slot1 sits below slot0's right end mirrored, so ELQ6..9 -> pairs 10..13 stay short
        c.reverse_groups()
    ports = ['CK', 'CKN', 'ENB', 'BQ', 'BH', 'BF'] + (xin if half else ['INJ']) + extra_in + \
        [f'GCK{i}' for i in range(lo, lo + 10)] + ([] if half else xin) + extra_out
    return c.row(ports)


def word():
    """r7f: phase-select and slip shadow registers (on GP, from wc_slot1) and the slip tags presented with the word (on GW)."""
    c = Cell('wc_word')
    c.buf('GP', 'GPL0')
    c.buf('GP', 'GPL1')
    c.buf('GP', 'GPL2')
    c.buf('GW', 'GWL')
    for b in range(3):
        c.inv(f'PSEL{b}', f'PN{b}', 1, 2)
    for k in range(8):
        bits = [(f'PSEL{b}' if (k >> b) & 1 else f'PN{b}') for b in range(3)]
        c.nand(bits, f'PD{k}B')
        c.inv(f'PD{k}B', f'PD{k}', 1, 2)
        c.ff(f'GPL{k // 4}', f'PD{k}', f'PSq{k}', keep=True)
        c.bufx(f'PSq{k}', f'PS{k}')
    c.ff('GPL2', 'SLIPP', 'SPQ', keep=True)
    c.ff('GPL2', 'SLIPM', 'SMQ', keep=True)
    _pad(c, 'SPQ', 'SPQp')
    _pad(c, 'SMQ', 'SMQp')
    c.ff('GPL2', 'SPQp', 'SPQ2', keep=True)
    c.ff('GPL2', 'SMQp', 'SMQ2', keep=True)
    c.ff('GWL', 'SPQ2', 'SLPq', keep=True)
    c.ff('GWL', 'SMQ2', 'SLMq', keep=True)
    c.bufx('SLPq', 'SLP')
    c.bufx('SLMq', 'SLM')
    return c.row(['GP', 'GW', 'ENB', 'PSEL0', 'PSEL1', 'PSEL2', 'SLIPP', 'SLIPM'] + [f'PS{k}' for k in range(8)] + ['SLP', 'SLM'])


def ctl():
    """EN buffers, capture clocks CK / CKN (r7e drivers), mode one-hot.  r7f: word load, phase select and slip moved to
    wc_slot1 (next to the enables that time them)."""
    c = Cell('wc_ctl')
    c.inv('EN', 'ENB0', 2, 4)
    c.inv('ENB0', 'ENX', 2, 4)
    c.inv('ENX', 'ENB', 4, 8)
    c.inv('ENX', 'ENB', 4, 8)
    c.nand(['CKP0', 'EN'], 'CKG', 4, 4)
    c.inv('CKG', 'CKGa', 2, 4)
    c.inv('CKGa', 'CKGb', 2, 4)
    c.inv('CKGb', 'CKA', 4, 8)
    for _ in range(2):
        c.inv('CKA', 'CKAB', 4, 8)
    for _ in range(6):
        c.inv('CKAB', 'CK', 4, 8)
    c.nor2('CKA', 'ENB', 'CKNA', 4, 8)
    for _ in range(2):
        c.inv('CKNA', 'CKNB', 4, 8)
    for _ in range(6):
        c.inv('CKNB', 'CKN', 4, 8)
    c.nor2('B2', 'B1', 'BQ', 2, 4)
    c.buf('B2', 'BH')
    c.buf('B1', 'BF')
    c.diode('CKP0')
    return c.row(['EN', 'CKP0', 'B2', 'B1', 'ENB', 'CK', 'CKN', 'BQ', 'BH', 'BF'])


# front retiming: hops (in eighths of a period) from a flop on ring phase r to the next ring phase, ending on phase 0
_HOPS = {0: [], 1: [7], 2: [6], 3: [7, 6], 4: [6, 6], 5: [7, 6, 6], 6: [6, 6, 6], 7: [6, 6, 6, 7]}
O_POS = 48            # octet O_j of sampling cycle m registered at 8m + O_POS eighths (r7e: 32)


def front_plan():
    """Flop list of the front: (name, phase, D, stage-position, padded).  Positions in eighths from the sampling cycle's CKP0."""
    fl = []
    arrive = {}
    for m in (0, 1):
        for j in range(8):
            p0 = j + 4 if m == 0 else j + 8
            nm = f'F{j}' if m == 0 else f'FR{j}'
            fl.append((nm, p0 % 8, f'S{j}', p0, 0))
            prev, p = nm, p0
            for k, h in enumerate(_HOPS[p0 % 8]):
                p += h
                n2 = f'{nm}h{k}'
                fl.append((n2, p % 8, prev, p, 0))
                prev = n2
            arrive[(m, j)] = (prev, p)
    for j in range(8):
        (a0, p0), (a1, p1) = arrive[(0, j)], arrive[(1, j)]
        mx = max(p0, p1)
        for m, (a, p) in ((0, (a0, p0)), (1, (a1, p1))):
            k = 0
            while p < mx:
                n2 = f'{"Z" if m == 0 else "Q"}{j}s{k}'
                fl.append((n2, 0, a, p + 8, 1))
                a, p, k = n2, p + 8, k + 1
            arrive[(m, j)] = (a, p)
        mux = f'M{j}'
        p = mx + 8
        last = f'O{j}r' if p == O_POS else f'X{j}m'
        fl.append((last, 0, ('MUX', arrive[(0, j)][0], arrive[(1, j)][0]), p, 0))
        k = 0
        while p < O_POS:
            p += 8
            n2 = f'O{j}r' if p == O_POS else f'X{j}s{k}'
            fl.append((n2, 0, last, p, 1))
            last, k = n2, k + 1
    for j in range(4, 8):
        fl.append((f'OP{j}r', 0, f'O{j}r', O_POS + 8, 1))
    return fl


def front():
    """r7f front: S_j captured as r7e (RCS=0: CKP(j+4); RCS=1: CKP(j), one period after sampling), then retimed to CKP0 by
    hops of 6/8 or 7/8 period only (front_plan), aligned by padded full-period shifts, RCS-muxed on a full-period hop into
    O_j (all j at 8m + 48 eighths), OP_j = O_j one cycle earlier.  Every flop clock is an EN-gated leaf (NAND + inverter),
    <= 4 flops per leaf, leaves never shared across stage positions."""
    c = Cell('wc_front')
    c.inv('ENB', 'ENL', 2, 4)
    c.inv('RCS', 'RCSB', 1, 2)
    c.inv('RCSB', 'RCSL', 1, 2)
    plan = front_plan()
    # r7f b2: chains laid out one after another (each flop next to its predecessor), one EN-gated leaf per flop.  The first
    # r7f build grouped flops by (position, phase) with <= 4 per leaf: successive chain flops sat up to several 100 um
    # apart and the 6/8-period hops took ~0.9 ns at tt instead of ~0.5 ns.
    order = {}
    for k, (nm, ph, d, pos, pad) in enumerate(plan):
        key = nm.split('h')[0].split('s')[0].split('m')[0].rstrip('r')
        order.setdefault(key, []).append(k)
    def chain_of(nm):
        import re as _re
        m = _re.match(r'(FR|F|Z|Q|X|OP|O)(\d)', nm)
        return int(m.group(2))
    plan = sorted(plan, key=lambda e: (chain_of(e[0]), e[3]))
    for n_, (nm, ph, d, pos, pad) in enumerate(plan):
        lf = f'CKF{n_}'
        if isinstance(d, tuple):
            _, a_, b_ = d
            c.nand([a_, 'RCSB'], f'{nm}_ma')
            c.nand([b_, 'RCSL'], f'{nm}_mb')
            c.nand([f'{nm}_ma', f'{nm}_mb'], f'{nm}_m')
            d = f'{nm}_m'
        elif pad:
            d = _pad(c, d, f'{nm}_d')
        c.nand([f'CKP{ph}', 'ENL'], lf + '_g', 2, 4)
        c.inv(lf + '_g', lf, 2, 4)
        c.ff(lf, d, nm)
    for j in range(8):
        c.bufx(f'O{j}r', f'O{j}')
    for j in range(4, 8):
        c.bufx(f'OP{j}r', f'OP{j}')
    ports = [f'CKP{k}' for k in range(8)] + [f'S{j}' for j in range(8)] + ['ENB', 'RCS'] + \
        [f'O{j}' for j in range(8)] + [f'OP{j}' for j in range(4, 8)]
    c.reverse_groups()
    return c.row(ports)


def lane():
    """r7f lanes, all on CK rise, built as LOCAL groups (first r7f build: one OC set feeding the whole 873 um row gave
    OC -> AOI wires of several 100 um and DLr setup 20 ps at tt 625):
      mux group : its own crossing copies OCm of O0..7 / OP4..7, PT = PS re-registered every cycle, full-rate 8:1 selection
                  pipelined (DFa/DFb registered, DFd = DFaR | DFbR)
      lane j    : its own crossing copies of the octet bits it uses, DF/EF registered locally (DFj/EFj from DFd/EFd),
                  AOI3 -> DLr_j / ELr_j, buffered out to the pairs.
    Every crossing flop takes O through XPAD inverter pairs (hold of the ring-domain -> CK-domain hop)."""
    c = Cell('wc_lane')
    nl = [0]

    def leaf():
        y = f'CKL{nl[0]}'
        nl[0] += 1
        _leaf(c, 'CK', y)
        return y

    def cross(lf, s, tag):
        d = _pad(c, s, f'{s}x{tag}', XPAD) if XPAD else s
        c.ff(lf, d, f'{s}C{tag}')
        return f'{s}C{tag}'
    # ---- mux group
    src = [f'O{k}' for k in range(8)] + [f'OP{k}' for k in range(4, 8)]
    ocm = {}
    for g in range(0, 12, 4):
        lf = leaf()
        for s_ in src[g:g + 4]:
            ocm[s_] = cross(lf, s_, 'm')
    for g in (0, 4):
        lf = leaf()
        for k in range(g, g + 4):
            c.ff(lf, f'PS{k}', f'PT{k}')
    stage1 = []
    for nm, off in (('DF', 0), ('EF', 4)):
        zs = []
        for k in range(8):
            s_ = ocm[f'OP{k}'] if (off == 0 and k >= 4) else ocm[f'O{(k + off) % 8}']
            c.nand([f'PT{k}', s_], f'{nm}z{k}')
            zs.append(f'{nm}z{k}')
        c.nand(zs[:4], f'{nm}a')
        c.nand(zs[4:], f'{nm}b')
        stage1 += [f'{nm}a', f'{nm}b']
    lf = leaf()
    for n in stage1:
        c.ff(lf, n, f'{n}R')
    for nm in ('DF', 'EF'):
        c.inv(f'{nm}aR', f'{nm}an', 1, 2)
        c.inv(f'{nm}bR', f'{nm}bn', 1, 2)
        c.nand([f'{nm}an', f'{nm}bn'], f'{nm}d0')
        c.inv(f'{nm}d0', f'{nm}e', 2, 4)
        c.inv(f'{nm}e', f'{nm}d', 4, 8)          # drives the four lane groups' DF/EF flops
    # ---- lane groups
    for j in range(4):
        lf = leaf()
        ins = {f'O{2 * j}', f'O{2 * j + 1}', 'O0' if j % 2 == 0 else 'O4', 'O2' if j % 2 == 0 else 'O6'}
        oc = {s_: cross(lf if k < 3 else lf2, s_, str(j)) for k, s_ in enumerate(sorted(ins))
              for lf2 in [lf]} if len(ins) <= 4 else None
        lf2 = leaf()
        c.ff(lf2, 'DFd', f'DF{j}')
        c.ff(lf2, 'EFd', f'EF{j}')
        c.aoi3([('BQ', oc[f'O{2 * j}']), ('BH', oc['O0' if j % 2 == 0 else 'O4']), ('BF', f'DF{j}')], f'DL{j}d')
        c.aoi3([('BQ', oc[f'O{2 * j + 1}']), ('BH', oc['O2' if j % 2 == 0 else 'O6']), ('BF', f'EF{j}')], f'EL{j}d')
        c.ff(lf2, f'DL{j}d', f'DL{j}r')
        c.ff(lf2, f'EL{j}d', f'EL{j}r')
        for x in ('DL', 'EL'):
            a_ = _pad(c, f'{x}{j}r', f'{x}{j}q', LPAD) if LPAD else f'{x}{j}r'
            c.bufx(a_, f'{x}{j}')
    ports = [x for j in range(8) for x in (f'O{j}', f'PS{j}')] + \
        [x for j, sel in zip(range(4, 8), ('BQ', 'BH', 'BF', 'CK')) for x in (f'OP{j}', sel)] + ['ENB'] + \
        [f'DL{j}' for j in range(4)] + [f'EL{j}' for j in range(4)]
    return c.row(ports)


def pd():
    """r4 (AC-3): per-bit Alexander phase detector on the aligned octet O (one ring cycle per vote).
    Quarter (BQ): UPk = O(2k) ^ O(2k+1) (data k vs edge k: clock late), DNk = O(2k+1) ^ O(2k+2) (edge k vs
    data k+1: clock early); data 4 is the next cycle's O0, so DN3 = OP7 (previous E3) ^ O0.  Half (BH):
    data O0/O4, edges O2/O6: UP0 = O0^O2, DN0 = O2^O4, UP1 = O4^O6, DN1 = OP6 ^ O0; legs 2,3 off.  Full
    rate (BF): all off (blind phase picker).  r5: the votes are registered ~1.1 ns after the CKP0 that follows the
    octet launch (see the clock comment below; r4 assumed O ~0.5 ns after CKP0 and used CKP1).  Outputs one ring
    cycle wide into pt_cdr UPk/DNk (strong buffers: they cross to the cdr cell).  Latency from the sampling edge
    ~5 ring cycles (O is at 4)."""
    c = Cell('wc_pd')
    c.inv('ENB', 'ENL', 2, 4)
    # r5g: votes registered PD_DELAY inverters (~1.1-1.2 ns tt) after the NEXT CKP0 rise, strongly buffered.  The octet
    # is launched ~1.15-1.3 ns after CKP0 (extracted, probes dbg_r4_q625 / dbg_r5f_q625) and the XOR of two octet
    # bits glitches for up to ~0.6 ns after that (bit-to-bit skew through NAND levels), so the settled vote window is
    # ~[launch + 1.9 ns, launch + T + 1.3 ns]: a clock at CKP0 + ~1.1 ns sits inside it from 480 to 834 MHz and, being
    # made of the same gates, moves with the corner.  r4 sampled on CKP1 (+T/8: inside the transition), r5d/f on a
    # CKN-derived 2/4 gate (the clock reached only 2.6 V, ~1.5 ns late, and caught the XOR glitch: DN 0.09-0.13).
    c.nand(['CKP0', 'ENL'], 'CKV_g', 2, 4)
    c.inv('CKV_g', 'CKVd0', 2, 4)
    prev = 'CKVd0'
    for k in range(PD_DELAY):
        nxt = 'CKVr' if k == PD_DELAY - 1 else f'CKVd{k + 1}'
        c.inv(prev, nxt, 2, 4)
        prev = nxt
    c.bufx('CKVr', 'CKV0')
    c.bufx('CKVr', 'CKV1')
    for n in [f'O{j}' for j in range(8)] + ['OP6', 'OP7']:
        c.inv(n, n + 'n', *PD_INV)

    def xor(a, b, y):        # y = a ^ b = NAND(NAND(a, !b), NAND(!a, b))
        c.nand([a, b + 'n'], y + 'p')
        c.nand([a + 'n', b], y + 'q')
        c.nand([y + 'p', y + 'q'], y)
    pairs = dict(qu0=('O0', 'O1'), qd0=('O1', 'O2'), qu1=('O2', 'O3'), qd1=('O3', 'O4'), qu2=('O4', 'O5'),
                 qd2=('O5', 'O6'), qu3=('O6', 'O7'), qd3=('OP7', 'O0'),
                 hu0=('O0', 'O2'), hd0=('O2', 'O4'), hu1=('O4', 'O6'), hd1=('OP6', 'O0'))
    for y, (a, b) in pairs.items():
        xor(a, b, 'x' + y)
    for k in range(4):
        for d in ('u', 'd'):
            y = f'{"UP" if d == "u" else "DN"}{k}'
            if k < 2:      # quarter or half
                c.nand(['BQ', f'xq{d}{k}'], f'{y}a')
                c.nand(['BH', f'xh{d}{k}'], f'{y}b')
                c.nand([f'{y}a', f'{y}b'], f'{y}m')
            else:
                c.nand(['BQ', f'xq{d}{k}'], f'{y}a')
                c.inv(f'{y}a', f'{y}m', 1, 2)
            c.ff('CKV0' if d == 'u' else 'CKV1', f'{y}m', f'{y}r')
            c.bufx(f'{y}r', y)
    ports = [f'O{j}' for j in range(8)] + ['OP6', 'OP7', 'CKP0', 'ENB', 'BQ', 'BH'] + \
        [f'UP{k}' for k in range(4)] + [f'DN{k}' for k in range(4)]
    return c.row(ports)


# r7b (2026-11-13): the full-top probes (scratch/wired_rx/r7cap/pd_{tt,ss}625) showed the vote D inputs still changing
# at the vote clock at ss/32/3.15, 625 MHz (settle margin 0.001 ns; tt 0.21 ns): the r5g comment above assumed a settled
# window that the weak 1/2 O -> On inverters and the O bit skew do not give.  Vote clock 6 -> 10 inverters and the On
# inverters 1/2 -> 2/4: cell-level (pdv/pdcell.py, reproduces the full-top tt pass / ss fail on the r7 cell) settle /
# hold margins tt 0.73 / 0.42, ss 0.50 / 0.53, ff 0.90 / 0.31 ns at 625 MHz.
# r7c (2026-11-14): pair-16 probe at ss/32/3.15, 625 MHz (scratch/wired_rx/r7cap/p16_an.py): the word load GWL rises only
# 0.48-0.57 ns after the last slot's GCL (the GW path is ~0.3 ns faster than the GCK path, so the "half period either
# side" above is not what the layout gives) and R settles 0.14-0.27 ns before it: pair 16 at 0.141 ns resolved its W flop
# 0.81 ns late and gave the EW16 edge error.  The other side (next word's slot 0 after GW) has > 1 ns.  Two inverter
# pairs move GW ~0.3 ns later.
GW_DELAY = 2         # inverter pairs between GW0 and GWX (wc_ctl); r7/r7b: 0
PD_DELAY = 10        # PD vote-clock delay after CKP0 (inverters, even); r5g..r7: 6
PD_INV = (2, 4)      # O -> On inverter size in the PD XORs; r5g..r7: (1, 2)


def split(fn, cuts, rev=()):
    """r7 (area): cut one wide single-row cell into rows at the given gate-group indices.  Each piece exports the
    original ports it uses plus every net shared with another piece.  The cuts are chosen so that NO locally gated
    clock (CK*/CN*/PC*/PR*) crosses a piece boundary (r7 first try, column-balanced cuts: CKF2/CNF/CKQ2 crossed
    rows, extracted q625 15 bit errors and wrong PD votes); only flop-to-flop data and static nets cross.  Pieces
    in `rev` are mirrored, so with the pieces stacked left-aligned the boundary ends of consecutive pieces sit
    above each other (snake) and the crossing nets stay short."""
    def make(idx):
        r, ports, net = fn()
        gs = r._cell.groups
        bnd = [0] + list(cuts) + [len(gs)]
        parts = [gs[bnd[j]:bnd[j + 1]] for j in range(len(bnd) - 1)]

        def nets(gl):
            return [n for _, nl in gl for line in nl for n in line.split()[1:5]]
        used = set(nets(parts[idx]))
        other = set(n for j, gl in enumerate(parts) if j != idx for n in nets(gl))
        clk = sorted(n for n in used & other if n.startswith(('CK', 'CN', 'PC', 'PR')) and not n.startswith('CKP'))
        assert not clk, f'gated clock crosses a split boundary: {clk}'
        orig = [p for p in ports if p not in ('VDD', 'VSS')]
        pp = [p for p in orig if p in used] + sorted(n for n in used if n in other and n not in orig
                                                      and n not in ('VDD', 'VSS'))
        sub = Cell(f'{r._cell.name}{idx}')
        for cols, nl in (reversed(parts[idx]) if idx in rev else parts[idx]):
            sub._add(cols, nl)
        # antenna: a crossing net received here only on gates gets an N+ diode in this piece (the shared planner
        # counts the driver's S/D in the other piece as protection; first r7 build: 6 x ANT.16_i_ANT.5 on M4)
        sd = set(n for _, nl in parts[idx] for line in nl for k, n in enumerate(line.split()[1:5]) if k != 1)
        for n in pp:
            if n not in orig and n not in sd:
                sub.diode(n)
            # mirrored piece: static gate-only ports now run the full row in M2 to their gate (r7c: RCS, ANT.3)
            elif idx in rev and n in orig and n not in sd and not n.startswith(('CKP', 'S')):
                sub.diode(n)
        return sub.row(pp)
    return [lambda i=i: make(i) for i in range(len(cuts) + 1)]


# r7: the 20->40 gearbox (wc_gear, AC-1/S3) moved into the digital macro (coordinator decision, interface row
# W7-GEAR): the block now ends at the 20-bit word DW/EW plus the word strobe WSTB (= wc_ctl GWT).
CELLS = dict(wc_pair=pair, wc_cnt=cnt, wc_slot0=lambda: slot(0), wc_slot1=lambda: slot(1),
             wc_ctl=ctl, wc_lane=lane, wc_pd=pd, wc_word=word)
SPLIT = dict(wc_front=(front, (162,), {1}))   # r7: the front row folded into 2 rows; r7f: cut at the column midpoint where no leaf clock crosses
for _nm, (_fn, *_k) in SPLIT.items():
    for _i, _f in enumerate(split(_fn, *_k)):
        CELLS[f'{_nm}{_i}'] = _f


def subckt(name, ports, net):
    return f'.subckt {name} {" ".join(ports)}\n' + '\n'.join(net) + f'\n.ends {name}\n'


def build_cell(name):
    row, ports, net = CELLS[name]()
    row.build()
    work = SCRATCH / 'cells' / name
    if work.exists():
        shutil.rmtree(work)
    row.emit(work, ports)
    sch = subckt(name, ports, net)
    res = compact.check(work, name, sch)
    FAST.mkdir(parents=True, exist_ok=True)
    for suf in ('.mag', '.ext.spice', '.lvs.spice', '.gds'):
        f = work / f'{name}{suf}'
        if f.exists():
            shutil.copy(f, FAST / f'{name}{suf}')
    (FAST / f'{name}.spice').write_text('* SPDX-License-Identifier: Apache-2.0\n* generated by capture.py (intended netlist)\n' + sch)
    rails = {}
    for key, (net_, yy) in row.rails.items():
        rails.setdefault(net_, [0.3, yy])
    (FAST / f'{name}.pins.json').write_text(json.dumps(dict(ports=ports, pins={k: list(v) for k, v in row.pins.items()},
                                                           rails=rails, bbox=[0.0, 0.0, round(row.width, 3), round(row.top, 3)]),
                                                      indent=1))
    res.update(size_um=[round(row.width, 2), round(row.top, 2)], area_um2=round(row.width * row.top, 1), devices=len(net))
    print(name, json.dumps({k: (v if k != 'lvs' else v['unique_match']) for k, v in res.items()}), flush=True)
    return res


# ----------------------------------------------------------------------------------------- top
TOP_PORTS = ([f'S{j}' for j in range(8)] + [f'CKP{k}' for k in range(8)] +
             ['EN', 'LDE', 'RCS', 'B2', 'B1', 'PSEL0', 'PSEL1', 'PSEL2', 'SLIPP', 'SLIPM'] +
             [f'DW{i}' for i in range(20)] + [f'EW{i}' for i in range(20)] + ['SLP', 'SLM'] +
             [f'UP{k}' for k in range(4)] + [f'DN{k}' for k in range(4)] + ['WSTB', 'VDD', 'VSS'])


def top_instances():
    """(instance name, cell, connections in cell port order)."""
    P = {n: CELLS[n]()[1] for n in CELLS}
    out = []

    def add(inst, cell, m):
        out.append((inst, cell, [m.get(p, p) for p in P[cell]]))
    add('XCTL', 'wc_ctl', {})
    for nm, (fn, cuts, _) in SPLIT.items():
        orig = set(fn()[1])
        for i in range(len(cuts) + 1):
            add(f'X{nm[3:].upper()}{i}', f'{nm}{i}', {q: f'{nm}_{q}' for q in P[f'{nm}{i}'] if q not in orig})
    add('XLN', 'wc_lane', {})
    add('XCN', 'wc_cnt', {})
    add('XSL0', 'wc_slot0', {})
    add('XSL1', 'wc_slot1', dict(GWT='WSTB'))
    add('XPD', 'wc_pd', {})
    add('XWD', 'wc_word', {})
    for i in range(20):
        add(f'XP{i}', 'wc_pair', dict(GCK=f'GCK{i}', DLN=f'DL{i % 4}', ELN=f'EL{i % 4}', DW=f'DW{i}', EW=f'EW{i}'))
    return out


def top_netlist(include_cells=True):
    txt = ''
    if include_cells:
        for n in CELLS:
            txt += subckt(n, *CELLS[n]()[1:])          # always the current intended netlists
    txt += f'.subckt pt_wrx_cap {" ".join(TOP_PORTS)}\n'
    for inst, cell, conns in top_instances():
        txt += f'{inst} {" ".join(conns)} {cell}\n'
    txt += '.ends pt_wrx_cap\n'
    return txt


if __name__ == '__main__':
    for n in sys.argv[1:] or CELLS:
        build_cell(n)


# ----------------------------------------------------------------------------------------- bench
def prbs(n, seed=0x5A):
    s, out = seed, []
    for _ in range(n):
        b = ((s >> 6) ^ (s >> 5)) & 1
        out.append((s >> 6) & 1)
        s = ((s << 1) | b) & 0x7F
    return out


def bench(bpc, f=625e6, words=12, psel=0, corner='typical', temp=27, vdd=3.3, d_lat=300e-12, slip_seq=None,
          ext_clock=False, lde_delay=0.3e-9, en_off=False, rcs=0, s_static=False):
    """Ideal ring phases + ideal sampler outputs (S_j changes d_lat after its phase edge, value = line at
    the phase edge) driving pt_wrx_cap.  Line: PRBS7 at bpc bits per ring cycle, data sampler centred.
    ext_clock: only CKP0/CKP4 toggle (CKP1-3 = CKP0, CKP5-7 = CKP4), as in the WCLK_IN fallback."""
    T = 1 / f
    ncyc = {4: 5, 2: 10, 1: 20}[bpc] * words + 12
    ui = T / bpc
    bits = prbs(int(ncyc * bpc) + 64)
    # data sampler for bit m: quarter j=2*(m%4), half j=4*(m%2), full j=psel; edges half a UI later
    dj = {4: [0, 2, 4, 6], 2: [0, 4], 1: [psel]}[bpc]
    t0 = 2e-9
    def line(t):   # bit m centred on the data sampler instants
        m = (t - t0 - (dj[0] * T / 8)) / ui + 0.5
        return bits[int(m)] if m >= 0 else 0
    lines = []
    tr = 40e-12
    for k in range(8):
        kk = k if not ext_clock else (0 if k < 4 else 4)
        lines.append(f'VCK{k} ckp{k} 0 PULSE(0 {vdd} {t0 + kk * T / 8:.6e} {tr} {tr} {T / 2 - tr:.6e} {T:.6e})')
    for j in range(8):
        pts = [(0, 0.)]
        for n in range(ncyc):
            ts = t0 + n * T + j * T / 8 + 1e-12
            v = vdd * line(ts + 0.25 * ui if (j not in dj) else ts)   # edge samplers: right after the boundary
            if s_static:   # r6: system safe state (slicer_en follows the capture EN, S held low by pt_slicer)
                v = 0.
            tc = ts + d_lat
            pts += [(tc, pts[-1][1]), (tc + 30e-12, v)]
        lines.append(f'VS{j} s{j} 0 {sims_pwl(pts)}')
    nw = {4: 5, 2: 10, 1: 20}[bpc]
    lde = [(0, 0.)]
    for w in range(words + 2):
        a = t0 + (w * nw + 2) * T + lde_delay
        lde += [(a, 0.), (a + 30e-12, vdd), (a + T, vdd), (a + T + 30e-12, 0.)]
    lines.append(f'VLDE lde 0 {sims_pwl(lde)}')
    b2, b1 = {4: (0, 0), 2: (1, 0), 1: (0, 1)}[bpc]
    lines += [f'VDD vdd 0 {vdd}', ('VEN en 0 0' if en_off else f'VEN en 0 PWL(0 0 1n 0 1.05n {vdd})'), f'VB2 b2 0 {b2 * vdd}', f'VB1 b1 0 {b1 * vdd}']
    lines += [f'VPS{b} psel{b} 0 {vdd * ((psel >> b) & 1)}' for b in range(3)] + ['VSP slipp 0 0', 'VSM slipm 0 0', f'VRCS rcs 0 {vdd * rcs}']
    conn = {p: p.lower() for p in TOP_PORTS}
    conn.update(VDD='vdd', VSS='0')
    lines.append('XCAP ' + ' '.join(conn[p] for p in TOP_PORTS) + ' pt_wrx_cap')
    lines += [f'CDW{i} dw{i} 0 20f' for i in range(20)] + [f'CEW{i} ew{i} 0 20f' for i in range(20)]
    # r4: vote outputs into the pt_cdr pins (~100 fF of route + gate); r7: WSTB into the macro pin (~50 fF)
    lines += [f'CUP{k} up{k} 0 100f' for k in range(4)] + [f'CDN{k} dn{k} 0 100f' for k in range(4)]
    lines += ['CWS wstb 0 50f']
    T_end = t0 + ncyc * T
    outs = ' '.join(f'v(dw{i})' for i in range(20)) + ' ' + ' '.join(f'v(ew{i})' for i in range(20))
    outs += ' ' + ' '.join(f'v(up{k})' for k in range(4)) + ' ' + ' '.join(f'v(dn{k})' for k in range(4))
    outs += ' v(wstb)'
    ctl = '\n'.join([f'tran 2p {T_end:.4g} 0 10p', 'set wr_singlescale', f'wrdata out.txt v(lde) {outs}',
                     f'meas tran iavg avg i(VDD) from={t0 + 6 * T:.4g} to={T_end:.4g}'])

    def analyse(log, data):
        import numpy as np
        d = np.loadtxt(data)
        t = d[:, 0]
        if en_off:   # safe state: EN=0 with ring phases, samples and LDE toggling
            iavg = None
            for line_ in log.splitlines():
                if line_.strip().startswith('iavg'):
                    iavg = -float(line_.split('=')[1].split()[0])
            omax = float(np.max(d[t > 3e-9, 2:51]))
            return dict(i_uA=iavg * 1e6 if iavg is not None else None, outputs_max_v=omax,
                        pass_=bool(iavg is not None and abs(iavg) < 10e-6 and omax < 0.3))
        # word update instants: clusters of output transitions (W flops all load on one edge)
        ch = np.zeros(len(t), bool)
        for col in range(2, 42):
            v = d[:, col] > vdd / 2
            ch[1:] |= v[1:] != v[:-1]
        tc = t[ch]
        groups = []
        for x in tc:
            if groups and x - groups[-1][-1] < 0.3 * nw * T:
                groups[-1].append(x)
            else:
                groups.append([x])
        up = [g[0] for g in groups]
        ws = []
        for a, b in zip(up, up[1:]):
            if abs(b - a - nw * T) > 0.2 * nw * T:   # start-up / no change in a word
                continue
            k = int(np.searchsorted(t, (a + b) / 2))
            ws.append(([int(v > vdd / 2) for v in d[k, 2:22]], [int(v > vdd / 2) for v in d[k, 22:42]]))
        ws = ws[2:]          # start-up: counter restart and the phase-select shadow need one word each
        stream = [b for w, _ in ws for b in w]
        estream = [b for _, e in ws for b in e]
        # find the PRBS alignment of the first full word and count mismatches over the rest
        best = None
        for off in range(len(bits) - len(stream) - 1):
            err = sum(1 for i, b in enumerate(stream) if bits[off + i] != b)
            if best is None or err < best[1]:
                best = (off, err)
        # edge words (added 2026-11-09; r1 evidence never checked EW): every edge sample is taken just
        # after the boundary between data bits k and k+1, so EW_k must equal data bit k+1
        edge_err = sum(1 for i, b in enumerate(estream) if bits[best[0] + i + 1] != b) if best else None
        iavg = None
        for line_ in log.splitlines():
            if line_.strip().startswith('iavg'):
                iavg = -float(line_.split('=')[1].split()[0])
        err_pos = sorted({i % 20 for i, b in enumerate(stream) if best and bits[best[0] + i] != b})
        eerr_pos = sorted({i % 20 for i, b in enumerate(estream) if best and bits[best[0] + i + 1] != b})
        # r4 PD: edge samples sit just after each boundary (clock late), so every transition must give an
        # UP vote on its leg and no DN vote; legs unused in the mode must stay quiet
        win = t > t0 + 12 * T
        act = [float(np.mean(d[win, 42 + k] > vdd / 2)) for k in range(8)]
        legs = {4: 4, 2: 2, 1: 0}[bpc]
        pd_ok = all((0.2 < act[k] < 0.8) if k < legs else act[k] < 0.02 for k in range(4)) and \
            all(a < 0.02 for a in act[4:])
        # r7 word interface (gear in the digital macro): DW/EW sampled at each WSTB rise must be the PREVIOUS word,
        # i.e. consecutive WSTB-rise samples are consecutive 20-bit words of the line PRBS; and the DW/EW transition
        # instants after each WSTB rise give the macro's hold (min) / setup (max) numbers.
        wsv = d[:, 50] > vdd / 2
        rises = [t[i] for i in range(1, len(t)) if wsv[i] and not wsv[i - 1]]
        falls = [t[i] for i in range(1, len(t)) if (not wsv[i]) and wsv[i - 1]]
        sw = []
        for tr_ in rises:
            k = int(np.searchsorted(t, tr_ - 20e-12))
            sw.append([int(v > vdd / 2) for v in d[k, 2:22]])
        sw = sw[3:]
        sstr = ''.join(map(str, bits))
        st_err, prev = 0, None
        for w in sw:
            pos = sstr.find(''.join(map(str, w)))
            ok_ = pos >= 0 and (prev is None or (pos - prev - 20) % 127 == 0)
            st_err += 0 if ok_ else 1
            prev = pos if pos >= 0 else None
        dly = []
        for tr_ in rises[3:]:
            m = (t > tr_) & (t < tr_ + 0.6 * nw * T)
            idx = np.where(m)[0]
            for col in range(2, 42):
                v = d[idx, col] > vdd / 2
                ch_ = np.where(v[1:] != v[:-1])[0]
                if len(ch_):
                    dly.append(t[idx[ch_[0] + 1]] - tr_)
        pw = [f_ - r_ for r_, f_ in zip(rises, [f for f in falls if f > rises[0]])] if rises else []
        word_timing = dict(dw_after_wstb_rise_ns=[round(min(dly) * 1e9, 3), round(max(dly) * 1e9, 3)] if dly else None,
                           wstb_high_ns=round(float(np.median(pw)) * 1e9, 3) if pw else None,
                           word_period_ns=round(nw * T * 1e9, 3))
        gear_ok = len(sw) >= max(1, len(ws) - 4) and st_err == 0
        return dict(words=len(ws), bits=len(stream), offset=best[0] if best else None, dw_err_bitpos=err_pos,
                    vote_activity=dict(zip([f'UP{k}' for k in range(4)] + [f'DN{k}' for k in range(4)], act)),
                    pd_ok=pd_ok, strobe_words=len(sw), strobe_word_errors=st_err, word_timing=word_timing, gear_ok=gear_ok,
                    ew_err_bitpos=eerr_pos,
                    bit_errors=best[1] if best else None, edge_bits=len(estream), edge_errors=edge_err,
                    i_mA=iavg * 1e3 if iavg else None,
                    pass_=bool(ws and len(ws) >= words - 4 and best and best[1] == 0 and edge_err == 0
                               and pd_ok and gear_ok))
    return '\n'.join(lines), ctl, analyse


def sims_pwl(points):
    return 'PWL(' + ' '.join(f'{t:.9e} {v:.4g}' for t, v in points) + ')'


def run_bench(tag, bpc, ext=False, assess_only=False, **kw):
    import wrx_flow as wf
    import sims
    work = SCRATCH / 'sim' / tag
    if assess_only:      # re-judge a stored run (same bench parameters) without simulating
        body, ctl, an = bench(bpc, **kw)
        log = (work / 'tb.cir.log').read_text()
        try:
            r = an(log, work / 'out.txt')
        except Exception as exc:
            r = dict(error=repr(exc)[:300])
        r.update(tag=tag, bpc=bpc, netlist='extracted' if ext else 'schematic', assessed_only=True,
                 **{k: v for k, v in kw.items() if k != 'slip_seq'})
        (work / 'result.json').write_text(json.dumps(r, indent=1, default=str))
        return r
    work.mkdir(parents=True, exist_ok=True)
    if ext:
        shutil.copy(GEN / 'wrx_cap.ext.spice', work / 'cap.spice')
    else:
        (work / 'cap.spice').write_text(top_netlist())
    body, ctl, an = bench(bpc, **kw)
    (work / 'tb.cir').write_text('\n'.join([f'* {tag}', sims.sim_header(kw.get('corner', 'typical'), kw.get('temp', 27)),
                                           '.include cap.spice', body, '.control', ctl, '.endc', '.end']))
    log = wf.ngspice(work, 'tb.cir', timeout=4 * 3600)
    try:
        r = an(log, work / 'out.txt')
    except Exception as exc:
        r = dict(error=repr(exc)[:300], log_tail=log[-400:])
    r.update(tag=tag, bpc=bpc, netlist='extracted' if ext else 'schematic', **{k: v for k, v in kw.items() if k != 'slip_seq'})
    (work / 'result.json').write_text(json.dumps(r, indent=1, default=str))
    return r


# ----------------------------------------------------------------------------------------- top layout
# r7 floorplan (no gear, 0.3 mm^2 class), rows bottom-up.  The front is folded into 2 rows stacked left-aligned
# (FRONT1 = S/F/FR input end, mirrored; FRONT0 = O output end), cut where only H/Z (into the CKP0 P/Q stage) cross:
# the r7b 3-way cut also crossed FR0..7 and F5..7 (half-period paths of the RCS=1 route).  O leaves FRONT0's left
# end straight up into LN and PD (row above).  Both slot cells sit directly above the two pair rows; each pair row is
# one slot cell's pairs, grouped by lane (i % 4) and lane-aligned between the rows, so GCK and DL/EL stay short.
# (r6 AREA's index-ordered 10-wide rows: DL/EL 250-317 fF, 13 errors; r7b lane-ordered rows with SL1 four rows
# away from its pairs: ext q625 1 error on pair 2.)
ROWS = [['FRONT1'], ['FRONT0'], ['LN', 'CN', 'CTL'], ['PD', 'SL0'], ['WD', 'SL1'],
        [f'P{i}' for i in (0, 4, 8, 1, 5, 9, 2, 6, 3, 7)],
        [f'P{i}' for i in (12, 16, 13, 17, 10, 14, 18, 11, 15, 19)]]


def build_top(rows=None, max_row_width=1100.0):
    """Assemble the compact rows with timing's generic macro placer/router (layout_engine), from this
    directory's generated/fast cells.  Writes generated/wrx_cap.{mag,gds,ext.spice,lvs.spice}."""
    import netlist as tn
    import wrx_flow as wf
    for n in CELLS:
        tn.MACROS[n] = json.loads((FAST / f'{n}.pins.json').read_text())['ports']
    le.FAST = FAST
    work = SCRATCH / 'top'
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    (work / 'top.spice').write_text(top_netlist(include_cells=False))
    ports, devices = tn.load(work / 'top.spice', 'pt_wrx_cap')
    if rows is None:
        # r5: GR below the pairs and LN at the left of its row (next to the pairs).  r4 put the 66 um gear row
        # (+51 um channel) between the slots and the pairs and LN right of PD: the lane nets DL/EL grew
        # 120 -> 200-255 fF extracted and the lane -> slot flop half-period path failed (q625 40/200 errors).
        rows = ROWS
    # r5h: the vote outputs as one trunk group flanked by static mode/select ports (r5g: CKP0's trunk beside UP3,
    # 68 fF: 0.6 V spikes on UP3 with EN = 0 and an extra 68 fF on one ring phase)
    rep = le.generate(work, 'pt_wrx_cap', ports, devices, rows=rows, max_row_width=max_row_width,
                      trunk_groups=[['RCS'] + [f'UP{k}' for k in range(4)] + [f'DN{k}' for k in range(4)] + ['B2']], over_cell=True)
    defs = ''.join((FAST / f'{m}.spice').read_text() for m in CELLS)
    top_sp = tn.flat_spice(ports, devices, 'pt_wrx_cap')
    ant = le.ad.spice_lines(rep.get('antenna_diodes', []))   # K1 antenna diodes -> LVS reference
    if ant:
        k = top_sp.rstrip().rfind('.ends')
        top_sp = top_sp[:k] + '\n'.join(ant) + '\n' + top_sp[k:]
    (work / 'schematic.spice').write_text(defs + top_sp)
    lvs = le.netgen_lvs(work, 'pt_wrx_cap.lvs.spice', 'pt_wrx_cap', 'schematic.spice', 'pt_wrx_cap')
    gen = GEN
    for suf in ('.mag', '.ext.spice', '.lvs.spice'):
        f = work / f'pt_wrx_cap{suf}'
        if f.exists():
            shutil.copy(f, gen / f'wrx_cap{suf}')
    for n in CELLS:
        if (work / f'{n}.mag').exists():
            shutil.copy(work / f'{n}.mag', FAST / f'{n}.mag')
    try:
        gx = wf.export_gds(work, 'pt_wrx_cap', 0)
    except Exception as exc:
        gx = dict(error=repr(exc)[:300])
    res = dict(drc_errors=le.drc_errors(rep['drc_count_raw']), lvs=lvs, layout={k: v for k, v in rep.items() if k != 'cmds'},
               gds_export=gx, devices=len(devices))
    (gen / 'wrx_cap-layout.json').write_text(json.dumps(res, indent=1, default=str))
    return res
