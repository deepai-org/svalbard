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
SCRATCH = HERE.parents[3] / 'scratch' / 'wired_rx' / 'cap'


class Cell:
    def __init__(self, name):
        self.name, self.cols, self.net, self.k = name, [], [], 0

    def _add(self, cols, net):
        if self.cols:
            self.cols.append(BRK)
        self.cols += cols
        self.net += net

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

    def row(self, ports, track_order=None):
        r = compact.Row(self.name, self.cols, ports=ports, wn=2, wp=4)
        if track_order:
            r.track_order = track_order
        return r, ports + ['VDD', 'VSS'], self.net


# ----------------------------------------------------------------------------------------- cells
def pair():
    """Bit pair i: two slot flops on the pair's gated clock GCK (one pulse per word, from wc_slot), two
    word flops on GW.  No ring-rate clock reaches the pairs."""
    c = Cell('wc_pair')
    c.buf('GCK', 'GCL')
    # r2f: keepers on the word flops only (r2e kept R too: the keeper slowed R enough to miss the
    # half-period R -> W hand-off at 810 MHz extracted, pair 16)
    c.ff('GCL', 'DLN', 'RD')
    c.ff('GCL', 'ELN', 'RE')
    c.buf('GW', 'GWL')
    c.ff('GWL', 'RD', 'DWq', keep=True)  # word outputs: static NOR output stage of the TSPC flop
    c.ff('GWL', 'RE', 'EWq', keep=True)
    # r5 (2026-11-10): strong output buffers.  r4 routed DW to the wc_gear row as well (L and DX flop inputs):
    # DW grew from 7-55 fF to 165-203 fF extracted, the keeper-flop output then took 1.2-2 ns and once
    # double-switched after GW (probe scratch/wired_rx/cap/sim/dbg_r4_q625): the q625 40/200 / f480 1/120 data
    # errors, with 0 edge errors (EW was not routed to the gear).  EW gets the same buffer (equal DW/EW delay).
    c.bufx('DWq', 'DW')
    c.bufx('EWq', 'EW')
    ports = ['GCK', 'GW', 'DLN', 'ELN', 'ENB', 'DW', 'EW']
    return c.row(ports)


def cnt():
    """Word restart: LDE re-registered twice on CK (INJ1, INJ).  INJ seeds the slot-0 enables of the
    one-hot slot chain (wc_slot*); the second register keeps the LDE -> slot-0 latency of the r1 binary
    counter (LDE, state, enable) and resolves a marginal first sample of LDE (any wordclk phase)."""
    c = Cell('wc_cnt')
    c.buf('CK', 'CKM')
    c.ff('CKM', 'LDE', 'INJ1')
    c.ff('CKM', 'INJ1', 'INJQ')
    c.buf('INJQ', 'INJ')
    ports = ['CK', 'ENB', 'LDE', 'INJ']
    return c.row(ports)


def _pred(i):
    """Predecessor enables of pair i (quarter, half, full): the pair one slot earlier, INJ for slot 0."""
    return tuple(f'ELQ{i - k}' if i >= k else 'INJ' for k in (4, 2, 1))


