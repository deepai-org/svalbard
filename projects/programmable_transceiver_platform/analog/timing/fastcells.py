"""Compact fast cells (P3): column descriptions for compact.Row plus the
intended transistor netlist of each cell (written independently, so LVS checks
the row compiler), and schematic-vs-extracted speed benches.

Cells
  ct_ring8   4-stage pseudo-differential ring, 8 phases at 45 deg, per-phase
             buffers O0..O7 (Ok has phase k*45 deg), output clamps (ENB)
             NMOS sources on VT (tail), PMOS sources on VH (header)
  ct_tspc2   TSPC divide-by-2 with QB reset (ENB) and output NOR(QB, ENB)
  ct_lodrv   lo_ext internal-mode driver: NAND(LOI,INT) -> inv -> 2x inv ->
             8-finger tristate (INT/INTB) onto the mixer LO node
  ct_rxin    self-biased receiver/limiter input stage with enable
             header/footer, clamp, then inv2 and inv4 (feedback resistor and
             its switch stay outside the cell: ports IN, A1)
Usage: python3 fastcells.py [cell ...]
"""
import json
import math
import shutil
import sys
from pathlib import Path

import compact
import timing_flow as tf


def C(n, p=None, same=True):
    return dict(k='c', n=n, p=(n if (same and p is None) else p))


def CN(n):
    return dict(k='c', n=n, p='-')


def G(net, wn=None, wp=None, n=True, p=True, netn=None, netp=None):
    d = dict(k='g', net=net, n=n, p=p)
    if wn is not None:
        d['wn'] = wn
    if wp is not None:
        d['wp'] = wp
    if netn:
        d['netn'] = netn
    if netp:
        d['netp'] = netp
    return d


BRK = dict(k='c', n='-', p='-')


def fet(name, d, g, s, b, w, kind='n'):
    return f'X{name} {d} {g} {s} {b} {"nfet_03v3" if kind == "n" else "pfet_03v3"} w={w:g}u l=0.28u'


# --------------------------------------------------------------- ct_ring8
def ring8():
    ph = ['P0', 'P1', 'P2', 'P3', 'N0', 'N1', 'N2', 'N3']
    stages = [('P0', 'N0', 'P1', 'N1'), ('P1', 'N1', 'P2', 'N2'), ('P2', 'N2', 'P3', 'N3'), ('P3', 'N3', 'N0', 'P0')]
    S = dict(k='c', n='VT', p='VH')
    cols, net = [], []
    KN, KP = 1, 2               # keeper strength: phase accuracy under tail starving vs speed
    WN, WP = 4, 8               # ring inverters (larger than the fixed restore/wire load)
    for k, (ip, inn, op, on) in enumerate(stages):
        if k:
            cols.append(BRK)
        cols += [C(on), G(ip, WN, WP), S, G(inn, WN, WP), C(op), G(on, KN, KP), S, G(op, KN, KP), C(on)]
        net += [fet(f'M{k}a', on, ip, 'VT', 'VSS', WN), fet(f'M{k}b', on, ip, 'VH', 'VDD', WP, 'p'),
                fet(f'M{k}c', op, inn, 'VT', 'VSS', WN), fet(f'M{k}d', op, inn, 'VH', 'VDD', WP, 'p'),
                fet(f'K{k}a', op, on, 'VT', 'VSS', KN), fet(f'K{k}b', op, on, 'VH', 'VDD', KP, 'p'),
                fet(f'K{k}c', on, op, 'VT', 'VSS', KN), fet(f'K{k}d', on, op, 'VH', 'VDD', KP, 'p')]
    # outputs: a low-threshold restore inverter (NMOS 4u / PMOS 2u, ~1.25 V,
    # on VDD/VSS) right at each ring node, then inv 2/4 (VDD/VSS) driving the
    # port wire.  The mirrored-header ring swings ~0.25 V..VH with VH down to
    # ~1.9 V at the bottom of the range, so a mid-rail threshold would miss
    # it.  Ok = !!ring node -> phase k*45 deg.  Off-state clamps (0.5u NMOS
    # on ENB) keep the unpowered ring nodes low (outputs then rest low).
    V = C('VSS', 'VDD', same=False)
    for k in range(8):
        cols += [BRK, V, G(ph[k], 4, 2), C(f'A{k}'), BRK, V, G(f'A{k}', 2, 4), C(f'O{k}')]
        net += [fet(f'R{k}n', f'A{k}', ph[k], 'VSS', 'VSS', 4), fet(f'R{k}p', f'A{k}', ph[k], 'VDD', 'VDD', 2, 'p'),
                fet(f'S{k}n', f'O{k}', f'A{k}', 'VSS', 'VSS', 2), fet(f'S{k}p', f'O{k}', f'A{k}', 'VDD', 'VDD', 4, 'p')]
    for k in range(0, 8, 2):
        a, b = ph[k], ph[k + 1]
        cols += [BRK, CN(a), G('ENB', 0.5, p=False), CN('VSS'), G('ENB', 0.5, p=False), CN(b)]
        net += [fet(f'C{k}a', a, 'ENB', 'VSS', 'VSS', 0.5), fet(f'C{k}b', b, 'ENB', 'VSS', 'VSS', 0.5)]
    ports = [f'O{k}' for k in range(8)] + ['ENB']
    row = compact.Row('ct_ring8', cols, rail_n='VT', tap_n='VSS', rail_p='VH', tap_p='VDD', ports=ports, wn=1, wp=2)
    row.track_order = ph + [f'A{k}' for k in range(8)] + [f'O{k}' for k in range(8)] + ['ENB']
    allports = ports + ['VT', 'VH', 'VDD', 'VSS']
    return row, allports, net


