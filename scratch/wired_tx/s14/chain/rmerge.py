"""Series-resistor reduction of a full extresist netlist: an internal node touched by exactly two resistors and no device
terminal (capacitors allowed) is removed when one of the two resistors is < RMIN ohm; the two become one resistor of the
summed value (series R is exact) and the node's capacitors move to the neighbour across the smaller resistor (moves
C by < RMIN ohm).  usage: rmerge.py in.spice out.spice [RMIN=0.5]"""
import sys, re
from collections import defaultdict
src, dst = sys.argv[1], sys.argv[2]; RMIN = float(sys.argv[3]) if len(sys.argv) > 3 else 0.5
lines = open(src).read().replace('\n+', ' ').split('\n')
ports = set(next(l for l in lines if l.lower().startswith('.subckt')).split()[2:])
R, Cs, other = {}, {}, []
for l in lines:
    p = l.split()
    if l[:1] == 'R' and len(p) == 4:
        R[p[0]] = [p[1], p[2], float(p[3])]
    elif l[:1] == 'C' and len(p) == 4:
        Cs[p[0]] = [p[1], p[2], p[3]]
    else:
        other.append(l)
dev = set()
for l in other:
    p = l.split()
    if l[:1] == 'X': dev.update(p[1:5])
    elif l[:1] == 'D': dev.update(p[1:3])
rat = defaultdict(set); cat = defaultdict(set)
for k, (a, b, v) in R.items(): rat[a].add(k); rat[b].add(k)
for k, (a, b, v) in Cs.items(): cat[a].add(k); cat[b].add(k)
n0 = len(R); changed = True
while changed:
    changed = False
    for n in list(rat):
        rs = rat[n]
        if len(rs) != 2 or n in ports or n in dev or n in ('VDD', 'VSS', '0'):
            continue
        k1, k2 = sorted(rs, key=lambda k: R[k][2])
        if R[k1][2] >= RMIN:
            continue
        o1 = R[k1][0] if R[k1][1] == n else R[k1][1]; o2 = R[k2][0] if R[k2][1] == n else R[k2][1]
        if o1 == o2:
            continue
        R[k2] = [o1, o2, R[k1][2] + R[k2][2]]
        rat[o1].discard(k1); rat[o1].add(k2); rat[o2].discard(k2); rat[o2].add(k2)
        del R[k1]; del rat[n]
        for c in list(cat[n]):
            a, b, v = Cs[c]; Cs[c] = [o1 if a == n else a, o1 if b == n else b, v]; cat[o1].add(c)
        del cat[n]; changed = True
out = []
for l in other:
    if l.lower().startswith('.ends'):
        out += [f'{k} {a} {b} {v:.6g}' for k, (a, b, v) in R.items()]
        out += [f'{k} {a} {b} {v}' for k, (a, b, v) in Cs.items() if a != b]
    out.append(l)
open(dst, 'w').write('\n'.join(out))
print(f'R {n0} -> {len(R)} (RMIN {RMIN} ohm)')