def slot(half):
    """One-hot slot chain for pairs 10*half .. 10*half+9 (r2, replaces the binary counter + global decode
    of r1, whose counter -> decode -> enable path exceeded one period extracted at 625 MHz):
        ELQ_i <= BQ & ELQ_(i-4) | BH & ELQ_(i-2) | BF & ELQ_(i-1)     (INJ in place of ELQ_(<0))
    registered on CK rise, so pair i is enabled one slot after its predecessor (quarter 4, half 2, full
    1 pairs per slot) and slot 0 one CK after INJ.  The chain has no wrap-around: every word is seeded
    by INJ and any corrupted enable shifts out within one word.  GCK_i = CKN & ELQ_i (one pulse per
    word, at the CK fall)."""
    c = Cell(f'wc_slot{half}')
    c.buf('CK', 'CKL0')
    c.buf('CKN', 'CNL0')
    for i in range(10 * half, 10 * half + 10):
        if i % 5 == 0 and i % 10:
            c.buf('CK', 'CKL1')
            c.buf('CKN', 'CNL1')
        ck, cn = ('CKL1', 'CNL1') if i % 10 >= 5 else ('CKL0', 'CNL0')
        q, h, f_ = _pred(i)
        if i == 0:
            d = 'INJ'
        else:
            c.aoi3([('BQ', q), ('BH', h), ('BF', f_)], f'E{i}')
            d = f'E{i}'
        # r2b: the flop output (ELQq) only drives this pair's clock gate and a buffer, so it settles
        # well inside the half period the gate allows; the buffered ELQ feeds the chain and exports
        c.ff(ck, d, f'ELQ{i}q')
        c.nand([cn, f'ELQ{i}q'], f'G{i}B')
        c.inv(f'G{i}B', f'GCK{i}', 2, 4)
        if i != 19:                       # pair 19 has no successor (wc_ctl keeps its own copy)
            c.bufx(f'ELQ{i}q', f'ELQ{i}')
    xin = ['ELQ6', 'ELQ7', 'ELQ8', 'ELQ9']          # slot1 pairs 10..13 follow slot0 pairs 6..9
    if half:      # r6 antenna: ELQ6/ELQ7 were 402-444 (ANT.3 limit 400); diodes on all four inputs
        for n in xin:
            c.diode(n)
    # r2d: wc_ctl rebuilds pair 19's enable locally from its predecessors (ELQ15/17/18)
    ports = ['CK', 'CKN', 'ENB', 'BQ', 'BH', 'BF'] + (xin if half else ['INJ']) + \
        [f'GCK{i}' for i in range(10 * half, 10 * half + 10)] + (['ELQ15', 'ELQ17', 'ELQ18'] if half else xin)
    return c.row(ports)


