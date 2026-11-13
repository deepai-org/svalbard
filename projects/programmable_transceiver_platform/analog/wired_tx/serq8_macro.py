"""wtx_serq8: dual-mode eighth-rate CMOS core of pt_wiredtx (coordinator decision WT23 / option 3, session 9).

One core for 0.3-3.24 Gb/s.  The ring's 8 phases (45 deg) clock 8 five-bit stream registers (the 40-bit word,
stream k = D(k + 8 j), D0 first on the line) and an 8:1 window mux; core rate = 8 x ring.  The digital repeats
every user bit n times (n = 1, 2, 4, 8; MODE_H / MODE_F), line rate = 8 x ring / n, ring 300-625 MHz:
    n = 1: 2.4 - 3.24 Gb/s (ring 300 - 405)      n = 2: 1.2 - 2.5    n = 4: 0.6 - 1.25    n = 8: 0.3 - 0.625
For n >= 2 (M2 = 1) adjacent slots carry the same bit, so the window gates switch to 2-slot windows (even k
only): no window is ever narrower than 1 / (8 x 405 MHz) = 309 ps, the proven 3.24 Gb/s slot.

Timing plan (slot units, register clock = phase 0; tcq ~ 1.3-1.5 slots):
  stream outputs B k change at 0 + 1.5, stable [1.5, 9.5);  hops (TSPC, wtx_tspcb):
    k = 0..4: one hop from B k at phase 4, 5, 6, 7, 0;   k = 5..7: B k at phase 4, then at phase 1, 2, 3.
  F k changes at k + 5.3, stable [k - 2.7, k + 5.3): window k (main) and k + 1 (postcursor) both inside with
  >= 2.7 slots either side.  Windows S k = QW k & QW k+5 (1 slot), or QW k & QW k+6 (2 slots, even k, M2).
Postcursor (one LINE bit late) window sources A k (see ppost8):
    k:   0    1    2            3    4         5    6                    7
         F7   F0   F1|F7(n4,8)  F2   F3|G(n8)  F4   F5|F3(n4)|G(n8)      F6
  G = F7 caught in window 0 (clocked inverter), held to window 7.

    python3 serq8_macro.py cells     # wtx_omux8, wtx_ppost8, wtx_qph8 (cell builds)
    python3 serq8_macro.py top       # wtx_serq8 -> generated/fast/wtx_serq8.*
"""
import os
import sys

import serq4_macro as M
import serq4c_macro as C4   # noqa: F401  (registers its SIZE entries, gate types and cells)

NAME = 'wtx_serq8'
PH = [f'PH{a}' for a in (0, 45, 90, 135, 180, 225, 270, 315)]
TOP_PORTS = [f'D{i}' for i in range(40)] + PH + ['SERQ', 'M2', 'R4', 'R8', 'Y', 'YB', 'DP', 'DPB', 'WCKQ', 'VDD', 'VSS']
QWD4 = os.environ.get('QWD4', '0') == '1'   # opening edge through 4 inverters (s9/c3: 2 gave 0.37-UI pulses)
HOPS8 = {0: (4,), 1: (5,), 2: (6,), 3: (7,), 4: (0,), 5: (4, 1), 6: (4, 2), 7: (4, 3)}

def g_aoi22(pre, a1, a2, b1, b2, y, wn, wp):
    """Y = !(A1 & A2 | B1 & B2): two column groups (A pair, B pair), internal z routed."""
    z = pre + 'z'
    cols = [dict(k='c', n='VSS', p=z), M.G(a2, wn, wp), dict(k='c', n=None, p=y), M.G(a1, wn, wp), dict(k='c', n=y, p=z),
            M.BRK, dict(k='c', n=y, p='VDD'), M.G(b1, wn, wp), dict(k='c', n=None, p=z), M.G(b2, wn, wp),
            dict(k='c', n='VSS', p='VDD')]
    net = [M._fet(pre + 'na1', y, a1, pre + 'm', 'n', wn), M._fet(pre + 'na2', pre + 'm', a2, 'VSS', 'n', wn),
           M._fet(pre + 'nb1', y, b1, pre + 'k', 'n', wn), M._fet(pre + 'nb2', pre + 'k', b2, 'VSS', 'n', wn),
           M._fet(pre + 'pa1', y, a1, z, 'p', wp), M._fet(pre + 'pa2', z, a2, y, 'p', wp),
           M._fet(pre + 'pb1', 'VDD', b1, z, 'p', wp), M._fet(pre + 'pb2', z, b2, 'VDD', 'p', wp)]
    return cols, net


