#!/usr/bin/env python3
"""CP4-1 condition on a gate-level netlist of pt_digital_macro (any flow stage, final included):

  every pin of integration/top/generated/macro_clamps.txt is connected to exactly one cell input,
  an input of a gf180mcu_fd_sc_mcu7t5v0__and2_* whose instance name ends in `.iso_and`, plus (optionally)
  antenna diodes; no buffer, hold cell or any other load sits between the pin and the AND2, and there are
  exactly as many `.iso_and` cells as listed pins. The other input of each AND2 must not be a constant.
  The resizer may change the drive strength and swap the two (equivalent) inputs: the cells cannot be dont_touch
  instances, because OpenROAD then refuses to buffer the nets they load (rst_n, island_on: RSZ-3006). What protects
  the pin is the dont_touch on the pin NET (RSZ_DONT_TOUCH_LIST) and this check on the final netlist.

Usage: clamp_check.py <netlist.v> [--clamps macro_clamps.txt]   (exit 1 on any violation)
Self-test: clamp_check.py --selftest  (three injected faults must be caught)
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLAMPS = HERE.parents[1] / 'integration/top/generated/macro_clamps.txt'
INST = re.compile(r'^\s*(gf180mcu_\w+)\s+(\\\S+\s|\w+)\s*\((.*?)\)\s*;', re.S | re.M)
CONN = re.compile(r'\.(\w+)\s*\(\s*(.*?)\s*\)\s*(?:,|$)', re.S)


def norm(n):
    n = n.strip()
    if n.startswith('\\'):
        n = n[1:]
    return re.sub(r'\s+', '', n)


def check(text, clamps):
    loads = {}       # net -> [(cell, inst, pin)]
    isos = {}
    for m in INST.finditer(text):
        cell, inst, body = m.group(1), norm(m.group(2)), m.group(3)
        pins = {p: norm(n) for p, n in CONN.findall(body)}
        if inst.endswith('.iso_and'):
            isos[inst] = (cell, pins)
        for p, n in pins.items():
            if p in ('Z', 'ZN', 'Q', 'VDD', 'VSS', 'VNW', 'VPW'):
                continue
            loads.setdefault(n, []).append((cell, inst, p))
    errs = []
    if len(isos) != len(clamps):
        errs.append(f'{len(isos)} .iso_and cells for {len(clamps)} clamp pins')
    seen = set()
    for inst, (cell, pins) in sorted(isos.items()):
        if not re.search(r'__and2_\d+$', cell):
            errs.append(f'{inst}: cell is {cell}, not an and2')
        ins = [pins.get('A1', ''), pins.get('A2', '')]
        hit = [n for n in ins if n in clamps]
        if len(hit) != 1:
            errs.append(f'{inst}: inputs {ins}: exactly one must be a clamp pin (something sits between the pin and the AND2)')
            continue
        seen.add(hit[0])
        other = ins[1] if ins[0] == hit[0] else ins[0]
        if re.match(r"^\d+'", other) or other == '':
            errs.append(f'{inst}: enable input is constant / open ({other})')
    for pin in sorted(clamps):
        if pin not in seen:
            errs.append(f'{pin}: no .iso_and cell has it on A1')
        for cell, inst, p in loads.get(pin, []):
            if inst.endswith('.iso_and') and p in ('A1', 'A2'):
                continue
            if 'antenna' in cell:
                continue
            errs.append(f'{pin}: extra load {inst} ({cell}.{p})')
    return errs, len(isos)


def read_clamps(path):
    return {l.split()[0] for l in Path(path).read_text().splitlines() if l.strip() and not l.startswith('#')}


def selftest():
    good = '''
 gf180mcu_fd_sc_mcu7t5v0__and2_1 \\iso_a.g[0].iso_and  ( .A1(a), .A2(on), .Z(y0) );
 gf180mcu_fd_sc_mcu7t5v0__and2_1 \\iso_b.g[1].iso_and  ( .A1(\\b[1] ), .A2(on), .Z(y1) );
 gf180mcu_fd_sc_mcu7t5v0__antenna ANTENNA_1 ( .I(a) );
'''
    clamps = {'a', 'b[1]'}
    assert check(good, clamps)[0] == [], check(good, clamps)
    swapped = good.replace('.A1(a), .A2(on)', '.A1(on), .A2(a)').replace('and2_1 \\iso_a', 'and2_2 \\iso_a')
    assert check(swapped, clamps)[0] == [], check(swapped, clamps)
    bad1 = good.replace('.A1(a)', '.A1(net5)') + ' gf180mcu_fd_sc_mcu7t5v0__buf_1 input7 ( .I(a), .Z(net5) );\n'
    bad2 = good + ' gf180mcu_fd_sc_mcu7t5v0__dlyb_1 hold3 ( .I(\\b[1] ), .Z(h) );\n'
    bad3 = good.replace('.A2(on), .Z(y1)', ".A2(1'h1), .Z(y1)")
    for i, b in enumerate((bad1, bad2, bad3), 1):
        assert check(b, clamps)[0], f'injected fault {i} not caught'
    print('clamp_check selftest: clean case passes, 3 injected faults caught')


def main():
    if '--selftest' in sys.argv:
        return selftest()
    clamps_path = CLAMPS
    if '--clamps' in sys.argv:
        clamps_path = sys.argv[sys.argv.index('--clamps') + 1]
    clamps = read_clamps(clamps_path)
    errs, n = check(Path(sys.argv[1]).read_text(), clamps)
    for e in errs:
        print('CLAMP-ERROR', e)
    print(f'clamp_check: {n} iso_and cells, {len(clamps)} clamp pins, {len(errs)} errors')
    sys.exit(1 if errs else 0)


if __name__ == '__main__':
    main()