def ctl():
    """Clock generation (EN gating), reset buffer, word-load gate GW, one-hot phase select and slip
    shadow registers, slip outputs, mode one-hot."""
    c = Cell('wc_ctl')
    c.inv('EN', 'ENB0', 2, 4)
    c.inv('ENB0', 'ENX', 2, 4)
    c.inv('ENX', 'ENB', 4, 8)
    c.inv('ENX', 'ENB', 4, 8)
    c.nand(['CKP0', 'EN'], 'CKG')
    c.inv('CKG', 'CKA', 2, 4)
    c.inv('CKA', 'CKAB', 4, 8)
    c.inv('CKAB', 'CK', 4, 8)
    c.inv('CKAB', 'CK', 4, 8)
    c.nor2('CKA', 'ENB', 'CKNA')
    c.inv('CKNA', 'CKNB', 4, 8)
    c.inv('CKNB', 'CKN', 4, 8)
    c.inv('CKNB', 'CKN', 4, 8)
    # word load gate: ELQ19 (pair 19 = last slot in every mode) through a latch transparent while CK
    # is low gates CK, so the word flops load at the CK rise after the last slot capture (half a
    # period either side).  r2b: static mux latch with a consensus term (r1: a CK-fall flop, which
    # needed ELQ19 within half a period and missed words at ss extracted).  r2d: ELQ19 is a local
    # copy of pair 19's enable, registered here from its predecessors (a full period to cross the
    # macro), so the latch and GW start from a lightly loaded local flop; with the remote ELQ19
    # (r2c) GW rose late at 810 MHz and raced slot 0 (bit-0 errors).
    c.aoi3([('BQ', 'ELQ15'), ('BH', 'ELQ17'), ('BF', 'ELQ18')], 'E19C')
    c.buf('CK', 'CKC')
    c.ff('CKC', 'E19C', 'ELQ19')
    c.nand(['ELQ19', 'CKN'], 'LW1')
    c.nand(['ELW', 'CK'], 'LW2')
    c.nand(['ELQ19', 'ELW'], 'LW3')
    c.nand(['LW1', 'LW2', 'LW3'], 'ELW')
    c.nand(['CK', 'ELW'], 'GWB')
    c.inv('GWB', 'GW0', 2, 4)
    c.inv('GW0', 'GWX', 2, 4)
    c.inv('GWX', 'GW', 4, 8)
    c.inv('GWX', 'GW', 4, 8)
    c.inv('GWX', 'GWT', 4, 8)           # r5: private copy for wc_gear (r5c on GW itself: 310 -> 552 fF extracted)
    c.buf('GW', 'GWL')
    # phase-select / slip shadow clock: the last slot's own capture edge (CK fall), so the lanes have a
    # full period to settle before slot 0 of the next word
    c.nand(['CKN', 'ELQ19'], 'GPB')
    c.inv('GPB', 'GP0', 3, 6)
    for b in range(3):
        c.inv(f'PSEL{b}', f'PN{b}', 1, 2)
    for k in range(8):
        bits = [(f'PSEL{b}' if (k >> b) & 1 else f'PN{b}') for b in range(3)]
        c.nand(bits, f'PD{k}B')
        c.inv(f'PD{k}B', f'PD{k}', 1, 2)
        if k % 4 == 0:
            c.buf('GP0', f'GPL{k // 4}')
        c.ff(f'GPL{k // 4}', f'PD{k}', f'PS{k}')
    c.buf('GP0', 'GPL2')
    c.ff('GPL2', 'SLIPP', 'SPQ')        # slip of the word now starting
    c.ff('GPL2', 'SLIPM', 'SMQ')
    c.ff('GPL2', 'SPQ', 'SPQ2')         # ... of the word now completing
    c.ff('GPL2', 'SMQ', 'SMQ2')
    c.ff('GWL', 'SPQ2', 'SLP')         # presented with that word
    c.ff('GWL', 'SMQ2', 'SLM')
    # mode one-hot
    c.nor2('B2', 'B1', 'BQ', 2, 4)
    c.buf('B2', 'BH')
    c.buf('B1', 'BF')
    c.diode('CKP0')    # r6 antenna: CKP0 ratio 414 (ANT.3 limit 400)
    # r5: no gear outputs here any more (r4 exported ELWO and loaded CK/CKN with the gear row; wc_gear now runs
    # from GW alone, see gear())
    ports = ['EN', 'CKP0', 'ELQ15', 'ELQ17', 'ELQ18', 'PSEL0', 'PSEL1', 'PSEL2', 'SLIPP', 'SLIPM', 'B2', 'B1',
             'ENB', 'CK', 'CKN', 'GW', 'BQ', 'BH', 'BF', 'SLP', 'SLM'] + [f'PS{k}' for k in range(8)] + ['GWT']
    return c.row(ports)


