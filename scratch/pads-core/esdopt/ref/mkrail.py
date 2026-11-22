#!/usr/bin/env python3
"""mkrail.py <model.spice> <asm_flat.spice (cell + rail cells, railcap.sh)> <physical.spice (cell alone)> <out.spice> [extra_fF_on_PAD_P]
Model variant with the UNDER-RAIL capacitance: per pad, (sum of the Magic C lines on PAD_x with the provider rail cell over the
cell) - (the same sum for the cell alone) is added as one capacitor PAD_x -> VSS inside the wrapper (all ring rails are AC ground).
Optional last argument: a test capacitor on PAD_P (known-answer control of the capacitance read-out)."""
import sys, re, collections
U = {'f': 1., 'p': 1e3, 'a': 1e-3, 'n': 1e6, '': 1e15}
def capsum(path):
    tot = collections.Counter()
    for line in open(path):
        t = line.split()
        if len(t) >= 4 and t[0][0] == 'C' and not t[3].startswith('cap_'):
            m = re.fullmatch(r'([0-9.eE+-]+)([fpan]?)F?', t[3])
            if not m: continue
            for a in t[1:3]:
                if a in ('PAD_P', 'PAD_N'): tot[a] += float(m[1]) * U[m[2]]
    return tot
a, c = capsum(sys.argv[2]), capsum(sys.argv[3]); txt = open(sys.argv[1]).read().splitlines()
i = next(k for k, l in enumerate(txt) if l.startswith('.ends tx_protected_pad'))
add = [f'CRAIL_{p[-1]} {p} VSS {a[p] - c[p]:.2f}f' for p in ('PAD_P', 'PAD_N')]
if len(sys.argv) > 5: add.append(f'CTEST PAD_P VSS {float(sys.argv[5]):.2f}f')
txt[i:i] = ['* under-rail capacitance (mkrail.py): with rail cell %s, cell alone %s' % (dict(a), dict(c))] + add
open(sys.argv[4], 'w').write('\n'.join(txt) + '\n'); print(sys.argv[4], add)
