"""Compact fast cells for the wired-TX quarter-rate path.

Reuses the timing family's row compiler (analog/timing/compact.py) and cell
helpers (fastcells.py) unchanged; the timing cells ct_mux4 and ct_tspcd are
used as they are (analog/timing/generated/fast).  Cells defined here:

  wtx_win   one mux window: S = MQ&QA&QB | MH&HA&HB | MF&FA&FB (two NAND3
            levels, then a two-inverter driver for four ct_mux4 select inputs);
            SX is the active-low copy (register-clock latch)
  wtx_cinv8 eight inverters (complements of the retimed data for the YB/DPB muxes)

Each cell gets an independently written netlist that Netgen compares against
the row layout; outputs go to generated/fast/ in the timing layout format
(.mag, .gds, .pins.json, .spice).  Usage: python3 wtx_fast.py
"""
import json
import shutil
import sys
from pathlib import Path

import tools

TIMING = tools.PROJECT / 'analog/timing'
sys.path.insert(0, str(TIMING))
import compact  # noqa: E402
from fastcells import C, G, BRK, fet  # noqa: E402

FAST = tools.GENERATED / 'fast'
TIMING_FAST = TIMING / 'generated/fast'
REUSED = ('ct_mux4', 'ct_tspcd', 'ct_div5')


def _nand3(a, b, c, y, pre, wn=3, wp=3):
    S = C('VSS', 'VDD', same=False)
    cols = [S, G(a, wn, wp), dict(k='c', n=None, p=y), G(b, wn, wp), dict(k='c', n=None, p='VDD'), G(c, wn, wp),
            C(y, y)]
    net = [fet(pre + 'n1', pre + 'm1', a, 'VSS', 'VSS', wn), fet(pre + 'n2', pre + 'm2', b, pre + 'm1', 'VSS', wn),
           fet(pre + 'n3', y, c, pre + 'm2', 'VSS', wn),
           fet(pre + 'p1', y, a, 'VDD', 'VDD', wp, 'p'), fet(pre + 'p2', y, b, 'VDD', 'VDD', wp, 'p'),
           fet(pre + 'p3', y, c, 'VDD', 'VDD', wp, 'p')]
    return cols, net


def _inv(a, y, pre, wn=2, wp=4):
    cols = [C('VSS', 'VDD', same=False), G(a, wn, wp), C(y)]
    net = [fet(pre + 'n', y, a, 'VSS', 'VSS', wn), fet(pre + 'p', y, a, 'VDD', 'VDD', wp, 'p')]
    return cols, net


def win():
    cols, net = [], []
    for pre, (m, a, b), y in (('q', ('MQ', 'QA', 'QB'), 'NQ'), ('h', ('MH', 'HA', 'HB'), 'NH'),
                               ('f', ('MF', 'FA', 'FB'), 'NF')):
        c, n = _nand3(m, a, b, y, pre, wn=3, wp=3)   # window width just under 1 UI after extraction
        cols += c + [BRK]; net += n
    c, n = _nand3('NQ', 'NH', 'NF', 'SB', 'o', wn=3, wp=4)
    cols += c + [BRK]; net += n
    c, n = _inv('SB', 'SX', 'i1', 3, 6)
    cols += c + [BRK]; net += n
    c, n = _inv('SX', 'S', 'i2', 6, 12)
    cols += c; net += n
    ports = ['MQ', 'QA', 'QB', 'MH', 'HA', 'HB', 'MF', 'FA', 'FB', 'S', 'SX']
    return compact.Row('wtx_win', cols, ports=ports, wn=3, wp=3), ports + ['VDD', 'VSS'], net


def inv8():
    cols, net = [], []
    for k in range(8):
        c, n = _inv(f'A{k}', f'Y{k}', f'i{k}', 2, 4)
        cols += c + ([BRK] if k < 7 else []); net += n
    ports = [f'A{k}' for k in range(8)] + [f'Y{k}' for k in range(8)]
    return compact.Row('wtx_cinv8', cols, ports=ports, wn=2, wp=4), ports + ['VDD', 'VSS'], net