def g_aoi21(pre, a1, a2, b, y, wn, wp):
    """Y = !(A1 & A2 | B)."""
    z = pre + 'z'
    cols = [dict(k='c', n='VSS', p=z), M.G(a2, wn, wp), dict(k='c', n=None, p=y), M.G(a1, wn, wp), dict(k='c', n=y, p=z),
            M.BRK, dict(k='c', n=y, p='VDD'), M.G(b, wn, wp), dict(k='c', n='VSS', p=z)]
    net = [M._fet(pre + 'na1', y, a1, pre + 'm', 'n', wn), M._fet(pre + 'na2', pre + 'm', a2, 'VSS', 'n', wn),
           M._fet(pre + 'nb', y, b, 'VSS', 'n', wn),
           M._fet(pre + 'pa1', y, a1, z, 'p', wp), M._fet(pre + 'pa2', z, a2, y, 'p', wp),
           M._fet(pre + 'pb', 'VDD', b, z, 'p', wp)]
    return cols, net


NF3 = int(os.environ.get('NF3', '3'))   # window NAND3 fingers (rev 7e: 3; rev 6-7d: 2)


def g_nand3x(pre, a, b, c, y, wn, wp):
    """NAND3 as NF3 parallel 4/8-um-per-device fingers (A next to the output)."""
    cols, net = [], []
    for f in range(NF3):
        c1, n1 = M.g_nand3(pre + f'f{f}', a, b, c, y, wn, wp)
        cols += ([M.BRK] if cols else []) + c1
        net += n1
    return cols, net


def _fingered(fn):
    """wrap a single-finger gate builder: total (wn, wp) split into parallel fingers of <= WN_MAX / WP_MAX."""
    import math

    def g(pre, *args):
        *pins, wn, wp = args
        nf = max(1, math.ceil(max(wn / M.WN_MAX, wp / M.WP_MAX) - 1e-9))
        cols, net = [], []
        for f in range(nf):
            c1, n1 = fn(pre + f'f{f}', *pins, wn / nf, wp / nf)
            cols += ([M.BRK] if cols else []) + c1
            net += n1
        return cols, net
    return g


M.GATES['nand3x'] = g_nand3x
M.GATES['aoi22'] = g_aoi22
M.GATES['aoi21'] = g_aoi21
M.GATES['nand3f'] = _fingered(M.g_nand3)
M.GATES['aoi22f'] = _fingered(g_aoi22)
M.GATES['aoi21f'] = _fingered(g_aoi21)
M.SIZE.update(NAND3X=('nand3x', 4, 8), AOIX=('aoi22', 4, 8), AOIY=('aoi21', 4, 8), NAND3W=('nand3', 4, 8), INVW8=('inv', float(os.environ.get('W8N', '12')), float(os.environ.get('W8P', '28'))), NOROUT=('nor2', 8, 32), NANDW8=('nand2', 4, 4), NANDX=('nand2', 4, 4))


