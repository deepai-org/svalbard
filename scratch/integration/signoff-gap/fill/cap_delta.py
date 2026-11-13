#!/usr/bin/env python3
"""cap_delta.py <nofill.flat.spice> <fillm.flat.spice> <inst prefix> <out.json> [regex of nets to list]
Per block net: wire capacitance without fill (C0), and with the PDK fill treated two ways:
  gnd   = every dummy shape AC-grounded (upper bound),
  float = dummy shapes floating; each couples net n to the rest through C(n,f)*(Ct(f)-C(n,f))/Ct(f).
"""
import sys, re, json
from collections import defaultdict
U = {'f': 1e-15, 'p': 1e-12, 'a': 1e-18, 'n': 1e-9, 'u': 1e-6}
def caps(path):
    out = []
    for ln in open(path, errors='replace'):
        if ln[:1] in 'Cc':
            t = ln.split()
            m = re.fullmatch(r'([-+0-9.eE]+)([a-z]?)', t[3].lower())
            out.append((t[1], t[2], float(m.group(1)) * U.get(m.group(2), 1.0)))
    return out
nof, fil, pre, outp = sys.argv[1:5]
pat = re.compile(sys.argv[5]) if len(sys.argv) > 5 else None
isblk = lambda n: n.startswith(pre) or n == 'VSUBS'
c0 = defaultdict(float)
for a, b, c in caps(nof):
    c0[a] += c; c0[b] += c
cnf, cfill, ct = defaultdict(float), defaultdict(lambda: defaultdict(float)), defaultdict(float)
nfillnets = set()
for a, b, c in caps(fil):
    fa, fb = not isblk(a), not isblk(b)
    if fa: ct[a] += c; nfillnets.add(a)
    if fb: ct[b] += c; nfillnets.add(b)
    if not fa and not fb:
        cnf[a] += c; cnf[b] += c
    elif fa and not fb:
        cfill[b][a] += c
    elif fb and not fa:
        cfill[a][b] += c
rows = {}
for n in set(c0) | set(cnf) | set(cfill):
    if not n.startswith(pre): continue
    g = sum(cfill[n].values())
    fl = sum(c * (ct[f] - c) / ct[f] for f, c in cfill[n].items() if ct[f] > 0)
    rows[n] = dict(c0_fF=c0[n]*1e15, with_fill_gnd_fF=(cnf[n]+g)*1e15, with_fill_float_fF=(cnf[n]+fl)*1e15, to_fill_fF=g*1e15, n_fill_neighbours=len(cfill[n]))
tot0 = sum(r['c0_fF'] for r in rows.values())
res = dict(nets=len(rows), fill_nets=len(nfillnets), sum_c0_fF=round(tot0, 1),
           sum_with_fill_gnd_fF=round(sum(r['with_fill_gnd_fF'] for r in rows.values()), 1),
           sum_with_fill_float_fF=round(sum(r['with_fill_float_fF'] for r in rows.values()), 1))
sel = {n: {k: round(v, 3) for k, v in r.items()} for n, r in rows.items() if pat and pat.search(n)}
res['selected'] = dict(sorted(sel.items()))
big = sorted(rows.items(), key=lambda kv: -(kv[1]['with_fill_gnd_fF'] - kv[1]['c0_fF']))[:15]
res['largest_abs_increase'] = {n: {k: round(v, 3) for k, v in r.items()} for n, r in big}
json.dump(res, open(outp, 'w'), indent=1)
print({k: v for k, v in res.items() if not isinstance(v, dict)})
for n, r in res['selected'].items():
    print(f"{n[len(pre):]:28s} C0 {r['c0_fF']:8.2f}  gnd {r['with_fill_gnd_fF']:8.2f} ({(r['with_fill_gnd_fF']/max(r['c0_fF'],1e-9)-1)*100:+6.1f}%)  float {r['with_fill_float_fF']:8.2f} ({(r['with_fill_float_fF']/max(r['c0_fF'],1e-9)-1)*100:+6.1f}%)  nfill {r['n_fill_neighbours']}")