def mux4(qn=6, qp=4):
    """ct_mux4 topology (timing fastcells.mux4) re-sized for data: NAND4 with
    stronger series NMOS so output falls and rises in similar time, and a
    larger output driver.  Y = OR_k(Ak & Sk)."""
    S = C('VSS', 'VDD', same=False)
    cols, net = [], []
    for k in range(4):
        z = f'Z{k}'
        cols += [S, G(f'S{k}', 3, 3), dict(k='c', n=None, p=z), G(f'A{k}', 3, 3), C(z, 'VDD', same=False), BRK]
        net += [fet(f'n{k}a', f'm{k}', f'S{k}', 'VSS', 'VSS', 3), fet(f'n{k}b', z, f'A{k}', f'm{k}', 'VSS', 3),
                fet(f'p{k}a', z, f'S{k}', 'VDD', 'VDD', 3, 'p'), fet(f'p{k}b', z, f'A{k}', 'VDD', 'VDD', 3, 'p')]
    cols += [S, G('Z0', qn, qp), dict(k='c', n=None, p='X'), G('Z1', qn, qp), dict(k='c', n=None, p='VDD'),
             G('Z2', qn, qp), dict(k='c', n=None, p='X'), G('Z3', qn, qp), C('X', 'VDD', same=False), BRK,
             S, G('X', 3, 6), C('XB'), BRK, S, G('XB', 4, 8), C('Y'), G('XB', 4, 8), S]
    net += [fet('q0', 'u0', 'Z0', 'VSS', 'VSS', qn), fet('q1', 'u1', 'Z1', 'u0', 'VSS', qn),
            fet('q2', 'u2', 'Z2', 'u1', 'VSS', qn), fet('q3', 'X', 'Z3', 'u2', 'VSS', qn)]
    net += [fet(f'r{k}', 'X', f'Z{k}', 'VDD', 'VDD', qp, 'p') for k in range(4)]
    net += [fet('b1', 'XB', 'X', 'VSS', 'VSS', 3), fet('b2', 'XB', 'X', 'VDD', 'VDD', 6, 'p'),
            fet('b3', 'Y', 'XB', 'VSS', 'VSS', 4), fet('b4', 'Y', 'XB', 'VDD', 'VDD', 8, 'p'),
            fet('b5', 'Y', 'XB', 'VSS', 'VSS', 4), fet('b6', 'Y', 'XB', 'VDD', 'VDD', 8, 'p')]
    ports = ['A0', 'A1', 'A2', 'A3', 'S0', 'S1', 'S2', 'S3', 'Y']
    return compact.Row('wtx_mux4', cols, ports=ports, wn=3, wp=3), ports + ['VDD', 'VSS'], net


CELLS = dict(wtx_win=win, wtx_cinv8=inv8, wtx_mux4=mux4)


def subckt(name, ports, net):
    return f'.subckt {name} {" ".join(ports)}\n' + '\n'.join(net) + f'\n.ends {name}\n'


def build(name):
    row, ports, net = CELLS[name]()
    row.build()
    work = tools.SCRATCH / 'fast' / name
    if work.exists():
        shutil.rmtree(work)
    row.emit(work, ports)
    sch = subckt(name, ports, net)
    res = compact.check(work, name, sch)
    FAST.mkdir(parents=True, exist_ok=True)
    for suf in ('.gds', '.mag', '.ext.spice', '.lvs.spice'):
        if (work / f'{name}{suf}').exists():
            shutil.copy(work / f'{name}{suf}', FAST / f'{name}{suf}')
    (FAST / f'{name}.spice').write_text('* generated by wtx_fast.py (intended netlist)\n' + sch)
    shutil.copy(work / 'lvs.txt', FAST / f'{name}-lvs.txt')
    rails = {}
    for key, (n, yy) in row.rails.items():
        rails.setdefault(n, [0.3, yy])
    meta = dict(ports=ports, pins={k: list(v) for k, v in row.pins.items()}, rails=rails,
                bbox=[0.0, 0.0, round(row.width, 3), round(row.top, 3)])
    (FAST / f'{name}.pins.json').write_text(json.dumps(meta, indent=1))
    res.update(size_um=[round(row.width, 2), round(row.top, 2)], devices=len(net))
    (FAST / f'{name}-check.json').write_text(json.dumps(res, indent=1, default=str))
    print(name, json.dumps(res, default=str)[:400], flush=True)
    return res


def import_reused():
    """Copy the reused timing cells (layout + intended netlist + pins) unchanged."""
    FAST.mkdir(parents=True, exist_ok=True)
    out = {}
    for n in REUSED:
        for suf in ('.mag', '.gds', '.spice', '.pins.json', '-lvs.txt', '-drc.txt'):
            if (TIMING_FAST / f'{n}{suf}').exists():
                shutil.copy(TIMING_FAST / f'{n}{suf}', FAST / f'{n}{suf}')
        out[n] = tools.sha(TIMING_FAST / f'{n}.mag')
    return out


def lookup(name):
    return FAST / f'{name}.pins.json', FAST / f'{name}.mag', FAST / f'{name}.spice'


if __name__ == '__main__':
    print(import_reused())
    for n in sys.argv[1:] or CELLS:
        build(n)
