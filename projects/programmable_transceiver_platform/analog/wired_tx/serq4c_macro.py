"""wtx_serq4c: the conventional CMOS quarter-rate core of pt_wiredtx as one hand-placed macro
(user decision 2026-11-10, path A = the guaranteed path for every rate <= 2.5 Gb/s).

Same compact cells as serq4_macro (phase slices wtx_qph, stream registers wtx_sreg5, TSPC hops,
static /5 counter), but:
  * quarter rate only.  With WT12 (half / full rate = 2x / 4x bit repetition of the user word in
    front of the core, cells.rep) the core always runs at ring x 4; the half / full phase generators
    (HA..JD toggle / Johnson flops) are gone.  MQ / MH / MF stay ports (the parent ties MQ = VDD,
    MH = MF = VSS); each slice's half / full inputs HB / FC are tied to MH / MF.
  * CMOS 4:1 window mux output stage (OMUX_CELL), no CML stage.

    python3 serq4c_macro.py cells     # (re)build the output-stage cell(s) only
    python3 serq4c_macro.py top       # wtx_serq4c -> generated/fast/wtx_serq4c.*
"""
import os
import sys

import serq4_macro as M

NAME = 'wtx_serq4c'
OMUX_CELL = os.environ.get('SERQ4C_OMUX', 'wtx_omuxt')
TOP_PORTS = [p for p in M.TOP_PORTS]          # D0..D19 PH* SERQ MQ MH MF Y YB DP DPB WCKQ VDD VSS
TOP_PORTS = TOP_PORTS[:-2] + ['R2', 'R4'] + TOP_PORTS[-2:]   # session 8: repetition mode (postcursor latch)


def g_tg(pre, a, en, enb, y, wn, wp):
    """Transmission gate a -> y (N gate en, P gate enb)."""
    cols = [dict(k='c', n=a, p='-'), M.G(en, wn, n=True, p=False), dict(k='c', n=y, p='-'), M.BRK,
            dict(k='c', n='-', p=a), M.G(enb, p=True, n=False, wp=wp), dict(k='c', n='-', p=y)]
    net = [M._fet(f'{pre}n', y, en, a, 'n', wn), M._fet(f'{pre}p', y, enb, a, 'p', wp)]
    return cols, net


M.GATES['tg'] = g_tg


def g_tsinv(pre, a, en, enb, y, wn, wp):
    """Clocked (tristate) inverter y = !a while en (C2MOS: a next to the rails, en / enb next to y)."""
    cols = [M.C('VSS', 'VDD', same=False), M.G(a, wn, wp), dict(k='c', n=None, p=None),
            M.G(en, wn, wp, netn=en, netp=enb), M.C(y, y)]
    net = [M._fet(f'{pre}na', f'{pre}mn', a, 'VSS', 'n', wn), M._fet(f'{pre}ne', y, en, f'{pre}mn', 'n', wn),
           M._fet(f'{pre}pa', f'{pre}mp', a, 'VDD', 'p', wp), M._fet(f'{pre}pe', y, enb, f'{pre}mp', 'p', wp)]
    return cols, net


M.GATES['tsinv'] = g_tsinv