def omux8():
    """Window gates and four 8:1 NAND-OR trees (Y, YB, DP, DPB).
    Window k: SN k = NAND2W(QWD k, X k), S k = INVWS(SN k), X k = M2 ? QW k+6 : QW k+5 (even k),
    M2 ? 0 : QW k+5 (odd k), built as a NAND-NAND static mux; QWD k = QW k through four inverters: probe s9/p1 (tt, 3.24 Gb/s) with two inverters
    and INVWS had 1.4-1.66-slot windows (the X mux path is slower), 13 errors; the extra delay on the opening edge
    trims the overlap.
    Tree: Z = NAND(S, A); U = NAND(Z, Z); V = INV; W = NAND(V, V) (= OR4); X = NOR(W0, W1); out = INVP(X)."""
    ports = [f'QW{k}' for k in range(8)] + [f'F{k}' for k in range(8)] + ['M2', 'Y', 'YB', 'DP', 'DPB'] + \
        [f'S{k}' for k in range(8)] + [f'dA{k}' for k in range(8)]
    # Windows (rev 2, probe s9/p3): both edges of a window are RISING edges of QW (S k = QW k & !QW k+1), so the
    # width is one slot plus one NAND delay whatever the QW duty cycle; the earlier QW k & QW k+5 window used a
    # rising and a falling edge from different paths and was 1.4-1.66 slots wide (or closed) -> errors.
    # 1-slot (M2 = 0):  SN k = NAND3(QW k, !(QW k+1 & M1), !(QW k+2 & M2))  (odd k: NAND3(QW k, !(QW k+1 & M1), M1))
    # 2-slot (M2 = 1, even k only): closed by QW k+2.
    # rev 3 (probe s9/p4): a 3-stack NAND3 window gate made 0.5-slot, 2.1-V runt windows; the window gate is a
    # NAND2W again, its closing input XC k = !(QW k+1 & M1) & !(QW k+2 & M2) (2 gates + INV) and its opening input
    # QW k through two inverters, so the window is one slot plus about one gate delay.
    gates = [('m1', 'INV2', 'M2', 'M1')]
    for k in range(8):
        # rev 6: opening edge = QW k itself (no gate), closing edge = QW k+1 (or k+2) through one NAND, window
        # gate a two-finger NAND3: one slot plus one NAND delay.  (rev 3-5: inverter / mux / AOI paths made
        # 0.5-slot runts, 1.65-1.8-slot overlaps, or closed windows; s9/p3-p5.)
        gates += [(f'x{k}a', 'NANDX', f'QW{(k + 1) % 8}', 'M1', f'XA{k}')]
        if k % 2 == 0:
            gates += [(f'x{k}b', 'NANDX', f'QW{(k + 2) % 8}', 'M2', f'XB{k}'),
                      (f'w{k}n', 'NAND3X', f'QW{k}', f'XA{k}', f'XB{k}', f'SN{k}')]
        else:
            gates += [(f'w{k}n', 'NAND3X', f'QW{k}', f'XA{k}', 'M1', f'SN{k}')]
        gates += [(f'w{k}i', 'INVW8', f'SN{k}', f'S{k}')]
    # rev 4: two trees only (each S k drives 2 NANDZ instead of 4 across a 550-um row); the complements are
    # inverters at the end (YB = !Y one inverter later than Y, matched for DP / DPB).
    for m, a, y in (('y', [f'F{k}' for k in range(8)], 'Y'), ('d', [f'dA{k}' for k in range(8)], 'DP')):
        gates += [(f'{m}z{k}', 'NANDZ', f'S{k}', a[k], f'{m}Z{k}') for k in range(8)]
        gates += [(f'{m}u{j}', 'NANDU', f'{m}Z{2 * j}', f'{m}Z{2 * j + 1}', f'{m}U{j}') for j in range(4)]
        gates += [(f'{m}v{j}', 'INVV', f'{m}U{j}', f'{m}V{j}') for j in range(4)]
        gates += [(f'{m}w{i}', 'NANDO', f'{m}V{2 * i}', f'{m}V{2 * i + 1}', f'{m}W{i}') for i in range(2)]
        # out = !X (three inversions), out B = X (two): the complement leads by one INV4
        gates += [(f'{m}x', 'NOROUT', f'{m}W0', f'{m}W1', f'{m}X'),
                  (f'{m}c', 'INV4', f'{m}X', f'{m}XC'), (f'{m}q', 'INV4', f'{m}XC', f'{m}XD'), (f'{m}p', 'INVP', f'{m}XD', y),
                  (f'{m}e', 'INV4', f'{m}X', f'{m}XE'), (f'{m}r', 'INVP', f'{m}XE', y + 'B')]
    return M.row_of('wtx_omux8', gates, ports)


