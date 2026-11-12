"""wtx_serq4 as one hand-placed compact macro (quarter/half/full-rate core of pt_wiredtx).

Why: placed device by device by layoutgen's generic serpentine row placer, the core was scattered
over the whole 0.34 mm2 block; its phase, window and load nets carried 35-350 fF of unequal routing
(extracted C0 38 fF vs C1 70 fF, QW 64-90 fF, QK 147/173 fF, LD/LDB 350 fF) and the extracted core
failed at every rate.  Here the gate-level logic of the core is compiled into standard-cell-like
compact rows (timing's compact.Row: shared diffusion, M1/M2 internal routing) and assembled with
timing's layout_engine macro placer in a fixed floorplan (as the slicer's ws_sa bank):

  wtx_qph   one phase slice, used four times with identical layout: ring-phase gate (G), one-hot
            rate select (SEL3) + buffers -> core phase C and its register-bank copy CR, the three
            CR loads (bank/divider drivers on slice 2, equal dummies elsewhere), the window-gate
            and hop phase drivers QW / Q and the window gate S = !(!(QW & QW_prev)).
            Every phase-path net is internal to the slice, so the four phases see the same
            wiring by construction; only QW -> next slice's QWP leaves the slice.
  wtx_ld5   load mux of one 5-bit stream (15 NAND2), used four times.
  wtx_q4ctl reset chain, LD/LDB buffers, WORD_CLK buffer, half/full toggle inverters.
  wtx_q4ck  register-bank (QK0/QK1) and divider (QD) phase drivers.
  wtx_tspcb / wtx_tspcbx  timing's ct_tspcd core with an output buffer (INV4 / INV8)
  wtx_div5b timing's ct_div5 counter with buffered A/C outputs
  wtx_omux  window gates + four 4:1 output muxes (wtx_mux4 topology) in one row

The schematic (cells.serq4) instantiates exactly these cells, so schematic, layout and LVS read
one netlist.  Device sizes equal the previous gate-level core (wide gates split into parallel
fingers of equal total width).

    python3 serq4_macro.py cells      # compact cells -> generated/fast (DRC, LVS each)
    python3 serq4_macro.py top        # wtx_serq4 macro -> generated/fast/wtx_serq4.*
"""
from pathlib import Path
import json
import math
import re
import shutil
import sys

import tools

TIMING = tools.PROJECT / 'analog/timing'
sys.path.insert(0, str(TIMING))
import compact  # noqa: E402
import layout_engine as le  # noqa: E402
from fastcells import C, G, BRK, _tspc_cols, fet, div5core  # noqa: E402


SREG_FAST_LD = __import__('os').environ.get('SREG_FAST_LD', '1') == '1'
NAND_TSPC_WPI = float(__import__('os').environ.get('NAND_TSPC_WPI', '3'))
NAND_TSPC_WPC = float(__import__('os').environ.get('NAND_TSPC_WPC', '4'))


def _tspc_nand_cols(ck, ins, q, qb, x, y, pre):
    """2-input merged-NAND TSPC flop (Q <= AND(ins)), charge-sharing safe (session 7).

    timing's fastcells._tspc_nand_cols puts the clock PMOS at VDD and the parallel input PMOS between
    its node n1 and X.  With CK high and both inputs high, n1 floats at VDD (plus its routed wire); when
    one input then falls (the shift data B j+1 changes right after the edge), n1 dumps onto the low X:
    extracted ff/22/3.35 at a 480 MHz ring X rose to 1.3 V inside the CK-high phase, the second stage
    evaluated, and B j flipped half a period early (43/140 errors, core 1.92 Gb/s).  Here the input
    PMOS sit at VDD and a clock PMOS sits next to X.  Layout: each input PMOS has its own clock PMOS
    (X | CK | ma | A | VDD | B | mb | CK | X), so ma / mb stay unrouted diffusion; with CK high X is
    isolated from both.  NMOS stack unchanged (VSS | A | s0 | B | X)."""
    assert len(ins) == 2
    # sizes: the series input + clock PMOS must charge X within the CK-low half period at ss/32/3.15 (3.24 Gb/s
    # core: the 2 + 3 um version lost loaded bits, 17 errors); input 3 um, clock 4 um, NMOS 4 um.
    wn, wpi, wpc = 4, NAND_TSPC_WPI, NAND_TSPC_WPC
    a, b = ins
    ma, mb = pre + 'ma', pre + 'mb'
    cols = [dict(k='c', n='-', p=x), G(ck, p=True, n=False, wp=wpc), dict(k='c', n='VSS', p=None), G(a, wn, wpi),
            dict(k='c', n=None, p='VDD'), G(b, wn, wpi), dict(k='c', n=x, p=None), G(ck, p=True, n=False, wp=wpc),
            dict(k='c', n='-', p=x), BRK]
    net = [fet(pre + 'P2A', x, ck, ma, 'VDD', wpc, 'p'), fet(pre + 'P1A', ma, a, 'VDD', 'VDD', wpi, 'p'),
           fet(pre + 'P1B', mb, b, 'VDD', 'VDD', wpi, 'p'), fet(pre + 'P2B', x, ck, mb, 'VDD', wpc, 'p'),
           fet(pre + 'N10', pre + 's0', a, 'VSS', 'VSS', wn), fet(pre + 'N11', x, b, pre + 's0', 'VSS', wn)]
    tc, tn = _tspc_cols(ck, 'UNUSED', q, qb, x, y, pre)
    cols += tc[5:]
    net += [l for l in tn if not any(l.startswith(f'X{pre}{t} ') for t in ('N1', 'P1', 'P2'))]
    return cols, net


