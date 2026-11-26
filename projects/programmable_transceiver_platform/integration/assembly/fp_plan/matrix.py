#!/usr/bin/env python3
"""matrix.py <chip.json>: block list, connectivity matrix (pairs, by class), macro pin sides, pad-side links."""
import json, sys, collections, itertools
D = json.load(open(sys.argv[1])); comp = D['comp']
DIE = (3932.0, 5122.0)
def side(r):
    cx, cy = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
    dd = {'W': r[0], 'E': DIE[0] - r[2], 'S': r[1], 'N': DIE[1] - r[3]}
    return min(dd, key=dd.get)
def grp(i):
    c = comp[i]
    if i.startswith('io_') or c['master'].startswith('gf180mcu_fd_io') or i.startswith('pad_') or i.endswith('_pad') and c['master'] == 'atb_pad':
        return 'ring_' + side(c['rect'])
    if i.startswith(('antd_', 'pdn')): return None
    return i
def kind(n, cls):
    if n.startswith('c_'): return 'ctl'
    if cls == 'hook': return 'hook'
    if n.startswith(('ATB', 'atb')) or 'ATB' in n: return 'atb'
    if 'CODE' in n or n.startswith(('ADC', 'DAC')) and '[' in n: return 'bus'
    return cls
pair = collections.Counter(); pk = collections.defaultdict(collections.Counter)
for n, v in D['nets'].items():
    if v['cls'] == 'hook': continue
    g = sorted({grp(e[0]) for e in v['ends']} - {None})
    k = kind(n, v['cls'])
    for a, b in itertools.combinations(g, 2): pair[(a, b)] += 1; pk[(a, b)][k] += 1
print('BLOCKS (instance master w x h placed-rect)')
for i, c in sorted(comp.items(), key=lambda x: -x[1]['w'] * x[1]['h']):
    if grp(i) == i and c['w'] * c['h'] > 15000:
        print(f"  {i:22s} {c['master']:22s} {c['w']:7.1f} x {c['h']:7.1f}  {[round(x) for x in c['rect']]}")
print('PAIRS (>=3 nets)')
for (a, b), k in pair.most_common():
    if k >= 3: print(f'  {a:18s} {b:18s} {k:4d}  {dict(pk[(a, b)])}')
# macro pin side
m = comp['digital']; r = m['rect']
def eside(x, y):
    dd = {'W': abs(x - r[0]), 'E': abs(r[2] - x), 'S': abs(y - r[1]), 'N': abs(r[3] - y)}
    return min(dd, key=dd.get)
ms = collections.Counter(); cons = collections.defaultdict(collections.Counter)
for n, v in D['nets'].items():
    if v['cls'] == 'hook': continue
    for e in v['ends']:
        if e[0] == 'digital':
            s = eside(e[2], e[3]); ms[(s, kind(n, v['cls']))] += 1
            for f in v['ends']:
                if f[0] != 'digital' and grp(f[0]): cons[grp(f[0])][s] += 1
print('MACRO pins by side/kind', dict(ms))
print('MACRO consumers (ends by macro side)')
for g, c in sorted(cons.items(), key=lambda x: -sum(x[1].values())): print(f'  {g:20s} {sum(c.values()):4d} {dict(c)}')