def front():
    """r3 (W1, 2026-11-10): static re-capture select RCS, data-path muxed, all clocks EN-gated.

    The real pt_slicer (r2 extracted) changes S_j 0.47-0.95 ns after its own phase edge.  r2f
    re-captured S_j on CKP(j+4), T/2 after sampling: that is inside the slicer delay at 810 MHz (T/2 =
    0.62 ns) and at 625 MHz ss (0.80 ns).  RCS=1 re-captures S_j on CKP(j) one full period after
    sampling (window d_max + setup < T and buffer delay + hold < d_min: 0.95 + 0.1 < 1.23 ns at 810 MHz,
    0.15 < 0.47 ns), which is the same edge in the WCLK_IN fallback too (CKP0..3 = CK, CKP4..7 = !CK).
    Timeline in T/8 from the sampling cycle's CKP0 rise:
        RCS=0 (r2f, unchanged): F_j at j+4; j=0 F->A(8)->Z(16); j=1..4 F->B(12)->Z(16); j=5..7 F->Z(16)
        RCS=1: F'_j at j+8; j=0..4 F'->H(16); j=5..7 F'->G(20)  [G: CKP4, T/2 -- same as r2f's B->Z]
        P_j <= Z_j (24), Q_j <= H_j|G_j (24), O_j <= RCS ? Q_j : P_j (32)
    The only mux is on a full-period CKP0 -> CKP0 path, so neither choice gets a tighter path than r2f
    (the W1 working copy muxed the clocks; its extra clock levels failed q810 extracted, 49 errors).
    Latency is two ring cycles more than r2f for RCS=0 and the word boundary moves (raw words and the CDR
    do not care; LDE still fixes the boundary).
    Every local clock is NAND(CKPk, ENL) + inverter (same depth as r2f's buffer) so all flop clocks are
    low while EN=0 (r2f: TSPC reset NMOS fought QB with the clock high, 10.2 mA extracted EN=0)."""
    c = Cell('wc_front')
    c.inv('ENB', 'ENL', 2, 4)
    c.inv('RCS', 'RCSB', 1, 2)
    c.inv('RCSB', 'RCSL', 1, 2)

    def gclk(src, y):      # EN-gated local clock buffer: low while EN = 0
        c.nand([src, 'ENL'], y + '_g', 2, 4)
        c.inv(y + '_g', y, 2, 4)
    for j in range(8):
        gclk(f'CKP{(j + 4) % 8}', f'PC{j}')
        c.ff(f'PC{j}', f'S{j}', f'F{j}')
        gclk(f'CKP{j}', f'PR{j}')
        c.ff(f'PR{j}', f'S{j}', f'FR{j}')
    # align stages on locally gated CKP0 / CKP4 (<= 4 flops per local buffer: TSPC needs sharp edges)
    gclk('CKP0', 'CKF1')
    gclk('CKP4', 'CNF')
    c.ff('CKF1', 'F0', 'A0')
    c.ff('CKF1', 'A0', 'Z0')
    gclk('CKP0', 'CKF2')
    for j in range(1, 5):
        c.ff('CNF', f'F{j}', f'B{j}')
        c.ff('CKF2', f'B{j}', f'Z{j}')
    gclk('CKP0', 'CKF3')
    for j in range(5, 8):
        c.ff('CKF3', f'F{j}', f'Z{j}')
    # RCS=1 alignment
    gclk('CKP0', 'CKH0')
    gclk('CKP0', 'CKH1')
    for j in range(0, 5):
        c.ff('CKH0' if j < 3 else 'CKH1', f'FR{j}', f'H{j}')
    gclk('CKP4', 'CNG')
    for j in range(5, 8):
        c.ff('CNG', f'FR{j}', f'H{j}')
    # both octets re-registered on CKP0 (24), then the static data mux into O (32)
    for blk in range(4):
        gclk('CKP0', f'CKQ{blk}')
        for j in (2 * blk, 2 * blk + 1):
            c.ff(f'CKQ{blk}', f'Z{j}', f'P{j}')
            c.ff(f'CKQ{blk}', f'H{j}', f'Q{j}')
    for j in range(8):
        c.nand([f'P{j}', 'RCSB'], f'M{j}a')
        c.nand([f'Q{j}', 'RCSL'], f'M{j}b')
        c.nand([f'M{j}a', f'M{j}b'], f'M{j}')
    gclk('CKP0', 'CKO0')
    gclk('CKP0', 'CKO1')
    for j in range(8):
        c.ff('CKO0' if j < 4 else 'CKO1', f'M{j}', f'O{j}r')
    gclk('CKP0', 'CKF4')
    for j in range(4, 8):                 # previous cycle's phases 4..7 (full-rate data, psel 4..7)
        c.ff('CKF4', f'O{j}r', f'OP{j}r')
    # r2: O / OP drive the lane row over a long route (r1: the TSPC's 2/4 NOR output, ~1.1 ns extracted)
    for j in range(8):
        c.bufx(f'O{j}r', f'O{j}')
    for j in range(4, 8):
        c.bufx(f'OP{j}r', f'OP{j}')
    ports = [f'CKP{k}' for k in range(8)] + [f'S{j}' for j in range(8)] + ['ENB', 'RCS'] + \
        [f'O{j}' for j in range(8)] + [f'OP{j}' for j in range(4, 8)]
    # r5: gate groups in reverse order, so the O/OP output stage sits at the LEFT end of the 1356 um row, over the
    # lane and PD cells (x 0-740 um): r4's O nets ran ~1000 um along the row edge, 240 fF each with 107 fF to each
    # neighbour, and O changed 1.1-1.5 ns after CKP0 extracted (probe), which every O consumer (lanes, PD) pays
    c.reverse_groups()
    return c.row(ports)