def _tspc_ld_cols(ck, d, q, qb, x, y, pre, wo=(4, 8)):
    """TSPC flop for the stream load flag (session 7): the _tspc_cols stages 1-3 without the ENB reset and
    with a plain INV output (wo n / p um) instead of NOR(QB, ENB).  Its output drives the five load NANDs
    directly as LD (LDB = INV4(LD)); the earlier NOR output -> INV4 -> INV4 chain put LD 0.62 T after the
    clock edge, and the loaded bit's X node then had < 0.3 T to charge before the load edge (extracted
    ss/32/3.15, 3.24 Gb/s core: 13-17 errors in the word's even slots).  No reset is needed: while SERQ
    is low the stream flops are held by their own ENB."""
    cols = [C('VSS', 'VDD'), G(d, 2, 4), C(x, None, same=False), G(ck, p=True, n=False, wp=4), dict(k='c', n='-', p=x),
            dict(k='c', n=y, p='-'), G(x, 2, n=True, p=False), dict(k='c', n=None, p='VDD'), G(ck, 2, 4),
            C('VSS', y, same=False), BRK,
            dict(k='c', n=qb, p='-'), G(ck, 2, n=True, p=False), dict(k='c', n=None, p='VDD'), G(y, 2, 4),
            C('VSS', qb, same=False), BRK, C('VSS', 'VDD', same=False), G(qb, wo[0], wo[1]), C(q)]
    net = [fet(pre + 'N1', x, d, 'VSS', 'VSS', 2), fet(pre + 'P1', pre + 'm1', d, 'VDD', 'VDD', 4, 'p'),
           fet(pre + 'P2', x, ck, pre + 'm1', 'VDD', 4, 'p'),
           fet(pre + 'N2', y, x, pre + 'm2', 'VSS', 2), fet(pre + 'N3', pre + 'm2', ck, 'VSS', 'VSS', 2),
           fet(pre + 'P3', y, ck, 'VDD', 'VDD', 4, 'p'),
           fet(pre + 'N4', qb, ck, pre + 'm3', 'VSS', 2), fet(pre + 'N5', pre + 'm3', y, 'VSS', 'VSS', 2),
           fet(pre + 'P4', qb, y, 'VDD', 'VDD', 4, 'p'),
           fet(pre + 'NO', q, qb, 'VSS', 'VSS', wo[0]), fet(pre + 'PO', q, qb, 'VDD', 'VDD', wo[1], 'p')]
    return cols, net


FAST = tools.GENERATED / 'fast'
SCRATCH = tools.SCRATCH / 'serq4_macro'
RAILS = ('VSS', 'VDD')
WN_MAX, WP_MAX = 4.0, 8.0


def _fet(name, d, g, s, kind, w):
    b = 'VSS' if kind == 'n' else 'VDD'
    m = 'nfet_03v3' if kind == 'n' else 'pfet_03v3'
    return f'X{name} {d} {g} {s} {b} {m} w={w:g}u l=0.28u'


def _nf(wn, wp, nmax=WN_MAX, pmax=WP_MAX):
    nf = max(1, math.ceil(wn / nmax - 1e-9), math.ceil(wp / pmax - 1e-9))
    while abs(round(wn / nf * 20) - wn / nf * 20) > 1e-6 or abs(round(wp / nf * 20) - wp / nf * 20) > 1e-6:
        nf += 1
    return nf


def g_inv(pre, a, y, wn, wp, nmax=WN_MAX, pmax=WP_MAX):
    nf = _nf(wn, wp, nmax, pmax)
    n, p = wn / nf, wp / nf
    cols, net = [C('VSS', 'VDD', same=False)], []
    for f in range(nf):
        cols += [G(a, n, p), C(y, y) if f % 2 == 0 else C('VSS', 'VDD', same=False)]
        net += [_fet(f'{pre}n{f}', y, a, 'VSS', 'n', n), _fet(f'{pre}p{f}', y, a, 'VDD', 'p', p)]
    return cols, net


def g_nand2(pre, a, b, y, wn, wp):
    """A (the fast input) next to the output in every series stack."""
    nf = _nf(wn, wp)
    n, p = wn / nf, wp / nf
    cols, net = [C('VSS', 'VDD', same=False)], []
    for f in range(nf):
        m = f'{pre}m{f}'
        if f % 2 == 0:
            cols += [G(b, n, p), dict(k='c', n=None, p=y), G(a, n, p), C(y, 'VDD', same=False)]
        else:
            cols += [G(a, n, p), dict(k='c', n=None, p=y), G(b, n, p), C('VSS', 'VDD', same=False)]
        net += [_fet(f'{pre}na{f}', y, a, m, 'n', n), _fet(f'{pre}nb{f}', m, b, 'VSS', 'n', n),
                _fet(f'{pre}pa{f}', y, a, 'VDD', 'p', p), _fet(f'{pre}pb{f}', y, b, 'VDD', 'p', p)]
    return cols, net


def g_nand3(pre, a, b, c, y, wn, wp):
    assert wn <= WN_MAX and wp <= WP_MAX
    cols = [C('VSS', 'VDD', same=False), G(c, wn, wp), dict(k='c', n=None, p=y), G(b, wn, wp),
            dict(k='c', n=None, p='VDD'), G(a, wn, wp), C(y, y)]
    net = [_fet(f'{pre}na', y, a, f'{pre}m1', 'n', wn), _fet(f'{pre}nb', f'{pre}m1', b, f'{pre}m2', 'n', wn),
           _fet(f'{pre}nc', f'{pre}m2', c, 'VSS', 'n', wn)]
    net += [_fet(f'{pre}p{k}', y, g, 'VDD', 'p', wp) for k, g in enumerate((a, b, c))]
    return cols, net


def g_nor2(pre, a, b, y, wn, wp):
    """A next to VDD, B next to the output in every PMOS series stack (as cells.nor2)."""
    nf = _nf(wn, wp)
    n, p = wn / nf, wp / nf
    cols, net = [C('VSS', 'VDD', same=False)], []
    for f in range(nf):
        m = f'{pre}m{f}'
        if f % 2 == 0:
            cols += [G(a, n, p), dict(k='c', n=y, p=None), G(b, n, p), C('VSS', y, same=False)]
        else:
            cols += [G(b, n, p), dict(k='c', n=y, p=None), G(a, n, p), C('VSS', 'VDD', same=False)]
        net += [_fet(f'{pre}pa{f}', m, a, 'VDD', 'p', p), _fet(f'{pre}pb{f}', y, b, m, 'p', p),
                _fet(f'{pre}na{f}', y, a, 'VSS', 'n', n), _fet(f'{pre}nb{f}', y, b, 'VSS', 'n', n)]
    return cols, net