def ppost8():
    """Postcursor window sources (see module docstring) for the d (F) and db (FN) trees."""
    ports = [f'F{k}' for k in range(8)] + ['S0', 'M2', 'R4', 'R8'] + [f'dA{k}' for k in range(8)]
    gates = [('s0', 'INV2', 'S0', 'SN0'), ('r8', 'INV1', 'R8', 'R8N'), ('ra', 'NOR2S', 'R4', 'R8', 'R48N'),
             ('rb', 'INV1', 'R48N', 'R48'), ('rc', 'NOR2S', 'R4', 'R8', 'N48')]
    gates += [('gl', 'TSL', 'F7', 'S0', 'SN0', 'GB'), ('gi', 'INV4', 'GB', 'G')]
    # R4X = R4 & !R8 (n = 4 only); NOT_R48 = !(R4 | R8)
    gates += [('r4x', 'NOR2S', 'R4N1', 'R8', 'R4X'), ('r4i', 'INV1', 'R4', 'R4N1')]
    for m, F, Gs in (('d', 'F', 'G'),):
        gates += [(f'{m}b0', 'INV2', f'{F}7', f'{m}A0n'), (f'{m}b0b', 'INV4', f'{m}A0n', f'{m}A0'),
                  (f'{m}b1', 'INV2', f'{F}0', f'{m}A1n'), (f'{m}b1b', 'INV4', f'{m}A1n', f'{m}A1'),
                  (f'{m}b3', 'INV2', f'{F}2', f'{m}A3n'), (f'{m}b3b', 'INV4', f'{m}A3n', f'{m}A3'),
                  (f'{m}b5', 'INV2', f'{F}4', f'{m}A5n'), (f'{m}b5b', 'INV4', f'{m}A5n', f'{m}A5'),
                  (f'{m}b7', 'INV2', f'{F}6', f'{m}A7n'), (f'{m}b7b', 'INV4', f'{m}A7n', f'{m}A7')]
        # A2 = (R4 | R8) ? F7 : F1
        gates += [(f'{m}2a', 'NAND4', f'{F}1', 'N48', f'{m}2x'), (f'{m}2b', 'NAND4', f'{F}7', 'R48', f'{m}2y'),
                  (f'{m}2o', 'NANDP', f'{m}2x', f'{m}2y', f'{m}A2')]
        # A4 = R8 ? G : F3
        gates += [(f'{m}4a', 'NAND4', f'{F}3', 'R8N', f'{m}4x'), (f'{m}4b', 'NAND4', Gs, 'R8', f'{m}4y'),
                  (f'{m}4o', 'NANDP', f'{m}4x', f'{m}4y', f'{m}A4')]
        # A6 = R8 ? G : (R4 ? F3 : F5)
        gates += [(f'{m}6a', 'NAND4', f'{F}5', 'N48', f'{m}6x'), (f'{m}6b', 'NAND4', f'{F}3', 'R4X', f'{m}6y'),
                  (f'{m}6c', 'NAND4', Gs, 'R8', f'{m}6z'), (f'{m}6o', 'NAND3P', f'{m}6x', f'{m}6y', f'{m}6z', f'{m}A6')]
    r, p_, n_ = M.row_of('wtx_ppost8', gates, ports)
    r.track_order = ['S0', 'SN0']
    return r, p_, n_


WNX = os.environ.get('WNX', '6,6')   # closing NAND (XA / XB) sizes, rev 7


def _qw_dummies(h):
    """rev 7c: equal load on every QW (s10/c2: QW0 / QW4, which fed both halves through the long route, were
    0.08 slot late -> windows 0.80-1.02 slot).  Every QW gets one NAND3X (opening) + three NANDXC (real XA / XB
    plus dummies NAND(QW, M1), outputs unused) and a gate in BOTH halves."""
    half = lambda k: k // 4
    out = {0: [], 1: []}
    for q in range(8):
        real = [half(q), half((q - 1) % 8)] + ([half((q - 2) % 8)] if (q - 2) % 2 == 0 else [])
        n = 4 - len(real)
        where = (1 - real[0]) if len(set(real)) == 1 else half(q)
        out[where] += [q] * n
    return out[h]