def omuxt():
    """Output stage, one row: window gates S k = QW k & QW k-1 (NAND2W + INVW, as wtx_omux), stream
    complements FN k, and four 4:1 window muxes built as a two-level NAND tree instead of wtx_mux4's
    NAND4:  Z k = NAND(S k, A k);  U01 = NAND(Z0, Z1) = T0 | T1;  U23 = T2 | T3;
    V = !U (INV);  out = NAND(V01, V23) = OR k (S k & A k);  then an INV -> INV output buffer.
    Why: extracted ss/22/3.15 at 2.5 Gb/s the NAND4 (four series NMOS of 6 um, a 16 um-PMOS-drain
    output node) gave slow, data-dependent falling edges: 371 ps pp jitter, 2 errors (session 3).
    Every stage here is a 2-stack, so rise / fall are fast and symmetric at every corner."""
    ports = [f'QW{k}' for k in range(4)] + [f'F{k}' for k in range(4)] + ['Y', 'YB', 'DP', 'DPB'] + \
        [f'S{k}' for k in range(4)] + ['dA1', 'dA2', 'dA3', 'dbA1', 'dbA2', 'dbA3']
    # Session 8 postcursor in the repetition modes (WT19: the digital repeats each user bit rep times on the
    # core, aligned to word bit 0).  The postcursor must be one LINE bit late.  DP window k normally carries
    # F(k-1); per mode the four window inputs A k are (static selects, mode bits R2 / R4):
    #   rep1: F3 F0 F1 F2      rep2: F3 F3 F1 F1      rep4: F3 F3 G G
    # F k is stable from window k-1 to window k+2 (hop timing), so F3 serves windows 0-1 and F1 windows 2-3.
    # rep4 needs the previous cycle's bit in windows 2-3 too, after F3 has moved on: G is F3 caught by a
    # clocked-inverter latch transparent in window 1 (S1) and held through windows 2-3.  The window selects
    # S k and the output path are unchanged, so MAIN -> POST skew is as before.  (A window-rate latch on DP,
    # tried first, needed a < 1 core-UI enable that the ss corner could not drive: DP stuck at 0.7 V.)
    gates = []
    for k in range(4):
        gates += [(f'w{k}n', 'NAND2W', f'QW{k}', f'QW{(k - 1) % 4}', f'SN{k}'), (f'w{k}i', 'INVWS', f'SN{k}', f'S{k}')]
    gates += [(f'c{k}', 'INV4', f'F{k}', f'FN{k}') for k in range(4)]
    for m, a, y in (('y', [f'F{k}' for k in range(4)], 'Y'), ('yb', [f'FN{k}' for k in range(4)], 'YB'),
                    ('d', ['F3', 'dA1', 'dA2', 'dA3'], 'DP'),
                    ('db', ['FN3', 'dbA1', 'dbA2', 'dbA3'], 'DPB')):
        gates += [(f'{m}z{k}', 'NANDZ', f'S{k}', a[k], f'{m}Z{k}') for k in range(4)]
        gates += [(f'{m}u0', 'NANDU', f'{m}Z0', f'{m}Z1', f'{m}U0'), (f'{m}u1', 'NANDU', f'{m}Z2', f'{m}Z3', f'{m}U1'),
                  (f'{m}v0', 'INVV', f'{m}U0', f'{m}V0'), (f'{m}v1', 'INVV', f'{m}U1', f'{m}V1'),
                  (f'{m}o', 'NANDO', f'{m}V0', f'{m}V1', f'{m}X'), (f'{m}b', 'INVB', f'{m}X', f'{m}XB'),
                  (f'{m}p', 'INVP', f'{m}XB', y)]
    # Session 8 slot overlap: probe s8/p3 (ss/32/3.15, 2.5 Gb/s): windows overlap 0.16 UI at nominal C but leave
    # 0.05-UI gaps with the pessimistic C (+25 % device, +15 % wire), and a gap glitches the OR tree for two equal
    # bits.  The window driver INVW is skewed (wider PMOS, narrower NMOS: S k rises early and falls late) to
    # add a fixed overlap.  (A NOR set/reset latch on the true/complement trees, tried first, was too slow to
    # follow 0.5-UI tree pulses at ss: 23 errors.)
    return M.row_of('wtx_omuxt', gates, ports)