# Window gates (NAND2W, INVW): strong opening path (series NMOS, INVW PMOS), weak closing path, so the
# extracted 1-UI windows reach 0 to +20 ps overlap at ss / 3.24 Gb/s instead of 21-33 ps gaps (a gap
# lets a run of ones dip through the AND-OR mux; an overlap only delays a falling edge).  Earlier
# sizes 8/8 and 8/20 (gate-level core); NAND2W PMOS 8 -> 7 um (8/4 gave 425-444 ps windows, 12/4 + 6/24 560 ps).
GATES = dict(inv=g_inv, nand2=g_nand2, nand3=g_nand3, nor2=g_nor2)
# sizes of the previous gate-level core (cells.py)
SIZE = dict(INV1=('inv', 1, 2), INV2=('inv', 2, 4), INV4=('inv', 4, 8), INV8=('inv', 8, 16),
            INV16=('inv', 16, 32), INVW=('inv', 8, 20), NAND=('nand2', 2, 2), NAND2E=('nand2', 8, 8),
            NAND2W=('nand2', 8, 7), NAND4=('nand2', 4, 4), NAND3S=('nand3', 3, 2), NOR2X=('nor2', 4, 16))


def row_of(name, gates, ports):
    """gates: list of (prefix, SIZE key, inputs..., output).  Adjacent gates share a rail column."""
    cols, net = [], []
    for g in gates:
        pre, kind, *pins = g
        typ, wn, wp = SIZE[kind]
        c, n = GATES[typ](pre, *pins, wn, wp)
        if cols:
            if cols[-1] == c[0]:
                c = c[1:]
            else:
                cols.append(BRK)
        cols += c
        net += n
    return compact.Row(name, cols, ports=ports, wn=WN_MAX, wp=WP_MAX), ports + ['VDD', 'VSS'], net


# ------------------------------------------------------------------------------------- cells
QW_NAND, QW_INV = 'NAND2E', 'INV16'   # serq4c overrides (skewed, slot overlap)


def qph():
    ports = ['PH', 'SERQ', 'MQ', 'MH', 'MF', 'HB', 'FC', 'G', 'XN0', 'XN1', 'XN2', 'QW', 'Q']
    gates = [('gn', 'NAND2E', 'PH', 'SERQ', 'GB'), ('gi', 'INV8', 'GB', 'G'),
             ('sa', 'NAND', 'PH', 'MQ', 'XA'), ('sb', 'NAND', 'HB', 'MH', 'XB'), ('sc', 'NAND', 'FC', 'MF', 'XC'),
             ('so', 'NAND3S', 'XA', 'XB', 'XC', 'CR'),
             ('cb', 'INV4', 'CR', 'CN'), ('cc', 'INV16', 'CN', 'C'),
             ('pw', QW_NAND, 'C', 'SERQ', 'QWN'), ('px', QW_INV, 'QWN', 'QW'),   # QW: two NAND2W inputs + route
             ('pg', 'NAND2E', 'C', 'SERQ', 'QN'), ('pb', 'INV8', 'QN', 'Q'),
             ('cd', 'INV4', 'CR', 'CRN'), ('ce', 'INV16', 'CRN', 'CRR'),
             ('x0', 'NAND2E', 'CRR', 'SERQ', 'XN0'), ('x1', 'NAND2E', 'CRR', 'SERQ', 'XN1'),
             ('x2', 'NAND2E', 'CRR', 'SERQ', 'XN2')]
    return row_of('wtx_qph', gates, ports)


def sreg5():
    """One 5-bit stream register in one row (replaces load-mux cell + five separate flops).

    LD flop: TSPC on the stream's register clock CK samples LDA = NOR(DA, DC); LDB = INV4, LD = INV4,
    so LD changes one clock-to-Q after the stream's own edge.  Bit j: MA = NAND(D'j, LD),
    MB = NAND(B(j+1), LDB) (MB4 = NAND(Z = VSS, LDB) = 1), and a TSPC flop whose first stage is the
    NAND of (MA, MB) (timing's _tspc_nand_cols): B j <= AND(MA, MB) = NOT(selected input).  The mux
    is merged into the flop, so the shift and load paths are clock-to-Q + one NAND2 + the flop's
    input stage, all on local wiring (the separate NAND-NAND mux, routed X wire and flop missed the
    next edge at ss / 3.24 Gb/s in the extracted core).

    Polarity: every register stage stores the complement of what it selects, so a bit loaded into
    stage m and shifted m times reaches B0 inverted m+1 times.  Odd stages load the complemented
    word bit (local INV1 on D1, D3), so B0 = NOT(D m) for every m: the stream is carried inverted
    and the output mux complements are swapped (Y uses the FN data path, see top_instances).
    B0 leaves the row through an INV2 -> INV4 buffer (BO)."""
    ports = [f'D{j}' for j in range(5)] + ['Z', 'LDA', 'CK', 'ENB', 'BO']
    if SREG_FAST_LD:
        cols, net = _tspc_ld_cols('CK', 'LDA', 'LD', 'LQB', 'LX', 'LY', 'lf')
        gates = [('li', 'INV4', 'LD', 'LDB')]
    else:
        cols, net = _tspc_cols('CK', 'LDA', 'LDQ', 'LQB', 'LX', 'LY', 'lf')
        gates = [('li', 'INV4', 'LDQ', 'LDB'), ('lj', 'INV4', 'LDB', 'LD')]
    gates += [(f'i{j}', 'INV1', f'D{j}', f'DI{j}') for j in (1, 3)]
    for j in range(5):
        d = f'DI{j}' if j % 2 else f'D{j}'
        nxt = 'Z' if j == 4 else f'B{j + 1}'
        gates += [(f'a{j}', 'NAND', d, 'LD', f'MA{j}'), (f'b{j}', 'NAND', nxt, 'LDB', f'MB{j}')]
    row, p_, n2 = row_of('wtx_sreg5', gates, ports)
    cols += [BRK] + row.cols
    net += n2
    for j in range(5):
        c, n = _tspc_nand_cols('CK', [f'MA{j}', f'MB{j}'], f'B{j}', f'QB{j}', f'X{j}', f'Y{j}', f'r{j}')
        cols += [BRK] + c
        net += n
    for pre, a, y, wn, wp in (('oa', 'B0', 'BN', 2, 4), ('ob', 'BN', 'BO', 4, 8)):
        c, n = g_inv(pre, a, y, wn, wp, 2, 4)
        cols += [BRK] + c
        net += n
    r = compact.Row('wtx_sreg5', cols, ports=ports, wn=2, wp=4)
    # merged-NAND TSPC input stages need this track order (as timing's div5core)
    r.track_order = [n for j in range(5) for n in (f'MA{j}', f'X{j}', f'MB{j}', f'r{j}n1')]
    return r, p_, net


