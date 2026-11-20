"""Correct the substrate capacitance of a Magic extresist netlist (ext2spice extresist on).
Found 2026-11-20: for a resisted net ext2spice writes the net's lumped substrate cap on the root node AND the extresist
rnode caps, and the rnode caps alone sum to several times the net's substrate cap in the .ext node record (XMUX.XE0:
node 10.38 fF, rnodes 36.3 fF, root 10.67 fF -> 47 fF written).  Fix: per net (base name, .tN/.nN stripped) scale every
'**FLOATING' (substrate) capacitor of the root and its sub-nodes so that their sum equals the .ext node cap.  Resistors
and coupling capacitors are unchanged.  usage: fixcap.py <flat.ext> <in.spice> <out.spice>"""
import re, sys
from collections import defaultdict
ext, src, dst = sys.argv[1:4]
cnode = {}
for l in open(ext):
    if l.startswith('node '):
        p = l.split(); cnode[p[1].strip('"').rstrip('#')] = float(p[3]) * 1e-18
def v(s):
    m = {'f': 1e-15, 'p': 1e-12, 'n': 1e-9, 'a': 1e-18}
    return float(s[:-1]) * m[s[-1]] if s[-1] in m else float(s)
base = lambda n: re.sub(r'\.(t|n)\d+$', '', n).rstrip('#')
L = open(src).read().split('\n')
tot = defaultdict(float); idx = []
for i, l in enumerate(L):
    p = l.split()
    if l.startswith('C') and 'FLOATING' in l:
        n = p[1] if p[2] in ('VSS', 'VDD') else p[2]
        tot[base(n)] += v(p[3]); idx.append((i, base(n)))
miss = 0; before = sum(tot.values()); after = 0
for i, b in idx:
    p = L[i].split()
    k = cnode[b] / tot[b] if b in cnode and tot[b] > 0 else 1.0
    if b not in cnode: miss += 1
    c = v(p[3]) * k; after += c
    L[i] = f'{p[0]} {p[1]} {p[2]} {c:.6g}'
open(dst, 'w').write('\n'.join(L))
print(f'substrate C {before * 1e12:.2f} pF -> {after * 1e12:.2f} pF; nets {len(tot)}, without .ext node record {miss} caps')