def ppost():
    """Postcursor sources for the repetition modes (session 8), a row of its own next to the counter so
    the output-mux row keeps its size (its growth cost the 3.24 Gb/s ss margin: 27 errors).  See omuxt:
    window inputs rep1 F3 F0 F1 F2, rep2 F3 F3 F1 F1, rep4 F3 F3 G G; G = F3 caught in window 0
    (clocked inverter on S0, held windows 1-3; F3 changes at window 2.4, probe s8/p2).  The sources have >= 1.5 windows of slack, so the extra
    gate levels and the route to the output-mux row are off the critical path."""
    ports = [f'F{k}' for k in range(4)] + ['S0', 'R2', 'R4', 'dA1', 'dA2', 'dA3', 'dbA1', 'dbA2', 'dbA3']
    gates = [('ra', 'NOR2S', 'R2', 'R4', 'R1'), ('rb', 'INV1', 'R1', 'R1N'), ('rc', 'INV1', 'R4', 'R4N'),
             ('s0', 'INV2', 'S0', 'SN0')]
    gates += [(f'c{k}', 'INV2', f'F{k}', f'FN{k}') for k in range(4)]
    gates += [('gl', 'TSL', 'F3', 'S0', 'SN0', 'GB'), ('gi', 'INV4', 'GB', 'G')]
    for m, F, Gs in (('d', 'F', 'G'), ('db', 'FN', 'GB')):
        gates += [(f'{m}a1', 'NAND4', f'{F}0', 'R1', f'{m}A1a'), (f'{m}a1b', 'NAND4', f'{F}3', 'R1N', f'{m}A1b'),
                  (f'{m}a1o', 'NANDP', f'{m}A1a', f'{m}A1b', f'{m}A1'),
                  (f'{m}a2', 'NAND4', f'{F}1', 'R4N', f'{m}A2a'), (f'{m}a2b', 'NAND4', Gs, 'R4', f'{m}A2b'),
                  (f'{m}a2o', 'NANDP', f'{m}A2a', f'{m}A2b', f'{m}A2'),
                  (f'{m}a3', 'NAND4', f'{F}2', 'R1', f'{m}A3a'), (f'{m}a3b', 'NAND4', f'{F}1', 'R2', f'{m}A3b'),
                  (f'{m}a3c', 'NAND4', Gs, 'R4', f'{m}A3c'), (f'{m}a3o', 'NAND3P', f'{m}A3a', f'{m}A3b', f'{m}A3c', f'{m}A3')]
    r, p_, n_ = M.row_of('wtx_ppost', gates, ports)
    r.track_order = ['S0', 'SN0']     # split S0 / SN0 gate column of the G latch: N net on the lower track
    return r, p_, n_


def sreg5d():
    """wtx_sreg5 with the load decode local: LDA = NOR(DA, DC) in the stream's own row, straight into its
    TSPC LD flop (the cell otherwise equals serq4_macro.sreg5).
    Why (session 6, extracted ss/22/3.15, 3.24 Gb/s core): the shared decode NOR2X -> INV4 -> INV8 in
    wtx_q4ctl plus the LDA trunk to the four stream rows made the counter-to-LD-flop path 1.34 ns against
    a 1.235 ns register period: LDA rose 90 ps before the capturing edge, the LD flop caught it late and
    held LD for two periods, so the fifth bit of every stream repeated the fourth (16/140 core-UI errors,
    positions 16..19 of every word).  Local NOR: path = counter clock-to-Q + DA/DC wire + one NOR."""
    r, ports, net = M.sreg5()
    ports = [p_ for p_ in ports if p_ != 'LDA']
    ports = ports[:6] + ['DA', 'DC'] + ports[6:]
    c, n = M.g_nor2('ld', 'DA', 'DC', 'LDA', *M.SIZE['NOR2L'][1:])
    cols = c + [M.BRK] + r.cols
    net = n + net
    row = M.compact.Row('wtx_sreg5d', cols, ports=[p_ for p_ in ports if p_ not in M.RAILS], wn=2, wp=4)
    row.track_order = r.track_order
    return row, ports, net


def _dff6q(p, d, ck, q, qb):
    """serq4_macro._dff6 with 4/4 um output NANDs (q, qb): the 2/2 output pair, loaded by the next flop,
    the feedback NOR and the decode, did not finish flipping inside a 0.6 ns clock-high phase (extracted
    ss/22/3.15, 3.24 Gb/s core: flop B rose to 1.2 V and fell back when CK fell, the counter ran /6)."""
    g = M._dff6(p, d, ck, q, qb)
    return g[:4] + [(f'{p}5', 'NANDQ', f'{p}n2', qb, q), (f'{p}6', 'NANDQ', f'{p}n3', q, qb)]