def q4ctl():
    """Reset chain, load decode LDA = NOR(DA, DC) (buffered, to the four stream load cells, which
    register it on their own clocks; see ld5), WORD_CLK buffer, half/full toggle inverters.

    With the registered load, the shift registers load one register period later than in the
    earlier core: four register periods after WORD_CLK rises (was three).  The word is stable from
    1.25 to 6.25 register periods after WORD_CLK rises, so the load sits 2.75 periods after the
    launch and 2.25 before the next one."""
    ports = ['SERQ', 'QRST', 'DA', 'DC', 'LDA', 'WCKQ']
    gates = [('ri', 'INV2', 'SERQ', 'QRA'), ('rj', 'INV4', 'QRA', 'QRB'), ('rk', 'INV8', 'QRB', 'QRST'),
             ('ln', 'NOR2X', 'DA', 'DC', 'LN0'), ('lb', 'INV4', 'LN0', 'LN1'), ('lc', 'INV8', 'LN1', 'LDA'),
             ('wa', 'INV4', 'DC', 'WCN'), ('wb', 'INV16', 'WCN', 'WCKQ')]
    return row_of('wtx_q4ctl', gates, ports)


def q4ck():
    ports = ['QKN0', 'QKN1', 'QDN', 'QK0', 'QK1', 'QD']
    gates = [('k0', 'INV16', 'QKN0', 'QK0'), ('k1', 'INV16', 'QKN1', 'QK1'), ('kd', 'INV8', 'QDN', 'QD')]
    return row_of('wtx_q4ck', gates, ports)


def tspcb(name='wtx_tspcb', wo=(4, 8), qn=False):
    """timing's ct_tspcd core (same devices, Q_int = NOR(QB, ENB)) plus an INV2 -> INV4 output
    buffer in the same row.  The bare NOR output (series 4/4 um PMOS, ~6 kohm) gave 350 ps edges
    on 19 fF of routed wire and 1.2-1.7 ns on the 80-150 fF stream outputs in the extracted core.
    qn=True (wtx_tspcbn) also brings out QN (= !Q, the buffer's first stage) for local feedback: the
    half-rate toggle (HA: D = own QN) and the full-rate Johnson ring (JA: D = JB's QN).  Their
    earlier feedback inverters were INV1s in wtx_q4ctl at the far end of the row; at ss/22/3.15
    (extracted) JB tcq 0.56 ns + that inverter on ~300 um of wire exceeded the 1.235 ns ring period
    and the full-rate ring divided by 5 (WORD_CLK = line/25)."""
    cols, net = _tspc_cols('CK', 'D', 'QI', 'QB', 'X', 'Y', '')
    c, n = g_inv('ba', 'QI', 'QN', 2, 4, 2, 4)
    cols += [BRK] + c
    net += n
    c, n = g_inv('bb', 'QN', 'Q', wo[0], wo[1], 2, 4)
    cols += c[1:] if cols[-1] == c[0] else [BRK] + c
    net += n
    ports = ['CK', 'D', 'Q', 'ENB'] + (['QN'] if qn else [])
    return compact.Row(name, cols, ports=ports, wn=2, wp=4), ports + ['VDD', 'VSS'], net


def div5b():
    """timing's ct_div5 counter (same devices; its loop runs on the flops' internal QB nodes) with
    INV2 -> INV4 buffers on the A and C outputs.  The bare TSPC outputs had ~900 ps edges at ss on
    the routed wire to the LD logic, which then missed the registered LD flop's setup."""
    row, _, net = div5core()
    cols = list(row.cols)
    for o in ('A', 'C'):
        for pre, a, y, wn, wp in ((f'{o.lower()}a', o, f'{o}N', 2, 4), (f'{o.lower()}b', f'{o}N', f'{o}O', 4, 8)):
            c, n = g_inv(pre, a, y, wn, wp, 2, 4)
            cols += c[1:] if cols[-1] == c[0] else [BRK] + c
            net += n
    ports = ['CK', 'ENB', 'AO', 'CO']
    r = compact.Row('wtx_div5b', cols, ports=ports, wn=2, wp=4)
    r.track_order = ['QBB', 'XA', 'QBC', 'fan1']
    return r, ports + ['VDD', 'VSS'], net


def omux():
    """Output stage in one row: the four window gates S k = QW k & QW k-1 (NAND2W + INVW, sizes of
    the earlier core), local complement inverters FN k = !F k, and the four 4:1 window muxes
    (wtx_mux4 topology and sizes): Y = OR S k & F k, YB = OR S k & FN k, DP = OR S k & F k-1,
    DPB = OR S k & FN k-1.  The 1-UI window pulses and the mux data stay on local M1/M2: routed,
    they carried 80-100 fF and did not reach full swing at ss in a 309 ps UI."""
    import wtx_fast
    ports = [f'QW{k}' for k in range(4)] + [f'F{k}' for k in range(4)] + ['Y', 'YB', 'DP', 'DPB'] + \
        [f'S{k}' for k in range(4)]     # window nets brought out for observation only (no load outside)
    gates = []
    for k in range(4):
        gates += [(f'w{k}n', 'NAND2W', f'QW{k}', f'QW{(k - 1) % 4}', f'SN{k}'), (f'w{k}i', 'INVW', f'SN{k}', f'S{k}')]
    gates += [(f'c{k}', 'INV2', f'F{k}', f'FN{k}') for k in range(4)]
    row, p_, net = row_of('wtx_omux', gates, ports)
    cols = row.cols
    for m, a, y in (('y', [f'F{k}' for k in range(4)], 'Y'), ('yb', [f'FN{k}' for k in range(4)], 'YB'),
                    ('d', [f'F{(k - 1) % 4}' for k in range(4)], 'DP'),
                    ('db', [f'FN{(k - 1) % 4}' for k in range(4)], 'DPB')):
        mrow, mports, mnet = wtx_fast.mux4()
        ren = {f'A{k}': a[k] for k in range(4)}
        ren.update({f'S{k}': f'S{k}' for k in range(4)})
        ren['Y'] = y
        ren.update(VDD='VDD', VSS='VSS')
        f = lambda n_: ren.get(n_, m + n_) if n_ not in (None, '-') else n_
        mc = []
        for c in mrow.cols:
            c = dict(c)
            for key in ('net', 'netn', 'netp', 'n', 'p'):
                if isinstance(c.get(key), str):
                    c[key] = f(c[key])
            mc.append(c)
        cols += [BRK] + mc
        for l in mnet:
            t = l.split()
            t[0] = 'X' + m + t[0][1:]
            t[1:5] = [f(x) for x in t[1:5]]
            net.append(' '.join(t))
    return compact.Row('wtx_omux', cols, ports=ports, wn=4, wp=8), p_, net