def lane():
    c = Cell('wc_lane')
    # full-rate 8:1 selections DF = O[psel], EF = O[psel+4]
    for nm, off in (('DF', 0), ('EF', 4)):
        zs = []
        for k in range(8):
            z = f'{nm}z{k}'
            # data for psel 4..7 from the previous cycle (OP), so the edge (psel+4) lies after it
            src = f'OP{k}' if (off == 0 and k >= 4) else f'O{(k + off) % 8}'
            c.nand([f'PS{k}', src], z)
            zs.append(z)
        c.nand(zs[:4], f'{nm}a')
        c.nand(zs[4:], f'{nm}b')
        c.inv(f'{nm}a', f'{nm}an', 1, 2)
        c.inv(f'{nm}b', f'{nm}bn', 1, 2)
        c.nand([f'{nm}an', f'{nm}bn'], nm)
    for j in range(4):
        c.aoi3([('BQ', f'O{2 * j}'), ('BH', 'O0' if j % 2 == 0 else 'O4'), ('BF', 'DF')], f'DL{j}r')
        c.aoi3([('BQ', f'O{2 * j + 1}'), ('BH', 'O2' if j % 2 == 0 else 'O6'), ('BF', 'EF')], f'EL{j}r')
        # r2: each lane drives 5 pairs across the pair array (r1: NAND3 with a 2 um pull-up, ~1.3 ns)
        c.bufx(f'DL{j}r', f'DL{j}')
        c.bufx(f'EL{j}r', f'EL{j}')
    # r5: port (= top channel-track) order interleaves the octet with the static phase/mode selects, so no O/OP track
    # runs beside another switching O/OP track (r4: ~107 fF O(k)-O(k+1) over the LN/PD channel, data-dependent
    # Miller doubling, O delay 1.1-1.5 ns after CKP0)
    ports = [x for j in range(8) for x in (f'O{j}', f'PS{j}')] + \
        [x for j, sel in zip(range(4, 8), ('BQ', 'BH', 'BF', None)) for x in ((f'OP{j}', sel) if sel else (f'OP{j}',))] + \
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
        c.inv(n, n + 'n', 1, 2)

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