def div5r():
    """Static /5 word counter (a <- NOR(b, c), b <- a, c <- b; abc 000 -> 100 -> 110 -> 011 -> 001, self-
    starting) plus a registered load flag LDR in the counter domain: LDR <= C & !B (state 001), so LDR is
    high exactly during state 000 and is a flop output (glitch-free).
    Why (session 6): the earlier decode NOR(A, C) changes on 110 -> 011 with A falling and C rising in the
    same edge; extracted ss the flops' clock-to-Q differ by ~0.5 ns, NOR(A, C) pulsed for 0.58 ns and the
    stream LD flops loaded twice per word.  The wtx_q4ctl NOR2X -> INV4 -> INV8 chain swallowed that pulse
    but made the counter -> LD-flop path 1.34 ns against a 1.235 ns register period at 3.24 Gb/s.
    Feedback / decode NORs are small (1/4 um) so the flop outputs carry little load."""
    gates = [('nr', 'NOR2S', 'B', 'C', 'DA')] + _dff6q('fa', 'DA', 'CK', 'A', 'AN') + \
        _dff6q('fb', 'A', 'CK', 'B', 'BN') + _dff6q('fc', 'B', 'CK', 'C', 'CN') + \
        [('ld', 'NOR2S', 'CN', 'B', 'LDD')] + _dff6q('fl', 'LDD', 'CK', 'LDR', 'LDRN') + \
        [('la', 'INV2', 'LDR', 'LB2'), ('lb', 'INV8', 'LB2', 'LDO'),
         ('ca', 'INV2', 'C', 'CB2'), ('cb', 'INV4', 'CB2', 'CO'), ('ed', 'INV1', 'ENB', 'ENX')]
    return M.row_of('wtx_div5r', gates, ['CK', 'ENB', 'CO', 'LDO'])


def q4ctlc():
    """wtx_q4ctl without the shared load decode (now local in wtx_sreg5d): reset chain + WORD_CLK buffer."""
    gates = [('ri', 'INV2', 'SERQ', 'QRA'), ('rj', 'INV4', 'QRA', 'QRB'), ('rk', 'INV8', 'QRB', 'QRST'),
             ('wa', 'INV4', 'DC', 'WCN'), ('wb', 'INV16', 'WCN', 'WCKQ')]
    return M.row_of('wtx_q4ctlc', gates, ['SERQ', 'QRST', 'DC', 'WCKQ'])


# sizes (n um, p um) of the tree; the window pulse drives NANDZ's series input next to the output
M.SIZE.update(INVWS=('inv', float(os.environ.get('INVWS_N', '6')), float(os.environ.get('INVWS_P', '24'))), NANDQW=('nand2', 12, 6), INVQW=('inv', 8, 40), TSL=('tsinv', 4, 8), NANDP=('nand2', 6, 6), NAND3P=('nand3', 4, 6), NANDZ=('nand2', 4, 3), NANDU=('nand2', 8, 6), INVV=('inv', 8, 16), NANDO=('nand2', 8, 6),
              INVB=('inv', 6, 12), INVP=('inv', 8, 16), NOR2L=('nor2', 2, 8), NOR2S=('nor2', 1, 4), NANDQ=('nand2', 4, 4))
def qphw():
    """wtx_qph with a skewed QW driver (session 8, slot overlap): QW high must exceed 2 core UI so the windows
    S k = QW k & QW k-1 overlap.  Measured QW 1.75 UI wide and S k 0.95 UI with 0.05-UI gaps (pessimistic ss:
    S at 2.9 V, glitches in the NAND-OR tree).  Fast QW rise (strong NAND pull-down, wide PMOS) and slow fall
    (narrow NMOS) widen QW."""
    M.QW_NAND, M.QW_INV = 'NANDQW', 'INVQW'
    try:
        return M.qph()
    finally:
        M.QW_NAND, M.QW_INV = 'NAND2E', 'INV16'


M.CELLS.update(wtx_ppost=ppost,   # qphw (skewed QW) tried session 8: ss 2.5 nominal 0 -> 13 errors; not used
                wtx_omuxt=omuxt, wtx_sreg5d=sreg5d, wtx_q4ctlc=q4ctlc, wtx_div5r=div5r)