def _dff6(p, d, ck, q, qb):
    """Static positive-edge D flop from six NAND gates (three SR latches); no dynamic node."""
    return [(f'{p}1', 'NAND', f'{p}n4', f'{p}n2', f'{p}n1'), (f'{p}2', 'NAND', ck, f'{p}n1', f'{p}n2'),
            (f'{p}3', 'NAND3S', ck, f'{p}n2', f'{p}n4', f'{p}n3'), (f'{p}4', 'NAND', f'{p}n3', d, f'{p}n4'),
            (f'{p}5', 'NAND', f'{p}n2', qb, q), (f'{p}6', 'NAND', f'{p}n3', q, qb)]


def div5s():
    """Static /5 word counter (replaces the TSPC ct_div5 in wtx_div5b): a <- NOR(b, c), b <- a, c <- b
    (abc 000 -> 100 -> 110 -> 011 -> 001, self-starting from every state).  Ports as wtx_div5b
    (AO = A, CO = C buffered; ENB unused but kept: the stopped clock holds the state).
    Why: in full rate the counter clock is ring/4 (2.5 ns high phase at 810 MHz); the TSPC A flop,
    whose merged-NAND first stage sees QB_b fall early in the high phase, lost its state 1.6 ns
    into the high phase and the counter ran /4 (schematic tt: WORD_CLK = line/16, LD irregular;
    extracted ss: first half of every word lost).  Quarter rate (0.6 ns high phase) was unaffected."""
    gates = [('nr', 'NOR2X', 'B', 'C', 'DA')] + _dff6('fa', 'DA', 'CK', 'A', 'AN') + \
        _dff6('fb', 'A', 'CK', 'B', 'BN') + _dff6('fc', 'B', 'CK', 'C', 'CN') + \
        [('aa', 'INV2', 'A', 'AB2'), ('ab', 'INV4', 'AB2', 'AO'), ('ca', 'INV2', 'C', 'CB2'), ('cb', 'INV4', 'CB2', 'CO'),
         ('ed', 'INV1', 'ENB', 'ENX')]
    return row_of('wtx_div5s', gates, ['CK', 'ENB', 'AO', 'CO'])


def omux2():
    """Half-rate CMOS 2:1 stage in front of the CML final 2:1 (cml_ser.wtx_cml2), one row:
    FN k = !F k (INV2), E = QW0 ? F0 : F2, O = QW1 ? F1 : F3 and their complements EB, OB from FN,
    all NAND-NAND with the select phase on the fast (output-side) input.  E / O change only at the
    select edges (2-UI windows); the CML flops sample the window centres."""
    ports = [f'QW{k}' for k in range(4)] + [f'F{k}' for k in range(4)] + ['E', 'EB', 'O', 'OB']
    gates = [(f'c{k}', 'INV2', f'F{k}', f'FN{k}') for k in range(4)]
    for o, (s0, s1), (d0, d1) in (('E', ('QW0', 'QW2'), ('F0', 'F2')), ('EB', ('QW0', 'QW2'), ('FN0', 'FN2')),
                                  ('O', ('QW1', 'QW3'), ('F1', 'F3')), ('OB', ('QW1', 'QW3'), ('FN1', 'FN3'))):
        gates += [(f'{o.lower()}a', 'NAND4', s0, d0, f'{o}A'), (f'{o.lower()}b', 'NAND4', s1, d1, f'{o}BN'),
                  (f'{o.lower()}o', 'NAND4', f'{o}A', f'{o}BN', o)]
    return row_of('wtx_omux2', gates, ports)


CELLS = dict(wtx_qph=qph, wtx_sreg5=sreg5, wtx_q4ctl=q4ctl, wtx_q4ck=q4ck, wtx_tspcb=tspcb,
             wtx_tspcbx=lambda: tspcb('wtx_tspcbx', (8, 16)), wtx_tspcbn=lambda: tspcb('wtx_tspcbn', qn=True),
             wtx_omux=omux, wtx_omux2=omux2, wtx_div5b=div5b, wtx_div5s=div5s)
import cml_ser as _cml  # noqa: E402  (CML final 2:1 transistor rows)
CELLS.update({_n: (lambda _n=_n: _cml.row_cell(_n)) for _n in _cml.ROWDEF})


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
    for suf in ('.gds', '.mag', '.ext.spice', '.lvs.spice'):
        if (work / f'{name}{suf}').exists():
            shutil.copy(work / f'{name}{suf}', FAST / f'{name}{suf}')
    (FAST / f'{name}.spice').write_text('* generated by serq4_macro.py (intended netlist)\n' + sch)
    shutil.copy(work / 'lvs.txt', FAST / f'{name}-lvs.txt')
    rails = {}
    for key, (n, yy) in row.rails.items():
        rails.setdefault(n, [0.3, yy])
    meta = dict(ports=ports, pins={k: list(v) for k, v in row.pins.items()}, rails=rails,
                bbox=[0.0, 0.0, round(row.width, 3), round(row.top, 3)])
    (FAST / f'{name}.pins.json').write_text(json.dumps(meta, indent=1))
    res.update(size_um=[round(row.width, 2), round(row.top, 2)], devices=len(net))
    (FAST / f'{name}-check.json').write_text(json.dumps(res, indent=1, default=str))
    print(name, json.dumps({k: (v if k != 'lvs' else v.get('unique_match')) for k, v in res.items()},
                           default=str)[:400], flush=True)
    return res