# --------------------------------------------------------------- ct_ring9
def ring9(WN=8, WP=16, KN=1, KP=2, name='ct_ring9'):
    """ct_ring8 topology for pll_ring r9 (CDR/pll_ring owner, 2026-11-10).  ct_ring8's extracted ring nodes carry
    25-30 fF of wiring (all restore inverters after the four stages: long Metal2 tracks), so the extracted ring ran
    at 763 MHz vs 1307 MHz schematic (ss/32 C/2.835 V, VCTRL = VDD).  r9: each stage is followed by the restore/port
    inverters and clamps of the two phases it drives (short tracks), ring devices 8/16 (2x), keepers kept at 1/2
    (stronger keepers cost speed, no phase-error benefit).  Extracted-cell speed: 945 MHz at ss/2.835 V, 892 MHz at
    ss/2.71 V (the pt_pll_vreg output at VIN 3.15 V, ss/32 C)."""
    ph = ['P0', 'P1', 'P2', 'P3', 'N0', 'N1', 'N2', 'N3']
    stages = [('P0', 'N0', 'P1', 'N1'), ('P1', 'N1', 'P2', 'N2'), ('P2', 'N2', 'P3', 'N3'), ('P3', 'N3', 'N0', 'P0')]
    S = dict(k='c', n='VT', p='VH')
    V = C('VSS', 'VDD', same=False)
    cols, net = [], []
    def restore(k):
        nonlocal cols, net
        cols += [BRK, V, G(ph[k], 4, 2), C(f'A{k}'), BRK, V, G(f'A{k}', 2, 4), C(f'O{k}')]
        net += [fet(f'R{k}n', f'A{k}', ph[k], 'VSS', 'VSS', 4), fet(f'R{k}p', f'A{k}', ph[k], 'VDD', 'VDD', 2, 'p'),
                fet(f'S{k}n', f'O{k}', f'A{k}', 'VSS', 'VSS', 2), fet(f'S{k}p', f'O{k}', f'A{k}', 'VDD', 'VDD', 4, 'p')]
    for k, (ip, inn, op, on) in enumerate(stages):
        if k:
            cols.append(BRK)
        cols += [C(on), G(ip, WN, WP), S, G(inn, WN, WP), C(op), G(on, KN, KP), S, G(op, KN, KP), C(on)]
        net += [fet(f'M{k}a', on, ip, 'VT', 'VSS', WN), fet(f'M{k}b', on, ip, 'VH', 'VDD', WP, 'p'),
                fet(f'M{k}c', op, inn, 'VT', 'VSS', WN), fet(f'M{k}d', op, inn, 'VH', 'VDD', WP, 'p'),
                fet(f'K{k}a', op, on, 'VT', 'VSS', KN), fet(f'K{k}b', op, on, 'VH', 'VDD', KP, 'p'),
                fet(f'K{k}c', on, op, 'VT', 'VSS', KN), fet(f'K{k}d', on, op, 'VH', 'VDD', KP, 'p')]
        # restore inverters of the two driven phases, right next to the stage; clamps for them too
        for n_ in (op, on):
            restore(ph.index(n_))
        cols += [BRK, CN(op), G('ENB', 0.5, p=False), CN('VSS'), G('ENB', 0.5, p=False), CN(on)]
        net += [fet(f'C{k}a', op, 'ENB', 'VSS', 'VSS', 0.5), fet(f'C{k}b', on, 'ENB', 'VSS', 'VSS', 0.5)]
    ports = [f'O{k}' for k in range(8)] + ['ENB']
    row = compact.Row(name, cols, rail_n='VT', tap_n='VSS', rail_p='VH', tap_p='VDD', ports=ports, wn=1, wp=2)
    row.track_order = ph + [f'A{k}' for k in range(8)] + [f'O{k}' for k in range(8)] + ['ENB']
    return row, ports + ['VT', 'VH', 'VDD', 'VSS'], net


# --------------------------------------------------------------- ct_tspc2
def tspc2():
    cols = [C('VSS', 'VDD'), G('QB', 2, 4), C('X', None, same=False), G('CK', p=True, n=False, wp=4), dict(k='c', n='-', p='X'),
            dict(k='c', n='Y', p='-'), G('X', 2, n=True, p=False), dict(k='c', n=None, p='VDD'), G('CK', 2, 4), C('VSS', 'Y', same=False),
            BRK,
            dict(k='c', n='QB', p='-'), G('CK', 2, n=True, p=False), dict(k='c', n=None, p='VDD'), G('Y', 2, 4), C('VSS', 'QB', same=False),
            G('ENB', 1, n=True, p=False), dict(k='c', n='QB', p='-'),
            BRK, C('VSS', 'VDD', same=False), G('QB', 2, 4), dict(k='c', n='Q', p=None), G('ENB', 2, 4), C('VSS', 'Q', same=False)]
    net = [fet('N1', 'X', 'QB', 'VSS', 'VSS', 2), fet('P1', 'm1', 'QB', 'VDD', 'VDD', 4, 'p'), fet('P2', 'X', 'CK', 'm1', 'VDD', 4, 'p'),
           fet('N2', 'Y', 'X', 'm2', 'VSS', 2), fet('N3', 'm2', 'CK', 'VSS', 'VSS', 2), fet('P3', 'Y', 'CK', 'VDD', 'VDD', 4, 'p'),
           fet('N4', 'QB', 'CK', 'm3', 'VSS', 2), fet('N5', 'm3', 'Y', 'VSS', 'VSS', 2), fet('P4', 'QB', 'Y', 'VDD', 'VDD', 4, 'p'),
           fet('NR', 'QB', 'ENB', 'VSS', 'VSS', 1),
           # Q = NOR(QB, ENB): low in reset, so the next stage's clock rests low
           fet('NO1', 'Q', 'QB', 'VSS', 'VSS', 2), fet('NO2', 'Q', 'ENB', 'VSS', 'VSS', 2),
           fet('PO1', 'mo', 'QB', 'VDD', 'VDD', 4, 'p'), fet('PO2', 'Q', 'ENB', 'mo', 'VDD', 4, 'p')]
    ports = ['CK', 'Q', 'ENB']
    row = compact.Row('ct_tspc2', cols, ports=ports, wn=2, wp=4)
    return row, ports + ['VDD', 'VSS'], net