def _windows(ks, h):
    """rev 7 window gates for slots ks.  Opening edge QW k on the BOTTOM device of the NAND3 stack (slowest pin),
    closing edge QW k+1 / k+2 through one NAND (XA / XB).  rev 6 (QW k next to the output, 4/4 NANDs) gave
    1.06-1.31-slot windows at tt (s10/p1), rev 7b (bottom pin, 10/10) 0.80-1.02 (gaps -> 46 errors, s10/c2)."""
    gates = [('m1', 'INV2', 'M2', 'M1')]
    for k in ks:
        gates += [(f'x{k}a', 'NANDXC', f'QW{(k + 1) % 8}', 'M1', f'XA{k}')]
        if k % 2 == 0:
            gates += [(f'x{k}b', 'NANDXC', f'QW{(k + 2) % 8}', 'M2', f'XB{k}'),
                      (f'w{k}n', 'NAND3X', f'XA{k}', f'XB{k}', f'QW{k}', f'SN{k}')]
        else:
            gates += [(f'w{k}n', 'NAND3X', f'XA{k}', 'M1', f'QW{k}', f'SN{k}')]
        gates += [(f'w{k}i', 'INVW8', f'SN{k}', f'S{k}')]
        # equal S k load: every window drives one INV2 (only S0P, the wtx_ppost8 G-latch copy, is used)
        gates += [(f'w{k}p', 'INV2', f'SN{k}', f'S{k}P')]
    for i, q in enumerate(_qw_dummies(h)):
        gates += [(f'qd{i}', 'NANDXC', f'QW{q}', 'M1', f'QD{i}')]
    return gates


REV8 = os.environ.get('OMUX_REV', '7') == '8'   # rev 8 (merged window / tree, TG closing select): 427-um cell, slower (s10/tree); not used


