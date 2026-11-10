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
from fastcells import C, G, BRK, _tspc_cols, _tspc_nand_cols, div5core  # noqa: E402

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


GATES = dict(inv=g_inv, nand2=g_nand2, nand3=g_nand3, nor2=g_nor2)
# sizes of the previous gate-level core (cells.py)
SIZE = dict(INV1=('inv', 1, 2), INV2=('inv', 2, 4), INV4=('inv', 4, 8), INV8=('inv', 8, 16),
            INV16=('inv', 16, 32), INVW=('inv', 8, 20), NAND=('nand2', 2, 2), NAND2E=('nand2', 8, 8),
            NAND2W=('nand2', 8, 8), NAND4=('nand2', 4, 4), NAND3S=('nand3', 3, 2), NOR2X=('nor2', 4, 16))


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
def qph():
    ports = ['PH', 'SERQ', 'MQ', 'MH', 'MF', 'HB', 'FC', 'G', 'XN0', 'XN1', 'XN2', 'QW', 'Q']
    gates = [('gn', 'NAND2E', 'PH', 'SERQ', 'GB'), ('gi', 'INV8', 'GB', 'G'),
             ('sa', 'NAND', 'PH', 'MQ', 'XA'), ('sb', 'NAND', 'HB', 'MH', 'XB'), ('sc', 'NAND', 'FC', 'MF', 'XC'),
             ('so', 'NAND3S', 'XA', 'XB', 'XC', 'CR'),
             ('cb', 'INV4', 'CR', 'CN'), ('cc', 'INV16', 'CN', 'C'),
             ('pw', 'NAND2E', 'C', 'SERQ', 'QWN'), ('px', 'INV16', 'QWN', 'QW'),   # QW: two NAND2W inputs + route
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
    ports = ['SERQ', 'QRST', 'HA', 'HAB', 'JB', 'JBB', 'DA', 'DC', 'LDA', 'WCKQ']
    gates = [('ri', 'INV2', 'SERQ', 'QRA'), ('rj', 'INV4', 'QRA', 'QRB'), ('rk', 'INV8', 'QRB', 'QRST'),
             ('ha', 'INV1', 'HA', 'HAB'), ('jb', 'INV1', 'JB', 'JBB'),
             ('ln', 'NOR2X', 'DA', 'DC', 'LN0'), ('lb', 'INV4', 'LN0', 'LN1'), ('lc', 'INV8', 'LN1', 'LDA'),
             ('wa', 'INV4', 'DC', 'WCN'), ('wb', 'INV16', 'WCN', 'WCKQ')]
    return row_of('wtx_q4ctl', gates, ports)


def q4ck():
    ports = ['QKN0', 'QKN1', 'QDN', 'QK0', 'QK1', 'QD']
    gates = [('k0', 'INV16', 'QKN0', 'QK0'), ('k1', 'INV16', 'QKN1', 'QK1'), ('kd', 'INV8', 'QDN', 'QD')]
    return row_of('wtx_q4ck', gates, ports)


def tspcb(name='wtx_tspcb', wo=(4, 8)):
    """timing's ct_tspcd core (same devices, Q_int = NOR(QB, ENB)) plus an INV2 -> INV4 output
    buffer in the same row.  The bare NOR output (series 4/4 um PMOS, ~6 kohm) gave 350 ps edges
    on 19 fF of routed wire and 1.2-1.7 ns on the 80-150 fF stream outputs in the extracted core."""
    cols, net = _tspc_cols('CK', 'D', 'QI', 'QB', 'X', 'Y', '')
    c, n = g_inv('ba', 'QI', 'QN', 2, 4, 2, 4)
    cols += [BRK] + c
    net += n
    c, n = g_inv('bb', 'QN', 'Q', wo[0], wo[1], 2, 4)
    cols += c[1:] if cols[-1] == c[0] else [BRK] + c
    net += n
    ports = ['CK', 'D', 'Q', 'ENB']
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


CELLS = dict(wtx_qph=qph, wtx_sreg5=sreg5, wtx_q4ctl=q4ctl, wtx_q4ck=q4ck, wtx_tspcb=tspcb,
             wtx_tspcbx=lambda: tspcb('wtx_tspcbx', (8, 16)), wtx_omux=omux, wtx_div5b=div5b)


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
HALF = {0: ('HA_', 'JA_'), 1: ('HC_', 'JB_'), 2: ('HB_', 'JC_'), 3: ('HD_', 'JD_')}


def top_instances():
    """(instance, cell, connections in cell port order).  Same connectivity as the previous
    gate-level cells.serq4 (net names kept)."""
    V = ['VDD', 'VSS']
    out = [('XCTL', 'wtx_q4ctl', ['SERQ', 'QRST', 'HA_', 'HAB', 'JB_', 'JBB', 'DA', 'DC', 'LDA', 'WCKQ'] + V),
           ('XCK', 'wtx_q4ck', ['QKN0', 'QKN1', 'QDN', 'QK0', 'QK1', 'QD'] + V),
           ('XDV', 'wtx_div5b', ['QD', 'QRST', 'DA', 'DC'] + V)]
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
    tsp = [('HA', 'G0', 'HAB', 'HA_'), ('HB', 'G0', 'HA_', 'HB_'), ('HC', 'G2', 'HA_', 'HC_'), ('HD', 'G2', 'HC_', 'HD_'),
           ('JA', 'G0', 'JBB', 'JA_'), ('JB', 'G0', 'JA_', 'JB_'), ('JC', 'G0', 'JB_', 'JC_'), ('JD', 'G0', 'JC_', 'JD_')]
    for n, ck, d, q in tsp:
        out.append((f'X{n}', 'wtx_tspcb', [ck, d, q, 'QRST'] + V))
    # streams arrive inverted (sreg5): F k = NOT(bit), so the complement outputs are swapped
    out.append(('XO', 'wtx_omux', [f'QW{k}' for k in range(4)] + [f'F{k}' for k in range(4)]
                + ['YB', 'Y', 'DPB', 'DP'] + [f'S{k}' for k in range(4)] + V))
    return out


# Floorplan (bottom to top).  Each stream's load mux, its five register flops and its retiming hops
# share a row; the four identical phase slices and the output row (window gates + muxes) sit in the
# middle, so every stream output F and every hop phase Q spans at most two rows and the four QW
# nets run from one slice row to the adjacent output row.
ROWS = [['CTL', 'DV', 'CK', 'HA', 'HB', 'HC', 'HD', 'JA', 'JB', 'JC', 'JD'],
        ['L0', 'H0_0', 'H0_1', 'L1', 'H1_0', 'H1_1', 'H1_2'],
        ['P0', 'P1', 'P2', 'P3'],
        ['O'],
        ['L2', 'H2_0', 'H2_1', 'H2_2', 'L3', 'H3_0', 'H3_1', 'H3_2']]


def macro_text():
    """Hierarchical intended netlist of wtx_serq4 (all child subckts included)."""
    txt = ''
    for n in CELLS:
        txt += (FAST / f'{n}.spice').read_text()
    return txt


def top_spice(diodes=()):
    body = [f'.subckt wtx_serq4 {" ".join(TOP_PORTS)}']
    body += [f'{i} {" ".join(c)} {cell}' for i, cell, c in top_instances()]
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


def build_top():
    import netlist as tn
    le.FAST = FAST
    for n in list(CELLS):
        tn.MACROS[n] = json.loads((FAST / f'{n}.pins.json').read_text())['ports']
    work = SCRATCH / 'top'
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    (work / 'top.spice').write_text(top_spice())
    ports, devices = tn.load(work / 'top.spice', 'wtx_serq4')
    rep = le.generate(work, 'wtx_serq4', ports, devices, rows=ROWS, max_row_width=400.0)
    W, H = rep['size_um']
    # pins for the parent (layoutgen): an M3-M5 via stack on each port trunk / power strap just
    # under the top edge; the parent's M3 riser starts there.  Above the last routing channel the
    # macro has only M5 (trunks, straps), so the stacks and risers cannot touch internal wiring.
    lab = _labels(work / 'wtx_serq4.mag')
    pin_y = round(H - 0.75, 3)
    pins, power = {}, []
    sig = [p for p in ports if p not in RAILS]
    for p in sig:
        pins[p] = [round(lab[p][0], 3), pin_y]
    x = 2.0 + 3.0
    while x < W - 2.0:
        for k, n in enumerate(('VDD', 'VSS')):
            power.append([n, round(x + 3.0 * k, 3), pin_y])
        x += le.STRAP_PITCH
    cmds = ['crashbackups stop', 'load wtx_serq4', 'units microns', 'snap internal']
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
    sch = macro_text() + top_spice(le.ad.spice_lines(rep.get('antenna_diodes', [])))
    (work / 'schematic.spice').write_text(sch)
    lvs = le.netgen_lvs(work, 'wtx_serq4.lvs.spice', 'wtx_serq4', 'schematic.spice', 'wtx_serq4')
    drc = le.drc_errors((work / 'drc-count.txt').read_text())
    (FAST / 'serq4_mag').mkdir(exist_ok=True)
    for f in work.glob('*.mag'):
        shutil.copy(f, FAST / 'serq4_mag' / f.name)
    shutil.copy(work / 'wtx_serq4.mag', FAST / 'wtx_serq4.mag')
    for suf in ('.gds', '.ext.spice', '.lvs.spice'):
        if (work / f'wtx_serq4{suf}').exists():
            shutil.copy(work / f'wtx_serq4{suf}', FAST / f'wtx_serq4{suf}')
    (FAST / 'wtx_serq4.spice').write_text('* generated by serq4_macro.py (intended netlist, hierarchical)\n' + sch)
    meta = dict(ports=TOP_PORTS, pins=pins, power_pins=power, rails={}, pin_layer='metal3',
                bbox=[0.0, 0.0, W, H], children=sorted(f.stem for f in work.glob('*.mag')))
    (FAST / 'wtx_serq4.pins.json').write_text(json.dumps(meta, indent=1))
    res = dict(size_um=[W, H], area_um2=round(W * H, 1), drc_errors=drc, lvs=lvs,
               rows=rep['rows'], antenna_diodes=len([d for d in rep.get('antenna_diodes', []) if d.get('placed')]),
               devices=sum(1 for l in sch.splitlines() if l.startswith('X') and 'fet_03v3' in l))
    (FAST / 'wtx_serq4-check.json').write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps({k: v for k, v in res.items() if k != 'rows'}, default=str)[:1200])
    return res


if __name__ == '__main__':
    what = sys.argv[1] if len(sys.argv) > 1 else 'cells'
    if what == 'cells':
        for n in sys.argv[2:] or CELLS:
            build_cell(n)
    elif what == 'top':
        build_top()