def gear():
    """r5 (AC-1/S3 40-bit boundary): one extra 2:1 stage after the 20-bit word, clocked by a delayed copy of the
    word-load pulse (GWT, wc_ctl's private GW copy) alone: the gear loads the word just loaded into DW, GEAR_DELAY
    inverters after GW (see below), with the rest of the word time as hold.  T toggles at every delayed-GW
    fall (stable while the delayed GW is high).  T = 0: L <= DW; T = 1: DX[19:0] <= L, DX[39:20] <= DW, so DX holds {later,
    earlier} for two words, word 0 (earliest) in the low bits.  WCLK40 = T: DX changes at a GW rise while WCLK40 is
    high, half a ring cycle before its fall; the macro samples DX on the WCLK40 rise (contract unchanged, AC3-W5).
    r4 clocked the gear from CK/CKN and a word-load enable ELWO routed from wc_ctl: extracted, ELWO (half-period
    path over ~600 um, 149 fF coupling to the r5b private CK copy) mis-timed GWD and DX never loaded (q625 5/5 DX
    words wrong), and the gear loaded the shared CK/CKN nets."""
    c = Cell('wc_gear')
    # r5d: the gear loads the NEW word, GEAR_DELAY inverters after GW.  r5c captured the previous word on the GW
    # rise itself, a race between two equal-depth paths (GW -> pair buffer -> W flop -> DW bufx, ~7 gates, against
    # GWT -> gear clock, ~5 gates): schematic q625 took the new word (DX 5/5 wrong).  A delay of 20 inverters plus
    # the 4-gate clock path (~24 gate delays vs ~7 for DW) scales with corner like the DW path, and the next GW is
    # >= 5 ring cycles away (quarter rate).
    c.buf('GWT', 'GWD0')
    prev = 'GWD0'
    for k in range(GEAR_DELAY):
        nxt = 'GWGr' if k == GEAR_DELAY - 1 else f'GWD{k + 1}'
        c.inv(prev, nxt, 1, 2)
        prev = nxt
    # r5f: the T flop clock is low while EN = 0 (NOR with ENB): an inverter of the (low) pulse held it high, so the
    # TSPC reset fought the clock -- the r4 gear did the same with GWDN (schematic safe_q625 410 uA, limit 10 uA)
    c.nor2('GWGr', 'ENB', 'GWN', 2, 4)
    c.ff('GWN', 'TB', 'Tq', keep=True)
    c.inv('Tq', 'TB', 1, 2)
    # r5e: the pulse and T are distributed along the 1.3 mm row by strong buffers and every block makes its own
    # clock (NAND + inverter).  r5d drove one NAND output (2 um) per word type into 5/10 block inverters spread over
    # the row: extracted, the 0.8 ns pulse never reached the far blocks (DX never loaded; schematic was clean).
    c.bufx('GWGr', 'GWG')
    c.bufx('Tq', 'T')
    for blk in range(5):                 # T = 0 words: load L
        c.inv('T', f'TL{blk}', 1, 2)
        c.nand(['GWG', f'TL{blk}'], f'GLB{blk}')
        c.inv(f'GLB{blk}', f'GL{blk}', 2, 4)
        for i in range(4 * blk, 4 * blk + 4):
            c.ff(f'GL{blk}', f'DW{i}', f'L{i}', keep=True)
    for blk in range(10):                # T = 1 words: load DX
        c.nand(['GWG', 'T'], f'GXB{blk}')
        c.inv(f'GXB{blk}', f'GX{blk}', 2, 4)
        for i in range(4 * blk, 4 * blk + 4):
            src = f'L{i}' if i < 20 else f'DW{i - 20}'
            c.ff(f'GX{blk}', src, f'DX{i}', keep=True)
    c.bufx('Tq', 'WCLK40')
    # r6 antenna: GWT ratio 1763, DW0/DW1 403-409 (ANT.3 limit 400): N+ diodes on GWT (3 columns) and every DW input
    c.diode('GWT', 3)
    for i in range(20):
        c.diode(f'DW{i}')
    ports = ['GWT', 'ENB'] + [f'DW{i}' for i in range(20)] + [f'DX{i}' for i in range(40)] + ['WCLK40']
    return c.row(ports)


PD_DELAY = 6         # r5g PD vote-clock delay after CKP0 (inverters, even)
GEAR_DELAY = 20      # r5d gear load delay (inverters, even): ~1.3 ns tt, > 2x the DW path


CELLS = dict(wc_pair=pair, wc_cnt=cnt, wc_slot0=lambda: slot(0), wc_slot1=lambda: slot(1),
             wc_ctl=ctl, wc_front=front, wc_lane=lane, wc_pd=pd, wc_gear=gear)


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
             [f'UP{k}' for k in range(4)] + [f'DN{k}' for k in range(4)] + [f'DX{i}' for i in range(40)] +
             ['WCLK40', 'VDD', 'VSS'])