def omux8h_r8(h):
    """rev 8 (session 10): window gate merged into the first tree stage.  Per slot k and tree m:
        Z_mk = NAND3(A_mk (top, static during the window), C_k (middle, closing), QW_k (bottom, opening))
        C_k = AOI22(QW k+1, M1, QW k+2, M2) (even k), AOI21(QW k+1, M1, M2) (odd k; M2 = 1 disables it)
    then U = NAND(Z, Z), V = INV, W = NAND(V, V), H = INVH (half output, active-low OR4).  QW -> Y is 8 stages
    (rev 7: 10); rev 7d at ss: the 0.8-0.9-slot S pulse (hi 2.9-3.0 V) lost 0.25 slot in the tree (s10/c5,
    s10/tree), 21 errors.  Assert / de-assert paths each have 4 PMOS-rise and 4 NMOS-fall stages to Y.
    S k (wtx_ppost8 G latch, S0P only) = INV2(NAND2(QW k, C k)) on every k for equal QW / C load."""
    ks = list(range(4 * h, 4 * h + 4))
    ports = [f'QW{q}' for q in range(8)] + [f'F{k}' for k in ks] + [f'dA{k}' for k in ks] + ['M2', 'HI', 'LO'] + \
        [f'S{k}' for k in ks] + ['YH', 'DH'] + (['S0P'] if h == 0 else [])
    # TG gate copies: N-gate nets (GN*, HI) on the highest tracks, P-gate nets (GP*, LO) on the lowest (the row
    # generator puts a gate's poly contact beside a diffusion contact whose metal must not cross its track)
    gates = [('m1', 'INV2', 'M2', 'M1'), ('gn1', 'INV1', 'M2', 'GN1'), ('gn2', 'INV1', 'M1', 'GN2'),
             ('gp1', 'INV1', 'M2', 'GP1'), ('gp2', 'INV1', 'M1', 'GP2')]
    for k in ks:
        # closing source CQ k: static transmission-gate select (the AOI22 / AOI21 of the first rev 8 draft hit
        # the row generator's poly-contact limit); odd k through an always-on TG so every path has one TG
        if k % 2 == 0:
            gates += [(f't{k}a', 'TGC', f'QW{(k + 1) % 8}', 'GN1', 'GP2', f'CQ{k}'),
                      (f't{k}b', 'TGC', f'QW{(k + 2) % 8}', 'GN2', 'GP1', f'CQ{k}'),
                      (f'c{k}', 'NANDC8', f'CQ{k}', 'HI', f'C{k}')]
        else:
            gates += [(f't{k}a', 'TGC', f'QW{(k + 1) % 8}', 'HI', 'LO', f'CQ{k}'),
                      (f'c{k}', 'NANDC8', f'CQ{k}', 'M1', f'C{k}')]
    for k in ks:
        gates += [(f's{k}n', 'NANDS', f'QW{k}', f'C{k}', f'SN{k}'), (f's{k}i', 'INV2', f'SN{k}', f'S{k}P' if k == 0 else f'S{k}')]
    for i, q in enumerate(_qw_dummies(h)):   # dummy = an always-on TG into a NAND input, as the real closing load
        gates += [(f'qd{i}', 'TGC', f'QW{q}', 'HI', 'LO', f'QE{i}'), (f'qe{i}', 'NANDC8', f'QE{i}', 'M1', f'QD{i}')]
    for m, a, y in (('y', 'F', 'YH'), ('d', 'dA', 'DH')):
        gates += [(f'{m}z{k}', 'Z3', f'{a}{k}', f'C{k}', f'QW{k}', f'{m}Z{k}') for k in ks]
        gates += [(f'{m}u{j}', 'U8', f'{m}Z{ks[2 * j]}', f'{m}Z{ks[2 * j + 1]}', f'{m}U{j}') for j in range(2)]
        gates += [(f'{m}v{j}', 'V8', f'{m}U{j}', f'{m}V{j}') for j in range(2)]
        gates += [(f'{m}w', 'O8', f'{m}V0', f'{m}V1', f'{m}W'), (f'{m}h', 'INVH', f'{m}W', y)]
    if h == 0:   # S0 port kept for the top netlist (unused): tie through a dummy-free buffer of S0P
        gates += [('s0x', 'INV1', 'SN0', 'S0')]
    r, p_, n_ = M.row_of(f'wtx_omux8{"ab"[h]}', gates, ports)
    order = []
    for c in r.cols:
        for key in (('n', 'p') if c['k'] == 'c' else ('net', 'netn', 'netp')):
            v = c.get(key)
            if isinstance(v, str) and v not in ('-', 'VDD', 'VSS') and v not in order:
                order.append(v)
    low, high = ['GP1', 'GP2', 'LO'], ['GN1', 'GN2', 'HI']
    r.track_order = low + [n for n in order if n not in low + high] + high
    return r, p_, n_


def omux8h(h):
    """rev 7 (session 10): one half of the 8:1 window mux, placed next to its own windows (slots 4h..4h+3).
    Per tree: Z = NAND(S, A); U = NAND(Z, Z) (OR2); V = INV; W = NAND(V, V) (OR4); H = INVH(W) (active-low OR4,
    drives the route to the final 2:1).  rev 6 ran one 8:1 tree (Z U V W, NOR with series PMOS, 3 INV) along a
    347-um row: yW0 / yW1 paths differed -> data-dependent delay, 24/160 errors at tt 3.24 (s9/c5)."""
    ks = list(range(4 * h, 4 * h + 4))
    ports = [f'QW{q}' for q in range(8)] + [f'F{k}' for k in ks] + [f'dA{k}' for k in ks] + ['M2'] + \
        [f'S{k}' for k in ks] + ['YH', 'DH'] + (['S0P'] if h == 0 else [])
    gates = _windows(ks, h)
    for m, a, y in (('y', 'F', 'YH'), ('d', 'dA', 'DH')):
        gates += [(f'{m}z{k}', 'Z8', f'S{k}', f'{a}{k}', f'{m}Z{k}') for k in ks]
        gates += [(f'{m}u{j}', 'U8', f'{m}Z{ks[2 * j]}', f'{m}Z{ks[2 * j + 1]}', f'{m}U{j}') for j in range(2)]
        gates += [(f'{m}v{j}', 'V8', f'{m}U{j}', f'{m}V{j}') for j in range(2)]
        gates += [(f'{m}w', 'O8', f'{m}V0', f'{m}V1', f'{m}W'), (f'{m}h', 'INVH', f'{m}W', y)]
    return M.row_of(f'wtx_omux8{"ab"[h]}', gates, ports)