CELLS = ['wtx_qph', 'wtx_sreg5', 'wtx_q4ctlc', 'wtx_q4ck', 'wtx_tspcb', 'wtx_tspcbx', 'wtx_div5r', 'wtx_ppost', OMUX_CELL]


def top_instances():
    V = ['VDD', 'VSS']
    out = [('XCTL', 'wtx_q4ctlc', ['SERQ', 'QRST', 'DC', 'WCKQ'] + V),
           ('XCK', 'wtx_q4ck', ['QKN0', 'QKN1', 'QDN', 'QK0', 'QK1', 'QD'] + V),
           ('XDV', 'wtx_div5r', ['QD', 'QRST', 'DC', 'LDA'] + V)]
    ph = ['PH0', 'PH90', 'PH180', 'PH270']
    for k in range(4):
        xn = ['QKN0', 'QKN1', 'QDN'] if k == 2 else [f'CXN{k}_{d}' for d in range(3)]
        out.append((f'XP{k}', 'wtx_qph', [ph[k], 'SERQ', 'MQ', 'MH', 'MF', 'MH', 'MF', f'G{k}'] + xn
                    + [f'QW{k}', f'Q{k}'] + V))
    for k in range(4):
        out.append((f'XL{k}', 'wtx_sreg5', [f'D{k + 4 * j}' for j in range(5)]
                    + ['VSS', 'LDA', 'QK0' if k < 2 else 'QK1', 'QRST', f'B{k}_0'] + V))
    for k, seq in M.HOPS.items():
        prev = f'B{k}_0'
        for i, q in enumerate(seq):
            o = f'F{k}' if i == len(seq) - 1 else f'R{k}_{i}'
            cell = 'wtx_tspcbx' if i == len(seq) - 1 else 'wtx_tspcb'
            out.append((f'XH{k}_{i}', cell, [f'Q{q}', prev, o, 'QRST'] + V))
            prev = o
    # streams arrive inverted (sreg5): F k = NOT(bit), so the true / complement outputs are swapped
    out.append(('XO', OMUX_CELL, [f'QW{k}' for k in range(4)] + [f'F{k}' for k in range(4)]
                + ['YB', 'Y', 'DPB', 'DP'] + [f'S{k}' for k in range(4)]
                + ['PA1', 'PA2', 'PA3', 'PB1', 'PB2', 'PB3'] + V))
    out.append(('XPP', 'wtx_ppost', [f'F{k}' for k in range(4)] + ['S0', 'R2', 'R4',
                                     'PA1', 'PA2', 'PA3', 'PB1', 'PB2', 'PB3'] + V))
    return out


# floorplan (bottom to top): stream rows 0/1, the four phase slices with the reset / clock-driver cells, the
# output mux with the counter, stream rows 2/3.  Every F k and hop phase Q spans at most two rows, QW one.
# (Session 6 area pass: the control / counter cells had a 171-um row of their own; 530 x 353 -> see build log.)
ROWS = [['L0', 'H0_0', 'H0_1', 'L1', 'H1_0', 'H1_1', 'H1_2'],
        ['P0', 'P1', 'P2', 'P3', 'CK', 'CTL'],
        ['O', 'PP', 'DV'],
        ['L2', 'H2_0', 'H2_1', 'H2_2', 'L3', 'H3_0', 'H3_1', 'H3_2']]


def top_spice():
    body = [f'.subckt {NAME} {" ".join(TOP_PORTS)}']
    body += [f'{i} {" ".join(c)} {cell}' for i, cell, c in top_instances()]
    return '\n'.join(body + [f'.ends {NAME}']) + '\n'


def macro_text():
    return ''.join((M.FAST / f'{n}.spice').read_text() for n in CELLS)


def build_top():
    return M.build_le(NAME, TOP_PORTS, top_spice(), macro_text(), ROWS, CELLS, max_row_width=560.0,
                      workname='topc')


if __name__ == '__main__':
    what = sys.argv[1] if len(sys.argv) > 1 else 'top'
    if what == 'cells':
        for n in sys.argv[2:] or [OMUX_CELL, 'wtx_q4ctlc', 'wtx_div5r']:
            M.build_cell(n)
    elif what == 'top':
        build_top()