# --------------------------------------------------------------------------------------- top
TOP_PORTS = [f'D{i}' for i in range(20)] + ['PH0', 'PH90', 'PH180', 'PH270', 'SERQ', 'MQ', 'MH', 'MF',
                                            'Y', 'YB', 'DP', 'DPB', 'WCKQ', 'VDD', 'VSS']
HOPS = {0: (2, 2), 1: (1, 0, 3), 2: (1, 0, 0), 3: (1, 1, 1)}
# half rate: HA toggles on G0 (PH0); HB = HA@G0 (= !HA); HY = HA@G3 (PH270, 0.75 T budget);
# HC = HY@G2 (PH180, 0.75 T); HD = HC@G2.  HC = HA delayed 1.5 T = !(HA delayed T/2), so the phase
# one UI (T/2) after HA is HD, and three UI after it HC.  (Earlier HC = HA@G2 had only T/2 = 617 ps
# for HA's clock-to-Q at 810 MHz; extracted ss tcq ~0.6 ns, so HC stuck and C1/C3 never toggled.)
HALF = {0: ('HA_', 'JA_'), 1: ('HD_', 'JB_'), 2: ('HB_', 'JC_'), 3: ('HC_', 'JD_')}


def top_instances():
    """(instance, cell, connections in cell port order).  Same connectivity as the previous
    gate-level cells.serq4 (net names kept)."""
    V = ['VDD', 'VSS']
    out = [('XCTL', 'wtx_q4ctl', ['SERQ', 'QRST', 'DA', 'DC', 'LDA', 'WCKQ'] + V),
           ('XCK', 'wtx_q4ck', ['QKN0', 'QKN1', 'QDN', 'QK0', 'QK1', 'QD'] + V),
           ('XDV', 'wtx_div5s', ['QD', 'QRST', 'DA', 'DC'] + V)]
    ph = ['PH0', 'PH90', 'PH180', 'PH270']
    for k in range(4):
        xn = ['QKN0', 'QKN1', 'QDN'] if k == 2 else [f'CXN{k}_{d}' for d in range(3)]
        g = f'G{k}' if k in (0, 2) else f'G{k}X'
        out.append((f'XP{k}', 'wtx_qph', [ph[k], 'SERQ', 'MQ', 'MH', 'MF', HALF[k][0], HALF[k][1], g] + xn
                    + [f'QW{k}', f'Q{k}'] + V))
    for k in range(4):
        out.append((f'XL{k}', 'wtx_sreg5', [f'D{k + 4 * j}' for j in range(5)]
                    + ['VSS', 'LDA', 'QK0' if k < 2 else 'QK1', 'QRST', f'B{k}_0'] + V))
    for k, seq in HOPS.items():
        prev = f'B{k}_0'
        for i, q in enumerate(seq):
            o = f'F{k}' if i == len(seq) - 1 else f'R{k}_{i}'
            cell = 'wtx_tspcbx' if i == len(seq) - 1 else 'wtx_tspcb'    # stream outputs F k: stronger
            out.append((f'XH{k}_{i}', cell, [f'Q{q}', prev, o, 'QRST'] + V))
            prev = o
    out.append(('XHA', 'wtx_tspcbn', ['G0', 'HAB', 'HA_', 'QRST', 'HAB'] + V))     # toggle: D = own QN
    out.append(('XJB', 'wtx_tspcbn', ['G0', 'JA_', 'JB_', 'QRST', 'JBB'] + V))     # Johnson feedback
    tsp = [('HB', 'G0', 'HA_', 'HB_'), ('HY', 'G3X', 'HA_', 'HY_'), ('HC', 'G2', 'HY_', 'HC_'), ('HD', 'G2', 'HC_', 'HD_'),
           ('HZ', 'G1X', 'VSS', 'HZ_'),            # dummy: G1X carries the same flop load as G3X
           ('JA', 'G0', 'JBB', 'JA_'), ('JC', 'G0', 'JB_', 'JC_'), ('JD', 'G0', 'JC_', 'JD_')]
    for n, ck, d, q in tsp:
        out.append((f'X{n}', 'wtx_tspcb', [ck, d, q, 'QRST'] + V))
    # streams arrive inverted (sreg5): F k = NOT(bit), so the complement outputs are swapped
    # half-rate CMOS 2:1 (E = QW0 ? F0 : F2, O = QW1 ? F1 : F3) + CML final 2:1 (cml_ser.wtx_cml2).
    # The streams arrive inverted (sreg5), so E / O carry NOT(bit) and the CML outputs are swapped.
    out.append(('XO', 'wtx_omux2', [f'QW{k}' for k in range(4)] + [f'F{k}' for k in range(4)]
                + ['EN_', 'E_', 'ON_', 'O_'] + V))
    out.append(('XC', 'wtx_cml2', ['E_', 'EN_', 'O_', 'ON_'] + [f'QW{k}' for k in range(4)]
                + ['SERQ', 'YB', 'Y', 'DPB', 'DP'] + V))
    return out