def ofin8():
    """Matched final 2:1 per tree: O = NAND(H0, H1) (= OR8, both inputs equal, no series-PMOS NOR), then
    Y = INVP(INV4(O)), YB = INVP(INV4(INV4(O))) (true / complement as rev 6: one INV4 apart)."""
    ports = ['YH0', 'YH1', 'DH0', 'DH1', 'Y', 'YB', 'DP', 'DPB']
    gates = []
    for m, y in (('y', 'Y'), ('d', 'DP')):
        gates += [(f'{m}o', 'F8', f'{m.upper()}H0', f'{m.upper()}H1', f'{m}O'),
                  (f'{m}c', 'INV4', f'{m}O', f'{m}OC'), (f'{m}p', 'INVP', f'{m}OC', y),
                  (f'{m}e', 'INV4', f'{m}OC', f'{m}OE'), (f'{m}r', 'INVP', f'{m}OE', y + 'B')]
    return M.row_of('wtx_ofin8', gates, ports)


# rev 7d tree sizes (s10/tree, extracted omux8a alone, tt: the rev 6 sizes NANDZ 4/3 ... took 90-145 ps per stage,
# 1.3-1.5 slots S -> YH, assert 0.26 slot slower than de-assert).  Each stage sized for equal measured rise / fall
# delay (rev 7d at 8/9, 12/14: NAND rise 1.15-1.4x the fall) -> NAND wp ~ 1.4-1.6 wn, INV wp ~ 2.3 wn.
C8N = tuple(map(float, os.environ.get('C8N', '16,16').split(',')))   # closing AOI (rev 8)
M.SIZE.update(NANDC8=('nand2', *C8N), TGC=('tg', *map(float, os.environ.get('TG8', '6,12').split(','))), Z3=('nand3f', 12, 12), C8E=('aoi22f', *C8N), C8O=('aoi21f', *C8N), NANDS=('nand2', 3, 3), NANDQD=('nand2', *C8N))
M.SIZE.update(Z8=('nand2', 8, 11), U8=('nand2', 12, 19), V8=('inv', 12, 28), O8=('nand2', 12, 20), F8=('nand2', 12, 18))
M.SIZE.update(INVH=('inv', 16, 36), NANDF=('nand2', 12, 10), NANDXC=('nand2', *map(float, WNX.split(','))))
M.CELLS.update(wtx_omux8=omux8, wtx_ppost8=ppost8, wtx_omux8a=lambda: (omux8h_r8 if REV8 else omux8h)(0),
               wtx_omux8b=lambda: (omux8h_r8 if REV8 else omux8h)(1),
               wtx_ofin8=ofin8)
CELLS = ['wtx_qph', 'wtx_sreg5', 'wtx_q4ctlc', 'wtx_q4ck', 'wtx_tspcb', 'wtx_tspcbx', 'wtx_div5r', 'wtx_ppost8',
         'wtx_omux8a', 'wtx_omux8b', 'wtx_ofin8']


