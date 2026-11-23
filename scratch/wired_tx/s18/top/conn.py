"""connectivity of Metal1-5 + vias in a flattened GDS; returns component id per shape and label sets."""
import sys
from collections import defaultdict
import gdsflat as G
ML = {34: 1, 36: 2, 42: 3, 46: 4, 81: 5}
VL = {35: (1, 2), 38: (2, 3), 40: (3, 4), 41: (4, 5)}
TL = {34: 1, 36: 2, 42: 3, 46: 4, 81: 5}

def build(gds, top):
    b, t = G.flatten(G.parse(gds), top)
    sh = []
    for (l, d), rs in b.items():
        if d == 0 and l in ML:
            sh += [('m', ML[l], r) for r in rs]
        elif d == 0 and l in VL:
            sh += [('v', VL[l], r) for r in rs]
    par = list(range(len(sh)))
    def f(i):
        while par[i] != i:
            par[i] = par[par[i]]; i = par[i]
        return i
    def u(i, j):
        a, c = f(i), f(j)
        if a != c: par[a] = c
    grid = defaultdict(list)
    S = 5.0
    for i, (k, l, r) in enumerate(sh):
        for gx in range(int(r[0] // S), int(r[2] // S) + 1):
            for gy in range(int(r[1] // S), int(r[3] // S) + 1):
                grid[(gx, gy)].append(i)
    def ov(a, c, touch):
        e = 0.0 if touch else -1e-6
        return a[0] <= c[2] + e and c[0] <= a[2] + e and a[1] <= c[3] + e and c[1] <= a[3] + e if touch else a[0] < c[2] and c[0] < a[2] and a[1] < c[3] and c[1] < a[3]
    for cell, ids in grid.items():
        for x in range(len(ids)):
            i = ids[x]; ki, li, ri = sh[i]
            for y in range(x + 1, len(ids)):
                j = ids[y]; kj, lj, rj = sh[j]
                if ki == 'm' and kj == 'm':
                    if li == lj and ov(ri, rj, True): u(i, j)
                elif ki == 'm' and kj == 'v':
                    if li in lj and ov(ri, rj, False): u(i, j)
                elif ki == 'v' and kj == 'm':
                    if lj in li and ov(ri, rj, False): u(i, j)
    lab = defaultdict(set)
    for (l, d, x, y, s_, cell) in t:
        for i in grid.get((int(x // S), int(y // S)), []):
            k, ll, r = sh[i]
            if k == 'm' and r[0] <= x <= r[2] and r[1] <= y <= r[3]:
                lab[f(i)].add(s_ if cell == top else f'{cell}:{s_}')
    comp = [f(i) for i in range(len(sh))]
    return sh, comp, lab
