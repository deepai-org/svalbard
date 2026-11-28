#!/usr/bin/env python3
"""Gate-poly correction of a Magic extresist netlist (MANDATE 4a caveat; coordinator 2026-11-28):
    python3 gatefix.py <in.rc.spice> <out.spice>
Magic extresist chains the poly of a multi-finger gate finger-to-finger in series (pt_rfdriver p3_p: 178.6 ohm between
consecutive gate terminals, 44 ohm effective for 32 x 20 um fingers vs 5.4 ohm by hand). Every R that touches a MOS gate
terminal node and is above RPOLY_MIN (poly, not metal: metal segments here are < 5 ohm) is shorted, and each MOS gets the
hand gate resistance in series instead: rho * W / (3 L) per finger (one-side contact, distributed), rho = 7.3 ohm/sq
(Magic tech allpolynonres), W / L of that finger's instance line."""
import re, sys
RHO, RPOLY_MIN = 7.3, 20.0
MOS = ('nfet_03v3', 'nfet_06v0', 'nfet_06v0_nvt', 'pfet_03v3', 'pfet_06v0', 'nfet_05v0', 'pfet_05v0')
src, dst = sys.argv[1:3]
L = open(src).read().replace('\n+', ' ').split('\n')
num = lambda s: float(re.sub(r'[a-zA-Z]+$', '', s)) * {'u': 1e-6, 'n': 1e-9, 'm': 1e-3, '': 1}[re.search(r'[a-zA-Z]*$', s).group(0).lower()[:1]]
gates = set(); out = []; nsh = nadd = 0
for l in L:
    p = l.split()
    if p and p[0][0] in 'Xx' and any(m in p for m in MOS): gates.add(p[2])
for l in L:
    p = l.split()
    if p and p[0][0] in 'Rr' and len(p) >= 4 and (p[1] in gates or p[2] in gates):
        try: v = float(p[3])
        except ValueError: v = 0.0
        if v > RPOLY_MIN: p[3] = '1m'; l = ' '.join(p); nsh += 1
    elif p and p[0][0] in 'Xx' and any(m in p for m in MOS):
        kv = dict(a.split('=') for a in p if '=' in a)
        w, ln = num(kv['w']), num(kv['l'])
        rg = RHO * w / (3 * ln)
        g = p[2]; p[2] = f'{g}__hg{nadd}'; out.append(f'Rhg{nadd} {p[2]} {g} {rg:.3f}'); nadd += 1; l = ' '.join(p)
    out.append(l)
open(dst, 'w').write('\n'.join(out) + '\n')
print(f'gatefix: shorted {nsh} poly segments on gate nodes, added {nadd} hand gate resistors (rho {RHO} ohm/sq, W/3L)')