def top_instances():
    V = ['VDD', 'VSS']
    out = [('XCTL', 'wtx_q4ctlc', ['SERQ', 'QRST', 'DC', 'WCKQ'] + V),
           ('XCK', 'wtx_q4ck', ['QKN0', 'QKN1', 'QDN', 'QK0', 'QK1', 'QD'] + V),
           ('XDV', 'wtx_div5r', ['QD', 'QRST', 'DC', 'LDA'] + V)]
    for k in range(8):   # register clocks from slice 0 (phase 0)
        xn = ['QKN0', 'QKN1', 'QDN'] if k == 0 else [f'CXN{k}_{d}' for d in range(3)]
        out.append((f'XP{k}', 'wtx_qph', [PH[k], 'SERQ', 'VDD', 'VSS', 'VSS', 'VSS', 'VSS', f'G{k}'] + xn
                    + [f'QW{k}', f'Q{k}'] + V))
    for k in range(8):
        out.append((f'XL{k}', 'wtx_sreg5', [f'D{k + 8 * j}' for j in range(5)]
                    + ['VSS', 'LDA', 'QK0' if k < 4 else 'QK1', 'QRST', f'B{k}_0'] + V))
    for k, seq in HOPS8.items():
        prev = f'B{k}_0'
        for i, q in enumerate(seq):
            o = f'F{k}' if i == len(seq) - 1 else f'R{k}_{i}'
            cell = 'wtx_tspcbx' if i == len(seq) - 1 else 'wtx_tspcb'
            out.append((f'XH{k}_{i}', cell, [f'Q{q}', prev, o, 'QRST'] + V))
            prev = o
    # streams arrive inverted (sreg5): F k = NOT(bit), so the true / complement outputs are swapped
    for h in (0, 1):
        ks = list(range(4 * h, 4 * h + 4))
        out.append((f'XO{"AB"[h]}', f'wtx_omux8{"ab"[h]}', [f'QW{q}' for q in range(8)] + [f'F{k}' for k in ks]
                    + [f'PA{k}' for k in ks] + (['M2', 'VDD', 'VSS'] if REV8 else ['M2']) + [f'S{k}' for k in ks] + [f'YH{h}', f'DH{h}']
                    + (['S0P'] if h == 0 else []) + V))
    # streams arrive inverted (sreg5): F k = NOT(bit), so the true / complement outputs are swapped
    out.append(('XOF', 'wtx_ofin8', ['YH0', 'YH1', 'DH0', 'DH1', 'YB', 'Y', 'DPB', 'DP'] + V))
    out.append(('XPP', 'wtx_ppost8', [f'F{k}' for k in range(8)] + ['S0P', 'M2', 'R4', 'R8']
                + [f'PA{k}' for k in range(8)] + V))
    return out


# rev 7 (session 10): 5 rows; mux halves next to their slices / streams, OA (R1) and OB (R3) at the same x,
# the final 2:1 (OF) between them in R2 so the YH0 / YH1 routes match.
# rev 7d: mux halves at the right end of the two phase-slice rows (same x), the final 2:1 (OF) in the row
# between them so the YH routes match; every QW reaches both halves (dummy loads, _qw_dummies).
# rev 7f: mux halves in the MIDDLE of the slice rows (rev 7e at the right end: QW0 route 166 fF vs QW4 95 fF,
# QW0 0.07-0.1 slot late at ss, s10/c6); OF in the middle of R2.
ROWS = [['L0', 'H0_0', 'L1', 'H1_0', 'L2', 'H2_0', 'CK', 'CTL'],
        ['P0', 'P1', 'OA', 'P2', 'P3'],
        ['L3', 'H3_0', 'H7_0', 'H7_1', 'OF', 'L4', 'H4_0', 'DV'],
        ['P4', 'P5', 'OB', 'P6', 'P7'],
        ['L5', 'H5_0', 'H5_1', 'L6', 'H6_0', 'H6_1', 'L7', 'PP']]


def top_spice():
    body = [f'.subckt {NAME} {" ".join(TOP_PORTS)}']
    body += [f'{i} {" ".join(c)} {cell}' for i, cell, c in top_instances()]
    return '\n'.join(body + [f'.ends {NAME}']) + '\n'


def macro_text():
    return ''.join((M.FAST / f'{n}.spice').read_text() for n in CELLS)


def build_top():
    return M.build_le(NAME, TOP_PORTS, top_spice(), macro_text(), ROWS, CELLS, max_row_width=640.0,
                      workname='top8')


if __name__ == '__main__':
    what = sys.argv[1] if len(sys.argv) > 1 else 'top'
    if what == 'cells':
        for n in sys.argv[2:] or ['wtx_ppost8', 'wtx_omux8']:
            M.build_cell(n)
    elif what == 'top':
        build_top()