def top_instances():
    """(instance name, cell, connections in cell port order)."""
    P = {n: CELLS[n]()[1] for n in CELLS}
    out = []

    def add(inst, cell, m):
        out.append((inst, cell, [m.get(p, p) for p in P[cell]]))
    add('XCTL', 'wc_ctl', {})
    add('XFR', 'wc_front', {})
    add('XLN', 'wc_lane', {})
    add('XCN', 'wc_cnt', {})
    add('XSL0', 'wc_slot0', {})
    add('XSL1', 'wc_slot1', {})
    add('XPD', 'wc_pd', {})
    add('XGR', 'wc_gear', {})
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
    # r4: vote outputs into the pt_cdr pins (~100 fF of route + gate), DX/WCLK40 into macro pins (~50 fF)
    lines += [f'CUP{k} up{k} 0 100f' for k in range(4)] + [f'CDN{k} dn{k} 0 100f' for k in range(4)]
    lines += [f'CDX{i} dx{i} 0 50f' for i in range(40)] + ['CWC wclk40 0 50f']
    T_end = t0 + ncyc * T
    outs = ' '.join(f'v(dw{i})' for i in range(20)) + ' ' + ' '.join(f'v(ew{i})' for i in range(20))
    outs += ' ' + ' '.join(f'v(up{k})' for k in range(4)) + ' ' + ' '.join(f'v(dn{k})' for k in range(4))
    outs += ' ' + ' '.join(f'v(dx{i})' for i in range(40)) + ' v(wclk40)'
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
            omax = float(np.max(d[t > 3e-9, 2:91]))
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
        # r4 gear: DX sampled at WCLK40 rises must be two consecutive words of the stream ({later, earlier})
        wc = d[:, 90] > vdd / 2
        rises = [t[i] for i in range(1, len(t)) if wc[i] and not wc[i - 1]]
        dxs = []
        for tr_ in rises:
            k = int(np.searchsorted(t, tr_ - 50e-12))
            dxs.append([int(v > vdd / 2) for v in d[k, 50:90]])
        dxs = dxs[2:]
        dx_err = None
        if best and dxs:
            # against the line PRBS itself (the DW stream window above ends before the last DX word)
            sstr = ''.join(map(str, bits))
            dx_err = 0
            prev = None
            for w in dxs:
                lo, hi = ''.join(map(str, w[:20])), ''.join(map(str, w[20:]))
                pos = sstr.find(lo + hi)
                # consecutive DX words must also be 40 line bits apart (mod the PRBS7 period)
                ok_ = pos >= 0 and (prev is None or (pos - prev - 40) % 127 == 0)
                dx_err += 0 if ok_ else 1
                prev = pos if pos >= 0 else None
        gear_ok = bool(dxs) and len(dxs) >= max(1, (len(ws) - 4) // 2 - 1) and dx_err == 0
        return dict(words=len(ws), bits=len(stream), offset=best[0] if best else None, dw_err_bitpos=err_pos,
                    vote_activity=dict(zip([f'UP{k}' for k in range(4)] + [f'DN{k}' for k in range(4)], act)),
                    pd_ok=pd_ok, dx_words=len(dxs), dx_word_errors=dx_err, gear_ok=gear_ok,
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
        shutil.copy(HERE / 'generated' / 'wrx_cap.ext.spice', work / 'cap.spice')
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
def build_top(rows=None, max_row_width=420.0):
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
        rows = [['CTL'], ['FR'], ['LN', 'PD'], ['CN', 'SL0'], ['SL1']] + \
               [[f'P{i}' for i in range(k, min(k + 4, 20))] for k in range(0, 20, 4)] + [['GR']]
    # r5h: the vote outputs as one trunk group flanked by static mode/select ports (r5g: CKP0's trunk beside UP3,
    # 68 fF: 0.6 V spikes on UP3 with EN = 0 and an extra 68 fF on one ring phase)
    rep = le.generate(work, 'pt_wrx_cap', ports, devices, rows=rows, max_row_width=max_row_width,
                      trunk_groups=[['RCS'] + [f'UP{k}' for k in range(4)] + [f'DN{k}' for k in range(4)] + ['B2']])
    defs = ''.join((FAST / f'{m}.spice').read_text() for m in CELLS)
    top_sp = tn.flat_spice(ports, devices, 'pt_wrx_cap')
    ant = le.ad.spice_lines(rep.get('antenna_diodes', []))   # K1 antenna diodes -> LVS reference
    if ant:
        k = top_sp.rstrip().rfind('.ends')
        top_sp = top_sp[:k] + '\n'.join(ant) + '\n' + top_sp[k:]
    (work / 'schematic.spice').write_text(defs + top_sp)
    lvs = le.netgen_lvs(work, 'pt_wrx_cap.lvs.spice', 'pt_wrx_cap', 'schematic.spice', 'pt_wrx_cap')
    gen = HERE / 'generated'
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