def _cml_rows():
    """Device rows of the CML stage inside the macro (flattened names C_<inst>_<dev>).

    Session 5 compact cluster: the CML stage occupies its own ~330 um wide column of rows at the left of
    the macro (the session-4 rows spread it over the full 530 um and carried 50-150 fF of wire on KP,
    the XOR inputs, the mux selects and the latch inputs).  Rows (bottom to top):
      c1  omux2 + clock-input buffers (QW -> P / PL) + first data delay buffers (E / O from omux2 local)
      c2  XOR + clock pre-driver (XOR inputs one row down) + second data delay buffers
      c3  E flop: driver, master, slave + output mux MY (EF and CKE local)
      c4  Y converter: level shift, two converters, inverters, feedback R, bias (YC one row down)
      c5  O flop + its dummy mux select (OF reaches MY two rows down and PM one row up)
      c6  postcursor O2 flop + postcursor mux MD (O2 and CKP local)
      c7  postcursor E2 flop + its dummy mux select (E2 one row down to MD)
      c8  DP converter (DC two rows down)
    Every clock driver sits next to its own latch pair; KP runs from c2 to the four drivers."""
    cmr = {'BL0', 'BL1', 'DKE', 'DKO', 'DKP', 'DKQ'}     # leaves with a common-mode drop resistor

    def g(*insts, t=True, r=True):
        out = []
        for i in insts:
            out += ([f'C_{i}_RCM'] if i in cmr else [])
            out += ([f'C_{i}_RLP'] if r else []) + ([f'C_{i}_T'] if t else []) + ([f'C_{i}_RLN'] if r else [])
        return out
    bias = ['C_PEN_0', 'C_PEN_1', 'C_PEN_2', 'C_PEN_3', 'C_NEI', 'C_PEI', 'C_RREF',
            'C_MREF_0', 'C_MREF_1', 'C_MREF_2', 'C_MREF_3', 'C_MOFF']

    def conv(outs, pairs):
        d = []
        for o in outs:
            d += [f'C_{o}C_T', f'C_{o}I1N', f'C_{o}I1P', f'C_{o}RF', f'C_{o}I2N', f'C_{o}I2P']
        for x in pairs:
            d += [f'C_K{x}N', f'C_K{x}P']
        return d
    return [['O'] + g('BC0', 'BL0', 'BC1', 'BL1', 'DE1', 'DO1'),
            g('DE2', 'XK', 'DK', 'DO2'),
            g('DKE', 'EM', 'ES', 'MY'),
            g('LY', r=False) + conv(('Y', 'YB'), ('YV', 'YBV')) + bias,
            g('DKO', 'OM', 'OS', 'MXO'),
            g('DKP', 'PM', 'PS', 'MD'),
            g('DKQ', 'QM', 'QS', 'MXQ'),
            g('LD', r=False) + conv(('DP', 'DPB'), ('DPV', 'DPBV'))]


CML_K_GAP = 0.0


# Floorplan (bottom to top).  Each stream's load mux, its five register flops and its retiming hops
# share a row; the four identical phase slices and the output row (window gates + muxes) sit in the
# middle, so every stream output F and every hop phase Q spans at most two rows and the four QW
# nets run from one slice row to the adjacent output row.
# Session 5: all four stream rows below the phase slices (F0..F3 reach omux2 in the first CML row), the
# CML stage as a compact column of rows above them (_cml_rows).
ROWS = [['CTL', 'DV', 'CK', 'HZ', 'HA', 'HB', 'HY', 'HC', 'HD', 'JA', 'JB', 'JC', 'JD'],
        ['L0', 'H0_0', 'H0_1', 'L1', 'H1_0', 'H1_1', 'H1_2'],
        ['L2', 'H2_0', 'H2_1', 'H2_2', 'L3', 'H3_0', 'H3_1', 'H3_2'],
        ['P0', 'P1', 'P2', 'P3'],
        *_cml_rows()]


def macro_text():
    """Hierarchical intended netlist of wtx_serq4 (all child subckts included)."""
    txt = ''
    for n in CELLS:
        txt += (FAST / f'{n}.spice').read_text()
    return txt


def _inline(cell, inst, conns, lib, out):
    """Flatten subckt `cell` (instance name inst, port connections conns) down to compact-row macros
    and primitives, with le.generate's names (devices <inst>_<dev>, internal nets <inst>.<net>), so
    the reference netlist carries the same net names as the antenna-diode lines."""
    ports, lines = lib[cell]
    m = dict(zip(ports, conns))
    m.update(VDD='VDD', VSS='VSS')
    for l in lines:
        tk = l.split()
        name, rest = tk[0][1:], tk[1:]
        sub = next((x for x in rest if '=' not in x and x in lib), None)
        params = [x for x in rest if '=' in x]
        nets = [x for x in rest if '=' not in x]
        model = nets[-1]
        nets = [m.get(n, f'{inst}.{n}') for n in nets[:-1]]
        if model in lib:
            _inline(model, f'{inst}_{name}', nets, lib, out)
        else:
            out.append(f'X{inst}_{name} {" ".join(nets)} {model} {" ".join(params)}'.rstrip())


def top_spice(diodes=()):
    body = [f'.subckt wtx_serq4 {" ".join(TOP_PORTS)}']
    lib = {}
    for c in _cml.lib_compact() + [_cml.cml2()]:
        lib[c.name] = (c.ports, c.lines)
    for i, cell, c in top_instances():
        if cell in lib:
            _inline(cell, i[1:], c, lib, body)
        else:
            body.append(f'{i} {" ".join(c)} {cell}')
    body += list(diodes)
    return '\n'.join(body + ['.ends wtx_serq4']) + '\n'


def _labels(magfile):
    """Port labels (name -> (x, y) um) in a Magic .mag written with units internal (0.005 um)."""
    out = {}
    for line in Path(magfile).read_text().splitlines():
        if line.startswith(('rlabel', 'flabel')):
            t = line.split()
            x1, y1, x2, y2, name = int(t[2]), int(t[3]), int(t[4]), int(t[5]), t[-1]
            out[name] = ((x1 + x2) / 2 * 0.005, (y1 + y2) / 2 * 0.005)
    return out


def _rects(magfile, layer):
    """Rectangles (um) of one layer in a Magic .mag written with units internal (0.005 um)."""
    out, cur = [], None
    for line in Path(magfile).read_text().splitlines():
        if line.startswith('<< '):
            cur = line[3:-3].strip()
        elif cur == layer and line.startswith('rect '):
            x1, y1, x2, y2 = (int(v) * 0.005 for v in line.split()[1:5])
            out.append((x1, y1, x2, y2))
    return out


