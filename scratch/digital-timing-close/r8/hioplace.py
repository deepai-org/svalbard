#!/usr/bin/env python3
"""hioplace.py <synth netlist> <floorplan/tap DEF> <out dir>

TC13 pad-edge host-link I/O block: FIXED (FIRM) placement of the hand-instantiated D2H launch/output
cells (south edge, next to d2h_clk_pin / d2h_pin) and H2D capture cells (north edge, next to h2d_clk /
h2d_pin), plus the dont-touch list for the resizer.

Writes  <out>/hio_placement.cfg  (MACRO_PLACEMENT_CFG: name x_um y_um orient; LibreLane's
        ManualMacroPlacement sets FIRM, before tap insertion / global placement)
        <out>/hio_dont_touch.txt (RSZ_DONT_TOUCH_LIST: hio_* instances + every net from launch Q to the
        D2H pin and from the H2D pin to the capture D)
        <out>/hio_layout.txt     (human-readable table)
Cells are placed on the site grid of the given DEF's rows, skipping the tap cells of that DEF (same die,
rows and tap rule as the run), one 21.28 um column per lane so every lane has the same cell stack.
"""
import re, sys, json
from pathlib import Path

nl_path, def_path, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
nl = open(nl_path).read()
# ---- instances and their pin->net maps
inst = {}
for m in re.finditer(r'^\s*(gf180mcu_fd_sc_mcu7t5v0__\w+)\s+(\\\S+|\S+)\s*\((.*?)\);', nl, re.M | re.S):
    cell, name, body = m.group(1), m.group(2).lstrip('\\'), m.group(3)
    pins = {p: n.strip().lstrip('\\').strip() for p, n in re.findall(r'\.(\w+)\(\s*(.*?)\s*\)\s*(?:,|$)', body, re.S)}
    inst[name] = (cell, pins)
W = {'dffrnq_1': 22.40, 'dffnrnq_1': 22.40, 'xor2_1': 6.72, 'buf_1': 3.36, 'mux2_2': 8.40, 'buf_8': 14.56, 'clkbuf_8': 14.56, 'clkinv_2': 3.36, 'clkinv_8': 10.08}
def need(n):
    if n not in inst: sys.exit(f'missing instance {n}')
    return n
# ---- rows and taps from the DEF
d = open(def_path).read()
dbu = int(re.search(r'UNITS DISTANCE MICRONS (\d+)', d).group(1))
rows = {}
for m in re.finditer(r'^ROW (\S+) \S+ (\d+) (\d+) (\w+) DO (\d+) BY 1 STEP (\d+) 0', d, re.M):
    idx = int(m.group(1).split('_')[-1]); rows[idx] = dict(x0=int(m.group(2)), y=int(m.group(3)), orient=m.group(4), n=int(m.group(5)), step=int(m.group(6)))
SITE = rows[0]['step']
taps = {}
comp = d[d.index('\nCOMPONENTS'):d.index('END COMPONENTS')]
for m in re.finditer(r'- (\S+) (gf180mcu_fd_sc_mcu7t5v0__(?:filltie|endcap))[^;]*?\+ (?:FIXED|PLACED|FIRM) \( (\d+) (\d+) \)', comp):
    taps.setdefault(int(m.group(4)), []).append((int(m.group(3)), int(m.group(3)) + int(1.12 * dbu)))
