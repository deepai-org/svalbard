"""Per-net and per-coupling-pair C cross-check: R+C netlist (terminal nodes mapped to base nets) vs the C-only extraction.
usage: ccheck.py C_ONLY RC -> prints and returns json (max |ratio - 1| per pair and per net)."""
import re, sys, json, collections
from pathlib import Path
join = lambda p: re.sub(r'\n\+\s*', ' ', Path(p).read_text()).splitlines()
base = lambda n: re.sub(r'\.[nt]\d+$', '', n)
def val(v):
    m = re.match(r'([\d.eE+-]+)([fpn]?)', v); return float(m.group(1)) * {'f': 1, 'p': 1e3, 'n': 1e6, '': 1e15}[m.group(2)]
def pairs(p, b):
    s = collections.Counter()
    for l in join(p):
        t = l.split()
        if t and t[0][0] == 'C' and len(t) >= 4: s[tuple(sorted((b(t[1]), b(t[2]))))] += val(t[3])
    return s
a, r = pairs(sys.argv[1], lambda n: n), pairs(sys.argv[2], base)
pr = [r[k] / a[k] for k in a if a[k] > 1e-3]; extra = [k for k in r if k not in a and r[k] > 1e-3]
net = collections.Counter(); netr = collections.Counter()
for (x, y), v in a.items(): net[x] += v; net[y] += v
for (x, y), v in r.items(): netr[x] += v; netr[y] += v
nr = [netr[k] / net[k] for k in net if net[k] > 1e-3]
o = dict(pairs=len(a), pair_ratio_min=round(min(pr), 6), pair_ratio_max=round(max(pr), 6), pairs_only_in_rc=len(extra), nets=len(net), net_ratio_min=round(min(nr), 6), net_ratio_max=round(max(nr), 6))
print(json.dumps(o))