def build_le(name, ports_list, inst_spice, children_text, rows, macros, max_row_width=400.0, workname=None, net_space=None):
    """Generic hand-floorplanned macro (le.generate) with the M3-M5 parent pin stacks of build_top."""
    import netlist as tn
    le.FAST = FAST
    for n in macros:
        tn.MACROS[n] = json.loads((FAST / f'{n}.pins.json').read_text())['ports']
    work = SCRATCH / (workname or name)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    (work / 'top.spice').write_text(children_text + inst_spice)
    ports, devices = tn.load(work / 'top.spice', name)
    if net_space:
        net_space = {n: v for n, v in (net_space(devices) if callable(net_space) else net_space).items()}
    rep = le.generate(work, name, ports, devices, rows=rows, max_row_width=max_row_width, net_space=net_space)
    W, H = rep['size_um']
    # pins for the parent (layoutgen): an M3-M5 via stack on each port trunk / power strap just
    # under the top edge; the parent's M3 riser starts there.  Above the last routing channel the
    # macro has only M5 (trunks, straps), so the stacks and risers cannot touch internal wiring.
    lab = _labels(work / f'{name}.mag')
    pin_y = round(H - 0.75, 3)
    pins, power = {}, []
    sig = [p for p in ports if p not in RAILS]
    for p in sig:
        pins[p] = [round(lab[p][0], 3), pin_y]
    # power pins on the straps as drawn (layout_engine report, cross-checked against the M5 geometry
    # of the saved .mag); never re-derived from the strap pitch
    m5 = _rects(work / f'{name}.mag', 'metal5')
    for n, sx in rep['straps']:
        hit = [r for r in m5 if r[0] - 1e-3 <= sx - le.STRAP_W / 2 and r[2] + 1e-3 >= sx + le.STRAP_W / 2
               and r[3] >= pin_y + 0.3]
        if not hit:
            raise RuntimeError(f'{name}: no M5 strap under power pin {n} x={sx}')
        power.append([n, round(sx, 3), pin_y])
    # the M3/M4 parts of every pin stack must land on empty M3/M4 (above the last channel)
    m34 = _rects(work / f'{name}.mag', 'metal3') + _rects(work / f'{name}.mag', 'metal4')
    for px in [v[0] for v in pins.values()] + [v[1] for v in power]:
        for r in m34:
            if r[0] < px + 0.9 and r[2] > px - 0.9 and r[1] < pin_y + 0.5 and r[3] > pin_y - 0.5:
                raise RuntimeError(f'{name}: pin stack at x={px} overlaps M3/M4 {r}')
    cmds = ['crashbackups stop', f'load {name}', 'units microns', 'snap internal']
    L = le.Layout()
    for p, (px, py) in pins.items():
        L.via(px, py, 3, 5)
    for n, px, py in power:
        for dx in (-0.45, 0.45):
            L.via(px + dx, py, 3, 5)
        L.rect('metal3', px - 0.65, py - 0.2, px + 0.65, py + 0.2)
    cmds += L.cmds + ['save', 'quit -noprompt']
    (work / 'pins.tcl').write_text('\n'.join(cmds) + '\n')
    le.docker_magic(work, 'pins.tcl')
    # re-run DRC / extraction / GDS after the pin stacks
    for script in ('drc.tcl', 'check.tcl'):
        le.docker_magic(work, script)
    dl = '\n'.join(le.ad.spice_lines(rep.get('antenna_diodes', [])))
    sch = children_text + inst_spice.replace(f'.ends {name}', (dl + '\n' if dl else '') + f'.ends {name}')
    (work / 'schematic.spice').write_text(sch)
    lvs = le.netgen_lvs(work, f'{name}.lvs.spice', f'{name}', 'schematic.spice', f'{name}')
    drc = le.drc_errors((work / 'drc-count.txt').read_text())
    magdir = FAST / ('serq4_mag' if name == 'wtx_serq4' else f'{name}_mag')
    magdir.mkdir(exist_ok=True)
    for f in work.glob('*.mag'):
        shutil.copy(f, magdir / f.name)
    shutil.copy(work / f'{name}.mag', FAST / f'{name}.mag')
    for suf in ('.gds', '.ext.spice', '.lvs.spice'):
        if (work / f'{name}{suf}').exists():
            shutil.copy(work / f'{name}{suf}', FAST / f'{name}{suf}')
    (FAST / f'{name}.spice').write_text('* generated by serq4_macro.py (intended netlist, hierarchical)\n' + sch)
    meta = dict(ports=ports_list, pins=pins, power_pins=power, rails={}, pin_layer='metal3',
                bbox=[0.0, 0.0, W, H], children=sorted(f.stem for f in work.glob('*.mag')))
    (FAST / f'{name}.pins.json').write_text(json.dumps(meta, indent=1))
    res = dict(size_um=[W, H], area_um2=round(W * H, 1), drc_errors=drc, lvs=lvs,
               rows=rep['rows'], antenna_diodes=len([d for d in rep.get('antenna_diodes', []) if d.get('placed')]),
               devices=sum(1 for l in sch.splitlines() if l.startswith('X') and 'fet_03v3' in l))
    (FAST / f'{name}-check.json').write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps({k: v for k, v in res.items() if k != 'rows'}, default=str)[:1200])
    return res



# Session 5: extracted, the router put each CML pair's true / complement on adjacent M4 tracks and M5
# trunks (KP / KPB 51 fF, EF / EFB 39 fF of mutual C: for a differential signal that counts twice, so KP
# saw ~130 fF effective per side) and a full-swing output trunk next to a latch output (Y -> OF 10 fF).
# Every CML signal net, and the full-swing nets that run through the CML rows, get extra clearance.
CML_SPACE_UM = 0.8
CML_AGGRESSORS = ['Y', 'YB', 'DP', 'DPB', 'E_', 'EN_', 'O_', 'ON_'] + [f'QW{k}' for k in range(4)]


def cml_net_space(devices):
    nets = {n for d in devices for n in d.nodes}
    sp = {n: CML_SPACE_UM for n in nets if n.startswith('C.') and n not in ('C.NB', 'C.RT', 'C.ENB')}
    sp.update({n: CML_SPACE_UM for n in CML_AGGRESSORS if n in nets})
    return sp


def build_top():
    return build_le('wtx_serq4', TOP_PORTS, top_spice(), macro_text(), ROWS, list(CELLS), max_row_width=560.0,
                    workname='top', net_space=cml_net_space)


if __name__ == '__main__':
    what = sys.argv[1] if len(sys.argv) > 1 else 'cells'
    if what == 'cells':
        for n in sys.argv[2:] or CELLS:
            build_cell(n)
    elif what == 'top':
        build_top()