yrow = {r['y']: k for k, r in rows.items()}
used = {}   # row -> list of (x0,x1)
def place(name, row, x_um):
    """first free site at or right of x_um in `row` (no tap / no placed cell overlap)"""
    cell = inst[need(name)][0].split('__')[1]
    w = int(round(W[cell] * dbu)); r = rows[row]
    k = max(0, -(-(int(round(x_um * dbu)) - r['x0']) // SITE))
    occ = taps.get(r['y'], []) + used.get(row, [])
    while True:
        x = r['x0'] + k * SITE
        if all(x + w <= a or x >= b for a, b in occ): break
        k += 1
    used.setdefault(row, []).append((x, x + w))
    return dict(name=name, cell=cell, row=row, x=x / dbu, y=r['y'] / dbu, orient=r['orient'])
P = []
COL = 24.64
# ---- D2H, south edge: lanes = forwarded clock, then data 0..9 (pin order); rows 0 (output) .. 5
d2h_lanes = [('host.gearbox.lc', 'host.clk_out', 'host.hio_cob')] + \
            [(f'host.gearbox.lq[{i}].l', f'host.stagger[{i}].lane', f'host.stagger[{i}].hio_ob') for i in range(10)]
X0 = 630.0
for j, (ln, st, ob) in enumerate(d2h_lanes):
    x = X0 + COL * j
    P.append(place(ob, 0, x))
    P.append(place(f'{st}.hio_m', 1, x))
    P.append(place(f'{st}.hio_d0', 2, x)); P.append(place(f'{st}.hio_d1', 2, x + 3.36))
    P.append(place(f'{ln}.hio_x', 3, x))
    P.append(place(f'{ln}.hio_i', 3, x + 8.96))
    P.append(place(f'{ln}.lf', 4, x))
    P.append(place(f'{ln}.lr', 5, x))
# ODDR select buffer (TC13 r4): centred above the launch rows, drives the 11 lane mux selects
P.append(place('host.gearbox.hio_sel', 6, X0 + COL * 5))
P.append(place('host.gearbox.hio_msel', 6, X0 + COL * 5 + 20.0))
# ---- H2D, north edge: top row = input buffers (+ cap_root), then (mux, flop) row pairs r, f, fhh
top = max(rows)
HX0 = 100.0
P.append(place('host.h2d.cap_root.cell', top, HX0 - COL))
P.append(place('host.h2d.core_root.cell', top - 1, HX0 - COL))
# fixed capture-clock row buffers (pt_cts_h2d.tcl keeps CTS out): centred under the block, one row below
for k, cb in enumerate(('cbr', 'cbf', 'cbh')):
    P.append(place(f'host.h2d.hio_{cb}.cell', top - 7, HX0 + COL * 3 + 18.0 * k))
for i in range(10):
    x = HX0 + COL * i
    P.append(place(f'host.h2d.ib[{i}].b.hio_ib', top, x))
    for k, (cap, ff) in enumerate([(f'host.h2d.cap[{i}].cr', 'p.lr'), (f'host.h2d.cap[{i}].cf', 'n.lf'), (f'host.h2d.fhh[{i}].c', 'n.lf')]):
        P.append(place(f'{cap}.hio_m', top - 1 - 2 * k, x))
        P.append(place(f'{cap}.{ff}', top - 2 - 2 * k, x))
with open(out / 'hio_placement.cfg', 'w') as f:
    for p in P: f.write(f"{p['name']} {p['x']:.2f} {p['y']:.2f} {p['orient']}\n")
with open(out / 'hio_layout.txt', 'w') as f:
    for p in sorted(P, key=lambda p: (-p['row'], p['x'])): f.write(f"row {p['row']:3d} x {p['x']:8.2f} y {p['y']:8.2f} {p['orient']:2s} {p['cell']:10s} {p['name']}\n")
# ---- dont-touch list
# hio_m muxes are NOT dont_touch instances: their select (and the capture flops' Q feedback, the SDR
# clock gate) are ordinary logic nets that repair_design may need to buffer, which OpenROAD refuses
# before dont_touch load pins (TC13 pA/pB: RSZ-3006 on the d2h_stagger select net). Their data nets are
# dont_touch; the cell types are checked after the run (hio/hiocheck.py).
dt_cells = sorted(n for n in inst if re.search(r'(^|\.)hio_\w+$', n))
dt_inst = [n for n in dt_cells if not n.endswith('.hio_m')]
dt_nets = set()
for n in dt_cells:
    cell, pins = inst[n]
    if n.endswith(('.hio_sel', '.hio_msel')): continue                     # clock nets (CTS refuses dont_touch clock nets)
    for p, net in pins.items():
        if p == 'S': continue                                   # select nets: ordinary logic
        if p == 'I1' and n == 'host.clk_out.hio_m': continue   # SDR forwarded-clock gate: logic
        dt_nets.add(net)
bad = [x for x in dt_nets if x.startswith("1'") or x == '']
if bad: sys.exit(f'constant nets in dont-touch list: {bad}')
(out / 'hio_dont_touch.txt').write_text(' '.join(dt_inst + sorted(dt_nets)) + '\n')
print(json.dumps(dict(placed=len(P), dont_touch_instances=len(dt_inst), dont_touch_nets=len(dt_nets))))
