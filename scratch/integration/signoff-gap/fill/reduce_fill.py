#!/usr/bin/env python3
"""reduce_fill.py <fillm.flat.spice> <inst prefix> <out.spice>
Replace every floating dummy-fill net by its effect on the block nets: each block net n gets a lumped capacitor to VSUBS of
sum_f C(n,f)*(Ct(f)-C(n,f))/Ct(f) (floating fill, everything else AC ground). Devices and block-to-block capacitors are kept."""
import sys, re
from collections import defaultdict
U = {'f': 1e-15, 'p': 1e-12, 'a': 1e-18, 'n': 1e-9, 'u': 1e-6}
src, pre, out = sys.argv[1:4]
isblk = lambda n: n.startswith(pre) or n == 'VSUBS'
keep, cf, ct = [], defaultdict(lambda: defaultdict(float)), defaultdict(float)
for ln in open(src, errors='replace'):
    if ln[:1] in 'Cc':
        t = ln.split(); m = re.fullmatch(r'([-+0-9.eE]+)([a-z]?)', t[3].lower()); c = float(m.group(1)) * U.get(m.group(2), 1.0)
        fa, fb = not isblk(t[1]), not isblk(t[2])
        if fa: ct[t[1]] += c
        if fb: ct[t[2]] += c
        if not fa and not fb: keep.append(ln)
        elif fa and not fb: cf[t[2]][t[1]] += c
        elif fb and not fa: cf[t[1]][t[2]] += c
    else:
        keep.append(ln)
with open(out, 'w') as f:
    f.writelines(l for l in keep if not l.strip().lower().startswith('.end'))
    i = 0
    for n, d in cf.items():
        if n == 'VSUBS': continue
        c = sum(v * (ct[k] - v) / ct[k] for k, v in d.items() if ct[k] > 0)
        f.write(f'CFILL{i} {n} VSUBS {c*1e15:.5f}f\n'); i += 1
print(out, 'lumped fill caps', i)
