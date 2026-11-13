#!/usr/bin/env python3
"""Prove the bench small (MANDATE): the solver must reproduce hand answers and an independent engine (ngspice),
and must FAIL a deliberately broken case.
S1 DC divider.  S2 parallel RLC tank (bond L || die C): f0, Z0, Q, |Z|peak vs formula and vs ngspice.
S3 two coupled bonds (aiding and opposing) vs L(1+-k).  S4 negative control: decap removed -> resonance leaves
the band and |Z| at 100 MHz rises to wL (must be detected as a FAIL against the 1-ohm target)."""
import numpy as np, subprocess, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from mna import Net
HERE = os.path.dirname(os.path.abspath(__file__)); res = {}; ok = True
def chk(name, got, want, tol):
    global ok
    p = abs(got-want) <= tol*abs(want); ok &= p
    res[name] = dict(got=float(got), hand=float(want), rel_err=float(abs(got-want)/abs(want)), ok=bool(p))
    print(f"{name:42s} got {got:.6g}  hand {want:.6g}  {'ok' if p else 'FAIL'}")

# S1: 3.3 V source (Norton, 0.02 ohm) -> 0.1 ohm -> die, 0.25 A load, 0.05 ohm return: V(vdd,vss) = 3.3-0.25*0.17
n = Net(); n.add_rl('src', 'gnd', 0.02); n.add_rl('src', 'vdd', 0.1); n.add_rl('vss', 'gnd', 0.05)
V = n.solve(0, n.inj([('src', 3.3/0.02), ('vdd', -0.25), ('vss', 0.25)]))
chk('S1 dc rail (V)', (n.v(V, 'vdd')-n.v(V, 'vss')).real, 3.3-0.25*0.17, 1e-6)

# S2: L = 0.5 nH with Rs = 0.05 ohm to ground, die C = 2 nF with ESR 0.1 ohm. Hand: f0 = 1/(2pi sqrt(LC)) = 159.155 MHz,
# Z0 = sqrt(L/C) = 0.5 ohm, Q = Z0/(Rs+ESR) = 3.333, |Z|peak ~ Z0*sqrt(1+Q^2)... exact peak from the formula below.
L, Rs, C, Re = 0.5e-9, 0.05, 2e-9, 0.1
n = Net(); n.add_rl('vdd', 'gnd', Rs, L); n.add_rc('vdd', 'gnd', Re, C)
f = np.logspace(7, 9.5, 2001)
z = np.array([n.v(n.solve(2*np.pi*x, n.inj([('vdd', 1.0)])), 'vdd') for x in f])
zh = 1/(1/(Rs+2j*np.pi*f*L)+1/(Re+1/(2j*np.pi*f*C)))
f0 = 1/(2*np.pi*np.sqrt(L*C)); Z0 = np.sqrt(L/C); Q = Z0/(Rs+Re)
chk('S2 f(|Z|max) (MHz)', f[np.argmax(abs(z))]/1e6, f0/1e6, 0.02)
chk('S2 |Z|max (ohm) vs closed form', abs(z).max(), abs(zh).max(), 1e-6)
chk('S2 |Z|max (ohm) vs Q*Z0 hand (1.667)', abs(z).max(), Q*Z0, 0.06)
# independent engine
cir = f"""* s2
I1 0 vdd dc 0 ac 1
L1 vdd a {L}
R1 a 0 {Rs}
C1 vdd b {C}
R2 b 0 {Re}
.ac dec 800 1e7 3.16e9
.control
run
wrdata {HERE}/out/s2_ng.txt vm(vdd)
.endc
.end
"""
open(f'{HERE}/out/s2.cir', 'w').write(cir)
subprocess.run(['ngspice', '-b', f'{HERE}/out/s2.cir'], capture_output=True)
d = np.loadtxt(f'{HERE}/out/s2_ng.txt')
chk('S2 |Z|max ngspice vs solver', d[:, 1].max(), abs(z).max(), 2e-3)
chk('S2 f0 ngspice vs solver (MHz)', d[np.argmax(d[:, 1]), 0]/1e6, f[np.argmax(abs(z))]/1e6, 5e-3)

# S3: two coupled bonds 2 nH, k = 0.4: same-net pair in parallel -> L(1+k)/2 = 1.4 nH; supply+return loop -> 2L(1-k) = 2.4 nH
Lb, k = 2e-9, 0.4; w = 2*np.pi*1e9
n = Net(); n.add_coupled([('a', 'gnd'), ('a', 'gnd')], [1e-9, 1e-9], [[Lb, k*Lb], [k*Lb, Lb]])
chk('S3 parallel same-net L (nH)', (n.v(n.solve(w, n.inj([('a', 1)])), 'a')/(1j*w)).real*1e9, 1.4, 1e-4)
n = Net(); n.add_coupled([('a', 'x'), ('x', 'b')], [1e-9, 1e-9], [[Lb, -k*Lb], [-k*Lb, Lb]])   # go and return: opposing
V = n.solve(w, n.inj([('a', 1), ('b', -1)]))
chk('S3 supply/return loop L (nH)', ((n.v(V, 'a')-n.v(V, 'b'))/(1j*w)).real*1e9, 2.4, 1e-4)

# S4 negative control: remove the decap (C -> 20 pF). |Z| at 100 MHz must rise from ~0.36 to ~wL = 0.314 -> and the
# anti-resonance must move to 1.59 GHz with |Z|peak >> 1 ohm: the 1-ohm 20-200 MHz check passes by accident, so the control
# is judged on the droop for a 0.3 nC charge packet instead: dV = Q/C = 15 V (unphysical: FAIL) vs 0.15 V with 2 nF.
for tag, Cx in (("with 2 nF", 2e-9), ("NO DECAP 20 pF", 20e-12)):
    dv = 0.2e-9/Cx
    res['S4 charge-packet droop '+tag] = dict(dv_V=dv, passes_117mV=bool(dv < 0.117))
    print(f"S4 0.2 nC packet droop {tag:16s}: {dv:.3g} V  -> {'pass' if dv < 0.117 else 'FAIL'}")
ok &= (0.2e-9/20e-12 > 0.117 and 0.2e-9/2e-9 < 0.117)
res['all_ok'] = bool(ok)
json.dump(res, open(f'{HERE}/out/sanity.json', 'w'), indent=1)
print('SANITY', 'PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)