# --------------------------------------------------------------- ct_lodrv
def lodrv(fingers=4):
    """Split-gate tristate LO driver with skewed last pre-drivers for
    break-before-make: PG = buf(NAND(LOI, INT)) rises fast / falls slow (P
    turns off before N turns on), NG = buf(NOR(LOI, INTB)) falls fast / rises
    slow.  INT=0: PG=1, NG=0 (output high-Z)."""
    S = C('VSS', 'VDD', same=False)
    cols = [S, G('LOI', 2, 3), dict(k='c', n=None, p='A'), G('INT', 2, 3), C('A', 'VDD', same=False),
            BRK, S, G('LOI', 1, 4), C('B', None, same=False), G('INTB', 1, 4), C('VSS', 'B', same=False),
            BRK, S, G('A', 2, 4), C('A2'), BRK, S, G('B', 2, 4), C('B2'),
            BRK, S, G('A2', 4, 8), C('PG'), BRK, S, G('B2', 4, 4), C('NG'), BRK, S]
    net = [fet('A1', 'm', 'LOI', 'VSS', 'VSS', 2), fet('A2', 'A', 'INT', 'm', 'VSS', 2),
           fet('A3', 'A', 'LOI', 'VDD', 'VDD', 3, 'p'), fet('A4', 'A', 'INT', 'VDD', 'VDD', 3, 'p'),
           fet('O1', 'B', 'LOI', 'VSS', 'VSS', 1), fet('O2', 'B', 'INTB', 'VSS', 'VSS', 1),
           fet('O3', 'mp', 'LOI', 'VDD', 'VDD', 4, 'p'), fet('O4', 'B', 'INTB', 'mp', 'VDD', 4, 'p'),
           fet('D1', 'A2', 'A', 'VSS', 'VSS', 2), fet('D2', 'A2', 'A', 'VDD', 'VDD', 4, 'p'),
           fet('E1', 'B2', 'B', 'VSS', 'VSS', 2), fet('E2', 'B2', 'B', 'VDD', 'VDD', 4, 'p'),
           fet('F1', 'PG', 'A2', 'VSS', 'VSS', 4), fet('F2', 'PG', 'A2', 'VDD', 'VDD', 8, 'p'),
           fet('H1', 'NG', 'B2', 'VSS', 'VSS', 4), fet('H2', 'NG', 'B2', 'VDD', 'VDD', 4, 'p')]
    for f in range(fingers // 2):
        cols += [G(None, 4, 8, netn='NG', netp='PG'), C('LO'), G(None, 4, 8, netn='NG', netp='PG'), S]
        for h in range(2):
            net += [fet(f'T{f}{h}n', 'LO', 'NG', 'VSS', 'VSS', 4), fet(f'T{f}{h}p', 'LO', 'PG', 'VDD', 'VDD', 8, 'p')]
    ports = ['LOI', 'INT', 'INTB', 'LO']
    row = compact.Row('ct_lodrv', cols, ports=ports, wn=2, wp=4)
    row.track_order = ['LOI', 'A', 'B', 'A2', 'B2', 'INT', 'NG', 'LO', 'PG', 'INTB']
    return row, ports + ['VDD', 'VSS'], net


# --------------------------------------------------------------- ct_rxin
def rxin():
    cols = [C('VSS', 'VDD', same=False), G(None, 12, 16, netn='EN', netp='ENB'), C(None, None, same=False), G('IN', 6, 12), C('A1'),
            G('ENB', 1, n=True, p=False), dict(k='c', n='VSS', p='-'),
            BRK, C('VSS', 'VDD', same=False), G('A1', 2, 4), C('A2'),
            BRK, C('VSS', 'VDD', same=False), G('A2', 2, 4), C('OUT'), G('A2', 2, 4), C('VSS', 'VDD', same=False)]
    net = [fet('F', 'f', 'EN', 'VSS', 'VSS', 12), fet('N1', 'A1', 'IN', 'f', 'VSS', 6),
           fet('H', 'h', 'ENB', 'VDD', 'VDD', 16, 'p'), fet('P1', 'A1', 'IN', 'h', 'VDD', 12, 'p'),
           fet('CL', 'A1', 'ENB', 'VSS', 'VSS', 1),
           fet('N2', 'A2', 'A1', 'VSS', 'VSS', 2), fet('P2', 'A2', 'A1', 'VDD', 'VDD', 4, 'p'),
           fet('N3a', 'OUT', 'A2', 'VSS', 'VSS', 2), fet('P3a', 'OUT', 'A2', 'VDD', 'VDD', 4, 'p'),
           fet('N3b', 'OUT', 'A2', 'VSS', 'VSS', 2), fet('P3b', 'OUT', 'A2', 'VDD', 'VDD', 4, 'p')]
    ports = ['IN', 'A1', 'OUT', 'EN', 'ENB']
    row = compact.Row('ct_rxin', cols, ports=ports, wn=2, wp=4)
    row.track_order = ['IN', 'EN', 'A1', 'A2', 'OUT', 'ENB']
    return row, ports + ['VDD', 'VSS'], net


def lim():
    """Polyphase limiter: small self-biased first stage (low Miller load on the
    RC network), then inv 2/4 and a 2-finger inv 2/4."""
    cols = [C('VSS', 'VDD', same=False), G(None, 4, 8, netn='EN', netp='ENB'), C(None, None, same=False), G('IN', 2, 4), C('A1'),
            G('ENB', 1, n=True, p=False), dict(k='c', n='VSS', p='-'),
            BRK, C('VSS', 'VDD', same=False), G('A1', 2, 4), C('A2'),
            BRK, C('VSS', 'VDD', same=False), G('A2', 2, 4), C('OUT'), G('A2', 2, 4), C('VSS', 'VDD', same=False)]
    net = [fet('F', 'f', 'EN', 'VSS', 'VSS', 4), fet('N1', 'A1', 'IN', 'f', 'VSS', 2),
           fet('H', 'h', 'ENB', 'VDD', 'VDD', 8, 'p'), fet('P1', 'A1', 'IN', 'h', 'VDD', 4, 'p'),
           fet('CL', 'A1', 'ENB', 'VSS', 'VSS', 1),
           fet('N2', 'A2', 'A1', 'VSS', 'VSS', 2), fet('P2', 'A2', 'A1', 'VDD', 'VDD', 4, 'p'),
           fet('N3a', 'OUT', 'A2', 'VSS', 'VSS', 2), fet('P3a', 'OUT', 'A2', 'VDD', 'VDD', 4, 'p'),
           fet('N3b', 'OUT', 'A2', 'VSS', 'VSS', 2), fet('P3b', 'OUT', 'A2', 'VDD', 'VDD', 4, 'p')]
    ports = ['IN', 'A1', 'OUT', 'EN', 'ENB']
    row = compact.Row('ct_lim', cols, ports=ports, wn=2, wp=4)
    row.track_order = ['IN', 'EN', 'A1', 'A2', 'OUT', 'ENB']
    return row, ports + ['VDD', 'VSS'], net


def rxout():
    """diff_clk_rx output stage: OUTP = INP & EN (via A3P = !INP),
    OUTN = INN | !EN (diff, A3N = !INN) or !INP | !EN (SE=1, via A2P = !A3P).
    Three gate levels per leg: NOR2/inv/inv (P) and AOI22/NOR2/inv (N).
    r5 (diff_clk_rx TIM-08): N path upsized (AOI22 4/8, NOR2 P 12, A2P inverter 2/4) so OUTN keeps
    pace with OUTP at 2 Gb/s; only diff_clk_rx uses this cell."""
    S = C('VSS', 'VDD', same=False)
    cols = [S, G('A3P', 2, 4), C('A2P'),                                   # A2P = !A3P
            BRK, C('Y', 'm', same=False), G('A3N', 4, 8), C(None, 'VDD', same=False), G('SEB', 4, 8),
            C('VSS', 'm', same=False), G('SE', 4, 8), C(None, 'Y', same=False), G('A2P', 4, 8), C('Y', 'm', same=False),
            BRK, S, G('A3P', 2, 8), C('GP', None, same=False), G('ENB', 2, 8), C('VSS', 'GP', same=False),   # GP = NOR(A3P, ENB)
            BRK, S, G('Y', 2, 12), C('GN', None, same=False), G('ENB', 2, 12), C('VSS', 'GN', same=False),     # GN = NOR(Y, ENB)
            BRK, S, G('GP', 2, 4), C('BP'),
            BRK, S, G('BP', 4, 8), C('OUTP'), G('BP', 4, 8), S,
            BRK, S, G('GN', 4, 8), C('OUTN'), G('GN', 4, 8), S]
    net = [fet('i1', 'A2P', 'A3P', 'VSS', 'VSS', 2), fet('i2', 'A2P', 'A3P', 'VDD', 'VDD', 4, 'p'),
           fet('a1', 'Y', 'A3N', 'n1', 'VSS', 4), fet('a2', 'n1', 'SEB', 'VSS', 'VSS', 4),
           fet('a3', 'Y', 'A2P', 'n2', 'VSS', 4), fet('a4', 'n2', 'SE', 'VSS', 'VSS', 4),
           fet('a5', 'm', 'A3N', 'VDD', 'VDD', 8, 'p'), fet('a6', 'm', 'SEB', 'VDD', 'VDD', 8, 'p'),
           fet('a7', 'Y', 'SE', 'm', 'VDD', 8, 'p'), fet('a8', 'Y', 'A2P', 'm', 'VDD', 8, 'p'),
           fet('n1', 'GP', 'A3P', 'VSS', 'VSS', 2), fet('n2', 'GP', 'ENB', 'VSS', 'VSS', 2),
           fet('n3', 'q1', 'A3P', 'VDD', 'VDD', 8, 'p'), fet('n4', 'GP', 'ENB', 'q1', 'VDD', 8, 'p'),
           fet('m1', 'GN', 'Y', 'VSS', 'VSS', 2), fet('m2', 'GN', 'ENB', 'VSS', 'VSS', 2),
           fet('m3', 'q2', 'Y', 'VDD', 'VDD', 12, 'p'), fet('m4', 'GN', 'ENB', 'q2', 'VDD', 12, 'p'),
           fet('b1', 'BP', 'GP', 'VSS', 'VSS', 2), fet('b2', 'BP', 'GP', 'VDD', 'VDD', 4, 'p'),
           fet('o1', 'OUTP', 'BP', 'VSS', 'VSS', 4), fet('o2', 'OUTP', 'BP', 'VDD', 'VDD', 8, 'p'),
           fet('o3', 'OUTP', 'BP', 'VSS', 'VSS', 4), fet('o4', 'OUTP', 'BP', 'VDD', 'VDD', 8, 'p'),
           fet('o5', 'OUTN', 'GN', 'VSS', 'VSS', 4), fet('o6', 'OUTN', 'GN', 'VDD', 'VDD', 8, 'p'),
           fet('o7', 'OUTN', 'GN', 'VSS', 'VSS', 4), fet('o8', 'OUTN', 'GN', 'VDD', 'VDD', 8, 'p')]
    ports = ['A3P', 'A3N', 'SE', 'SEB', 'ENB', 'OUTP', 'OUTN']
    row = compact.Row('ct_rxout', cols, ports=ports, wn=2, wp=4)
    row.track_order = ['A3P', 'A3N', 'SEB', 'SE', 'ENB', 'A2P', 'Y', 'GP', 'GN', 'BP', 'm', 'OUTP', 'OUTN']
    return row, ports + ['VDD', 'VSS'], net


def phbuf8():
    """Port drivers for the ring phases (revision 3).  ct_ring8 already
    restores its nodes to full swing (low-threshold inverter + inv 2/4), so
    each phase here is inv 2/4 -> 2-finger inv 3/6 -> PHk (PHk = Ik polarity
    after the even number of inversions overall).  The divider clock DK is
    taken from I0 through inv 1/2 -> inv 2/4; every other input carries an
    identical 1/2 dummy so the eight phases are equally loaded.  Off state
    (ring outputs low): ports low, DK low."""
    S = C('VSS', 'VDD', same=False)
    cols, net = [], []
    for k in range(8):
        tap = 'DKB' if k == 0 else f'U{k}'
        cols += [S, G(f'I{k}', 1, 2), C(tap), BRK,
                 S, G(f'I{k}', 2, 4), C(f'M{k}'), BRK,
                 S, G(f'M{k}', 3, 6), C(f'PH{k}'), G(f'M{k}', 3, 6), S, BRK]
        net += [fet(f'u{k}n', tap, f'I{k}', 'VSS', 'VSS', 1), fet(f'u{k}p', tap, f'I{k}', 'VDD', 'VDD', 2, 'p'),
                fet(f'm{k}n', f'M{k}', f'I{k}', 'VSS', 'VSS', 2), fet(f'm{k}p', f'M{k}', f'I{k}', 'VDD', 'VDD', 4, 'p'),
                fet(f'o{k}a', f'PH{k}', f'M{k}', 'VSS', 'VSS', 3), fet(f'o{k}b', f'PH{k}', f'M{k}', 'VDD', 'VDD', 6, 'p'),
                fet(f'o{k}c', f'PH{k}', f'M{k}', 'VSS', 'VSS', 3), fet(f'o{k}d', f'PH{k}', f'M{k}', 'VDD', 'VDD', 6, 'p')]
    cols += [S, G('DKB', 2, 4), C('DK')]
    net += [fet('dkn', 'DK', 'DKB', 'VSS', 'VSS', 2), fet('dkp', 'DK', 'DKB', 'VDD', 'VDD', 4, 'p')]
    ports = [f'I{k}' for k in range(8)] + [f'PH{k}' for k in range(8)] + ['DK']
    row = compact.Row('ct_phbuf8', cols, ports=ports, wn=2, wp=4)
    row.track_order = ([f'I{k}' for k in range(8)] + [f'M{k}' for k in range(8)]
                       + ['DKB'] + [f'PH{k}' for k in range(8)] + ['DK'])
    return row, ports + ['VDD', 'VSS'], net


def tspcd():
    """TSPC D flip-flop (rising CK) with reset: Q = NOR(QB, ENB)."""
    row, ports, net = tspc2()
    for c in row.cols:
        if c.get('net') == 'QB' and c['k'] == 'g' and c.get('n', True) and c.get('p', True) and c is row.cols[1]:
            c['net'] = 'D'
    net = [n.replace('XN1 X QB VSS', 'XN1 X D VSS').replace('XP1 m1 QB VDD', 'XP1 m1 D VDD') for n in net]
    row.name = 'ct_tspcd'
    row.ports = ['CK', 'D', 'Q', 'ENB']
    return row, row.ports + ['VDD', 'VSS'], net


def mux4():
    """One-hot 4:1 clock select, Y = OR_k(Ak & Sk): four NAND2 into a NAND4,
    then a two-inverter buffer.  All selects 0 (reset) = stopped, Y=0.  The
    input-side NMOS of each NAND2 is the select (bottom), so a stopped input
    only charges the top gate."""
    S = C('VSS', 'VDD', same=False)
    cols, net = [], []
    for k in range(4):
        z = f'Z{k}'
        cols += [S, G(f'S{k}', 2, 2), dict(k='c', n=None, p=z), G(f'A{k}', 2, 2), C(z, 'VDD', same=False), BRK]
        net += [fet(f'n{k}a', f'm{k}', f'S{k}', 'VSS', 'VSS', 2), fet(f'n{k}b', z, f'A{k}', f'm{k}', 'VSS', 2),
                fet(f'p{k}a', z, f'S{k}', 'VDD', 'VDD', 2, 'p'), fet(f'p{k}b', z, f'A{k}', 'VDD', 'VDD', 2, 'p')]
    cols += [S, G('Z0', 4, 3), dict(k='c', n=None, p='X'), G('Z1', 4, 3), dict(k='c', n=None, p='VDD'),
             G('Z2', 4, 3), dict(k='c', n=None, p='X'), G('Z3', 4, 3), C('X', 'VDD', same=False), BRK,
             S, G('X', 2, 4), C('XB'), BRK, S, G('XB', 3, 6), C('Y'), G('XB', 3, 6), S]
    net += [fet('q0', 'u0', 'Z0', 'VSS', 'VSS', 4), fet('q1', 'u1', 'Z1', 'u0', 'VSS', 4),
            fet('q2', 'u2', 'Z2', 'u1', 'VSS', 4), fet('q3', 'X', 'Z3', 'u2', 'VSS', 4)]
    net += [fet(f'r{k}', 'X', f'Z{k}', 'VDD', 'VDD', 3, 'p') for k in range(4)]
    net += [fet('b1', 'XB', 'X', 'VSS', 'VSS', 2), fet('b2', 'XB', 'X', 'VDD', 'VDD', 4, 'p'),
            fet('b3', 'Y', 'XB', 'VSS', 'VSS', 3), fet('b4', 'Y', 'XB', 'VDD', 'VDD', 6, 'p'),
            fet('b5', 'Y', 'XB', 'VSS', 'VSS', 3), fet('b6', 'Y', 'XB', 'VDD', 'VDD', 6, 'p')]
    ports = ['A0', 'A1', 'A2', 'A3', 'S0', 'S1', 'S2', 'S3', 'Y']
    row = compact.Row('ct_mux4', cols, ports=ports, wn=2, wp=4)
    return row, ports + ['VDD', 'VSS'], net


def _tspc_cols(ck, d, q, qb, x, y, pre):
    """Columns + netlist of one TSPC D flip-flop (rising ck, Q = NOR(QB, ENB))."""
    cols = [C('VSS', 'VDD'), G(d, 2, 4), C(x, None, same=False), G(ck, p=True, n=False, wp=4), dict(k='c', n='-', p=x),
            dict(k='c', n=y, p='-'), G(x, 2, n=True, p=False), dict(k='c', n=None, p='VDD'), G(ck, 2, 4), C('VSS', y, same=False),
            BRK,
            dict(k='c', n=qb, p='-'), G(ck, 2, n=True, p=False), dict(k='c', n=None, p='VDD'), G(y, 2, 4), C('VSS', qb, same=False),
            G('ENB', 1, n=True, p=False), dict(k='c', n=qb, p='-'),
            BRK, C('VSS', 'VDD', same=False), G(qb, 2, 4), dict(k='c', n=q, p=None), G('ENB', 2, 4), C('VSS', q, same=False)]
    net = [fet(pre + 'N1', x, d, 'VSS', 'VSS', 2), fet(pre + 'P1', pre + 'm1', d, 'VDD', 'VDD', 4, 'p'),
           fet(pre + 'P2', x, ck, pre + 'm1', 'VDD', 4, 'p'),
           fet(pre + 'N2', y, x, pre + 'm2', 'VSS', 2), fet(pre + 'N3', pre + 'm2', ck, 'VSS', 'VSS', 2),
           fet(pre + 'P3', y, ck, 'VDD', 'VDD', 4, 'p'),
           fet(pre + 'N4', qb, ck, pre + 'm3', 'VSS', 2), fet(pre + 'N5', pre + 'm3', y, 'VSS', 'VSS', 2),
           fet(pre + 'P4', qb, y, 'VDD', 'VDD', 4, 'p'), fet(pre + 'NR', qb, 'ENB', 'VSS', 'VSS', 1),
           fet(pre + 'NO1', q, qb, 'VSS', 'VSS', 2), fet(pre + 'NO2', q, 'ENB', 'VSS', 'VSS', 2),
           fet(pre + 'PO1', pre + 'mo', qb, 'VDD', 'VDD', 4, 'p'), fet(pre + 'PO2', q, 'ENB', pre + 'mo', 'VDD', 4, 'p')]
    return cols, net


def _tspc_nand_cols(ck, ins, q, qb, x, y, pre):
    """TSPC flip-flop whose first (clocked, CK-low transparent) stage is a
    NAND of `ins`: Q <= AND(ins).  Merging the gate into the flop removes two
    gate delays from a feedback/decode path.  Stage 1: PMOS CK switch from
    VDD to n1, input PMOS in parallel n1 -> X, input NMOS in series to VSS."""
    n = len(ins)
    wn = {1: 2, 2: 3, 3: 4}[n]
    n1 = pre + 'n1'
    cols = [dict(k='c', n='-', p='VDD'), G(ck, p=True, n=False, wp=4)]
    net = [fet(pre + 'P2', n1, ck, 'VDD', 'VDD', 4, 'p')]
    for k, g in enumerate(ins):
        cols += [dict(k='c', n=('VSS' if k == 0 else None), p=(n1 if k % 2 == 0 else x)), G(g, wn, 2)]
        d_ = x if k == n - 1 else f'{pre}s{k}'
        s_ = 'VSS' if k == 0 else f'{pre}s{k - 1}'
        net += [fet(f'{pre}N1{k}', d_, g, s_, 'VSS', wn), fet(f'{pre}P1{k}', x, g, n1, 'VDD', 2, 'p')]
    cols += [dict(k='c', n=x, p=(n1 if n % 2 == 0 else x)), BRK]
    tc, tn = _tspc_cols(ck, 'UNUSED', q, qb, x, y, pre)
    cols += tc[5:]
    net += [l for l in tn if not any(l.startswith(f'X{pre}{t} ') for t in ('N1', 'P1', 'P2'))]
    return cols, net


def div5core():
    """Self-starting /5 counter on TSPC flops (a <- NOR(b,c), b <- a, c <- b;
    states abc 000 -> 100 -> 110 -> 011 -> 001).  The NOR is merged into the
    first stage of flop A as NAND(QB_b, QB_c) on the flops' internal inverted
    nodes, so the a-loop is clock -> QB -> flop A with no gate in between
    (the ss 810 MHz limit of the gate-level version)."""
    cols, net = [], []
    c_, n_ = _tspc_nand_cols('CK', ['QBB', 'QBC'], 'A', 'QBA', 'XA', 'YA', 'fa')
    cols += c_ + [BRK]
    net += n_
    c_, n_ = _tspc_cols('CK', 'A', 'B', 'QBB', 'XB', 'YB', 'fb')
    cols += c_ + [BRK]
    net += n_
    c_, n_ = _tspc_cols('CK', 'B', 'C', 'QBC', 'XC', 'YC', 'fc')
    cols += c_
    net += n_
    ports = ['CK', 'ENB', 'A', 'B', 'C']
    row = compact.Row('ct_div5', cols, ports=ports, wn=2, wp=4)
    row.track_order = ['QBB', 'XA', 'QBC', 'fan1']
    return row, ports + ['VDD', 'VSS'], net


def tspcn3():
    """TSPC flip-flop Q <= AND(I0, I1, I2) (NAND merged into the first stage)."""
    cols, net = _tspc_nand_cols('CK', ['I0', 'I1', 'I2'], 'Q', 'QB', 'X', 'Y', 'f')
    ports = ['CK', 'I0', 'I1', 'I2', 'Q', 'ENB']
    row = compact.Row('ct_tspcn3', cols, ports=ports, wn=2, wp=4)
    row.track_order = ['I0', 'I1', 'I2', 'X', 'fn1']
    return row, ports + ['VDD', 'VSS'], net



# --------------------------------------------------------------- ct_locml
def locml(units=10, wn=6, wp=4):
    """Switching core of the lo_ext CML LO driver (pt_lo_cml in lo_ext.spice):
    interdigitated NMOS pair (GA -> DN, GB -> DP, sources on the tail node TS,
    `units` x 2 fingers of wn um per side) under the PMOS load-header switches
    (INTB, sources on VS, drains VHN / VHP, `units` x 2 fingers of wp um per
    side).  Loads, tail, bias and the CM loop stay in the block (lo_ext.spice).
    Gate resistance is not extracted (C-only): the benches add it explicitly
    at the GA/GB ports."""
    cols, net = [], []
    k = 0
    for u in range(units):
        for g, d, hp in (('GA', 'DN', 'VHN'), ('GB', 'DP', 'VHP')):
            cols += [C('TS', 'VS', same=False), G(None, wn, wp, netn=g, netp='INTB'), C(d, hp, same=False),
                     G(None, wn, wp, netn=g, netp='INTB')]
            for h in range(2):
                net += [fet(f'M{k}', d, g, 'TS', 'VSS', wn), fet(f'H{k}', hp, 'INTB', 'VS', 'VDD', wp, 'p')]
                k += 1
    cols.append(C('TS', 'VS', same=False))
    ports = ['GA', 'GB', 'DN', 'DP', 'VHN', 'VHP', 'INTB']
    row = compact.Row('ct_locml', cols, rail_n='TS', tap_n='VSS', rail_p='VS', tap_p='VDD', ports=ports, wn=wn, wp=wp)
    row.track_order = ['DN', 'GA', 'GB', 'DP', 'INTB', 'VHN', 'VHP']
    return row, ports + ['TS', 'VS', 'VDD', 'VSS'], net

# --------------------------------------------------------------- ct_rxamp
def rxamp(F=8):
    """diff_clk_rx r5 (PD29/TIM-08) amplifier core, MOS only: CML preamp (pair GP/GN -> O1N/O1P, 4 x 8 um per
    side, tail 10 x 8 um on VBN), cross-coupled hysteresis pair (4 x 6 um per side, tail 2 x 6.5 um), and two 5T
    comparator (pair 2 x 8 um, PMOS mirror 2 x 8 um, tail 6 x 8 um) with an EN pull-up and the output
    inverter YA -> A3P.  r5b: one comparator only; ct_rxout derives OUTN from A3P (its SE path), so OUTP and
    OUTN come from the same decision (a second, mirrored comparator gave OUTN its own offset and duty error).  Poly loads, bias reference and the enable gating stay in the block (pt_rx_amp)."""
    cols, net = [], []
    k = [0]

    def nf(d, g, s_, w):
        net.append(fet(f'M{k[0]}', d, g, s_, 'VSS', w)); k[0] += 1

    def pf(d, g, s_, w):
        net.append(fet(f'M{k[0]}', d, g, s_, 'VDD', w, 'p')); k[0] += 1
    # stage 1: input pair, two units of [S1 GP O1N GP S1 GN O1P GN]
    for u in range(2):
        cols += [CN('S1'), G('GP', F, p=False), CN('O1N'), G('GP', F, p=False), CN('S1'), G('GN', F, p=False), CN('O1P'),
                 G('GN', F, p=False)]
        nf('O1N', 'GP', 'S1', F); nf('O1N', 'GP', 'S1', F); nf('O1P', 'GN', 'S1', F); nf('O1P', 'GN', 'S1', F)
    cols.append(CN('S1'))
    for u in range(5):                           # tail, 10 fingers
        cols += [G('VBN', F, p=False), CN('VSS'), G('VBN', F, p=False), CN('S1')]
        nf('S1', 'VBN', 'VSS', F); nf('S1', 'VBN', 'VSS', F)
    cols.append(BRK)
    # hysteresis pair, two units of [SH O1P O1N O1P SH O1N O1P O1N]
    for u in range(2):
        cols += [CN('SH'), G('O1P', 6, p=False), CN('O1N'), G('O1P', 6, p=False), CN('SH'), G('O1N', 6, p=False), CN('O1P'),
                 G('O1N', 6, p=False)]
        nf('O1N', 'O1P', 'SH', 6); nf('O1N', 'O1P', 'SH', 6); nf('O1P', 'O1N', 'SH', 6); nf('O1P', 'O1N', 'SH', 6)
    cols += [CN('SH'), G('VBN', 6.5, p=False), CN('VSS'), G('VBN', 6.5, p=False), CN('SH')]
    nf('SH', 'VBN', 'VSS', 6.5); nf('SH', 'VBN', 'VSS', 6.5)
    # two 5T comparators: (Y, D, gate of the D-side input, gate of the Y-side input, tail node, inverter out)
    for y, d, gd, gy, st, out in (('YA', 'DA', 'O1P', 'O1N', 'S2', 'A3P'),):
        cols += [BRK, C(d, d), G(None, F, F, netn=gd, netp=d), C(st, 'VDD', same=False), G(None, F, F, netn=gy, netp=d),
                 C(y, y), G(None, F, F, netn=gy, netp=d), C(st, 'VDD', same=False), G(None, F, F, netn=gd, netp=d), C(d, d)]
        nf(d, gd, st, F); nf(y, gy, st, F); nf(y, gy, st, F); nf(d, gd, st, F)
        pf(d, d, 'VDD', F); pf(y, d, 'VDD', F); pf(y, d, 'VDD', F); pf(d, d, 'VDD', F)
        cols += [BRK, CN(st)]
        for u in range(3):                       # tail, 6 fingers
            cols += [G('VBN', F, p=False), CN('VSS'), G('VBN', F, p=False), CN(st)]
            nf(st, 'VBN', 'VSS', F); nf(st, 'VBN', 'VSS', F)
        # EN pull-up on Y, then the inverter Y -> out (N 2 x 1 um, P 2 x 6 um)
        cols += [BRK, dict(k='c', n='-', p=y), G('EN', wp=1, n=False), dict(k='c', n='-', p='VDD'),
                 BRK, C('VSS', 'VDD', same=False), G(y, 1, 6), C(out), G(y, 1, 6), C('VSS', 'VDD', same=False)]
        pf(y, 'EN', 'VDD', 1)
        nf(out, y, 'VSS', 1); pf(out, y, 'VDD', 6); nf(out, y, 'VSS', 1); pf(out, y, 'VDD', 6)
    ports = ['GP', 'GN', 'O1P', 'O1N', 'VBN', 'EN', 'A3P']
    row = compact.Row('ct_rxamp', cols, ports=ports, wn=F, wp=F)
    row.track_order = ['S1', 'SH', 'S2', 'S3', 'O1N', 'O1P', 'GP', 'GN', 'VBN', 'DA', 'DB', 'YA', 'YB', 'EN', 'A3P', 'A3N']
    return row, ports + ['VDD', 'VSS'], net


CELLS = dict(ct_rxamp=rxamp, ct_locml=locml, ct_div5=div5core, ct_tspcn3=tspcn3, ct_mux4=mux4, ct_tspcd=tspcd, ct_phbuf8=phbuf8, ct_rxout=rxout, ct_lim=lim, ct_ring8=ring8, ct_ring9=ring9, ct_tspc2=tspc2, ct_lodrv=lodrv, ct_rxin=rxin)


def subckt(name, ports, net):
    return f'.subckt {name} {" ".join(ports)}\n' + '\n'.join(net) + f'\n.ends {name}\n'


def build(name):
    row, ports, net = CELLS[name]()
    row.build()
    work = tf.SCRATCH / 'fast' / name
    if work.exists():
        shutil.rmtree(work)
    row.emit(work, ports)
    sch = subckt(name, ports, net)
    res = compact.check(work, name, sch)
    gen = tf.GENERATED / 'fast'
    gen.mkdir(parents=True, exist_ok=True)
    for suf in ('.gds', '.mag', '.ext.spice', '.lvs.spice'):
        f = work / f'{name}{suf}'
        if f.exists():
            shutil.copy(f, gen / f'{name}{suf}')
    (gen / f'{name}.spice').write_text('* SPDX-License-Identifier: Apache-2.0\n* generated by fastcells.py (intended netlist)\n' + sch)
    shutil.copy(work / 'lvs.txt', gen / f'{name}-lvs.txt')
    det = (work / 'drc-details.txt').read_text() if (work / 'drc-details.txt').exists() else ''
    (gen / f'{name}-drc.txt').write_text(f'errors: {res["drc_errors"]}\n{det}')
    rails = {}
    for key, (net_, yy) in row.rails.items():
        rails.setdefault(net_, [0.3, yy])
    (gen / f'{name}.pins.json').write_text(json.dumps(dict(ports=ports, pins={k: list(v) for k, v in row.pins.items()},
                                                          rails=rails, bbox=[0.0, 0.0, round(row.width, 3), round(row.top, 3)]), indent=1))
    res.update(size_um=[round(row.width, 2), round(row.top, 2)], area_um2=round(row.width * row.top, 1),
               devices=len(net), work=str(work))
    print(name, json.dumps({k: v for k, v in res.items() if k != 'work'}), flush=True)
    return res


if __name__ == '__main__':
    for n in sys.argv[1:] or CELLS:
        build(n)


# --------------------------------------------------------------- speed benches
def bench(name, inc, v=3.3, **kw):
    hdr = f'.param vth={v / 2}\n.include {inc}\nVDD vdd 0 {v}\n'
    if name == 'ct_ring8':
        body = hdr + '''VT vt 0 0
VENB enb 0 0
X1 o0 o1 o2 o3 o4 o5 o6 o7 od enb vt vdd vdd 0 ct_ring8
COD od 0 15f
.ic v(x1.P0)=0 v(x1.N0)=3.3
.tran 1p 12n
.measure tran per trig v(o0) val={vth} td=6n rise=1 targ v(o0) val={vth} td=6n rise=6
.measure tran d90 trig v(o0) val={vth} td=6n rise=1 targ v(o2) val={vth} td=6n rise=1
.measure tran d45 trig v(o0) val={vth} td=6n rise=1 targ v(o1) val={vth} td=6n rise=1
.measure tran ion avg i(VDD) from=6n to=12n
'''
        def an(m):
            f = 5 / m['per'] if 'per' in m else None
            return dict(f_hz=f, phase_o0_o1_deg=(m['d45'] * f * 360 if f and 'd45' in m else None),
                        phase_o0_o2_deg=(m['d90'] * f * 360 if f and 'd90' in m else None), i_ma=-m.get('ion', math.nan) * 1e3,
                        metric=('period_ps', m['per'] / 5 * 1e12 if 'per' in m else None))
    elif name == 'ct_tspc2':
        f = kw.get('f', 2e9)
        body = hdr + f'''VCK ck 0 pulse(0 {v} 0 25p 25p {0.5 / f - 25e-12} {1 / f})
VENB enb 0 0
X1 ck q enb vdd 0 ct_tspc2
CL q 0 10f
.tran 1p {6e-9 + 12 / f}
.measure tran per trig v(q) val={{vth}} td=6n rise=1 targ v(q) val={{vth}} td=6n rise=4
.measure tran dly trig v(ck) val={{vth}} td=6n rise=1 targ v(q) val={{vth}} td=6n rise=1
.measure tran ion avg i(VDD) from=6n to={6e-9 + 12 / f}
'''
        def an(m, f=f):
            fo = 3 / m['per'] if 'per' in m else None
            return dict(f_in_hz=f, f_out_hz=fo, divides=bool(fo and abs(fo / (f / 2) - 1) < 0.01), i_ma=-m.get('ion', math.nan) * 1e3,
                        metric=('ck_to_q_ps', (m['dly'] * 1e12) % (1e12 / f * 2) if 'dly' in m else None))
    elif name == 'ct_lodrv':
        f = kw.get('f', 2.45e9)
        body = hdr + f'''VLOI loi 0 pulse(0 {v} 0 30p 30p {0.5 / f - 30e-12} {1 / f})
VINT int 0 {v}
VINTB intb 0 0
X1 loi int intb lo vdd 0 ct_lodrv
XRX rxd lo rxs 0 nfet_03v3 w=5u l=0.28u m=12
XTX txd lo txs 0 nfet_03v3 w=10u l=0.28u m=4
CW lo 0 22f
VRXD rxd 0 1.65
VRXS rxs 0 1.65
VTXD txd 0 2.5
VTXS txs 0 1.0
.tran 1p 8n
.measure tran lmax max v(lo) from=4n to=8n
.measure tran lmin min v(lo) from=4n to=8n
.measure tran dly trig v(loi) val={{vth}} td=4n rise=1 targ v(lo) val={{vth}} td=4n rise=1
.measure tran per trig v(lo) val={{vth}} td=4n rise=1 targ v(lo) val={{vth}} td=4n rise=5
.measure tran thi trig v(lo) val={{vth}} td=4n rise=1 targ v(lo) val={{vth}} td=4n fall=1
.measure tran ion avg i(VDD) from=4n to=8n
'''
        def an(m, f=f):
            fo = 4 / m['per'] if 'per' in m else None
            return dict(f_hz=fo, lo_swing_v=[m.get('lmin'), m.get('lmax')], duty=(m['thi'] * fo if fo and m.get('thi', -1) > 0 else None),
                        i_ma=-m.get('ion', math.nan) * 1e3, metric=('loi_to_lo_ps', m['dly'] * 1e12 if 'dly' in m else None))
    else:  # ct_rxin and ct_lim (same ports)
        f = kw.get('f', 2.45e9)
        a = kw.get('amp', 0.1)
        body = hdr + f'''VEN en 0 {v}
VENB enb 0 0
VS s 0 sin(0 {a} {f})
CC s in 1p
RF a1 in 40k
X1 in a1 out en enb vdd 0 {name}
CL out 0 20f
.tran 1p 30n
.measure tran per trig v(out) val={{vth}} td=20n rise=1 targ v(out) val={{vth}} td=20n rise=5
.measure tran omax max v(out) from=20n to=30n
.measure tran omin min v(out) from=20n to=30n
.measure tran a1pp pp v(a1) from=20n to=30n
.measure tran dly trig v(s) val=0 td=20n rise=1 targ v(out) val={{vth}} td=20n fall=1
.measure tran ion avg i(VDD) from=20n to=30n
'''
        def an(m, f=f):
            fo = 4 / m['per'] if 'per' in m else None
            return dict(f_hz=fo, out_swing_v=[m.get('omin'), m.get('omax')], stage1_pp_v=m.get('a1pp'),
                        i_ma=-m.get('ion', math.nan) * 1e3, metric=('in_to_out_ps', m['dly'] * 1e12 if 'dly' in m else None))
    return body, an


def speed(name, cases=None):
    from concurrent.futures import ThreadPoolExecutor
    work = tf.SCRATCH / 'fast' / name / 'sim'
    work.mkdir(parents=True, exist_ok=True)
    gen = tf.GENERATED / 'fast'
    shutil.copy(gen / f'{name}.spice', work / f'{name}.spice')
    shutil.copy(gen / f'{name}.ext.spice', work / f'{name}.ext.spice')
    cases = cases or [dict()]
    jobs = [(c, ext) for c in cases for ext in (False, True)]

    def one(j):
        c, ext = j
        inc = f'{name}.ext.spice' if ext else f'{name}.spice'
        body, an = bench(name, inc, **c)
        tag = ('ext' if ext else 'sch') + ''.join(f'_{k}{v:g}' for k, v in c.items())
        m = tf.ngspice(work, tag, tf.header() + body + '.end\n')
        r = an(m)
        r.update(netlist='extracted' if ext else 'schematic', case=c, deck=f'scratch/timing/fast/{name}/sim/{tag}.spice')
        return r
    with ThreadPoolExecutor(3) as ex:
        res = list(ex.map(one, jobs))
    return res
