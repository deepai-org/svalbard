"""Tank-net C of the QVCO core top outside the RF cell: top.c.spice minus the RF cell's c.spice (C-only, flat).
usage: topc.py <top.c.spice> <rf c.spice> <out.json>"""
import sys, json, re
from collections import defaultdict
T = ('IP', 'IN', 'QP', 'QN')
def v(s):
    m = {'f': 1e-15, 'p': 1e-12, 'a': 1e-18}
    return float(s[:-1]) * m[s[-1]] if s[-1] in m else float(s)
def tab(f):
    g, mu = defaultdict(float), defaultdict(float)
    for l in open(f):
        p = l.split()
        if not l.startswith('C') or len(p) < 4: continue
        a, b = [re.sub(r'^.*/', '', x) for x in p[1:3]]
        c = v(p[3]) * 1e15
        if a in T and b in T: mu['-'.join(sorted((a, b), key=T.index)).lower()] += c
        elif a in T: g[a.lower()] += c
        elif b in T: g[b.lower()] += c
    return g, mu
g1, m1 = tab(sys.argv[1]); g0, m0 = tab(sys.argv[2])
out = dict(gnd={k: round(g1[k] - g0.get(k, 0), 2) for k in g1}, mut={k: round(m1[k] - m0.get(k, 0), 2) for k in m1})
json.dump(out, open(sys.argv[3], 'w'), indent=1); print(out)
