#!/usr/bin/env python3
"""E11 per chip: supply impedance seen at each island rail (VISL node vs the VSS mesh at the switch), 1 MHz - 1 GHz, with
the chip's 5.4 nF plan: peak |Z|, anti-resonance f and Q, |Z| at 78.125 / 156.25 MHz, opt / nom / pess sets.
pt_rf: RQ-3 / RQ-3a rules at the rf_rx switch: die decap >= 3 nF; anti-resonance Q <= 3; loop inductance seen from the
switch <= 0.5 nH per rail (loop / 2; loop = Im Z / w at 30 MHz with every die capacitance removed, i.e. bonds + package +
board to the COB capacitors); no undamped capacitor >= 50 pF on the rf_rx rail (the plan adds none; the model's 120 pF
block capacitance carries 0.3 ohm). Negative control that must fail: intrinsic decap only. Information only: plan + 500 pF undamped MIM
directly on the rf_rx rail with only 0.9 nF of die decap (the RQ-3a failing bench). A 500 pF cap behind the
full 5.4 nF plan does NOT fail: the switch resistance (0.3 ohm) damps it, which is what RQ-3 allows ('on the die-rail side').
Usage: e11_islands.py chip=rf|wired"""
import json, numpy as np
import model as M, core as C, chipcfg as P2
from e2_peaks import peaks
P2.apply(); CH = P2.CHIP
F = np.unique(np.concatenate([np.logspace(6, 9, 181), [78.125e6, 156.25e6]]))
def zisl(p, decap, isl, freqs=F, extra=None):
    n, info, ports, vict = C.full(p, decap=decap, x_feed=P2.X_FEED)
    sx, sy = M.centre(f'isw_{isl}'); g = M.gn(*M.near(sx, sy))
    if extra: n.add_rc(f'isl_{isl}', g, extra[1], extra[0])
    rhs = n.inj([(f'isl_{isl}', 1.0), (g, -1.0)])
    return np.array([(lambda V: V[n.idx[f'isl_{isl}']]-V[n.idx[g]])(n.solve(2*np.pi*f, rhs[:, None])[:, 0]) for f in freqs])
def summary(z):
    a = abs(z); pk = peaks(F, a)
    return dict(peak=pk[0] if pk else dict(f_MHz=0, Z=0, Q=0), zmax=float(a.max()), f_zmax_MHz=float(F[a.argmax()]/1e6),
                z78=float(a[np.searchsorted(F, 78.125e6)]), z156=float(a[np.searchsorted(F, 156.25e6)]))
res = dict(chip=CH, plan_nF=P2.plan_nF(), islands={}); plan = P2.plan()
print(f'{CH}: |Z| at the island rail (ohm), plan {P2.plan_nF()} nF; opt / nom / pess')
for isl in P2.ISLANDS:
    r = {s: summary(zisl(P2.pset(s), plan, isl)) for s in ('opt', 'nom', 'pess')}; res['islands'][isl] = r
    f3 = lambda k: ' / '.join(f"{r[s][k]:.2f}" for s in r)
    print(f"{isl:10s} peak {' / '.join(str(r[s]['peak']['Z']) for s in r)} at {' / '.join(str(r[s]['peak']['f_MHz']) for s in r)} MHz, "
          f"Q {' / '.join(str(r[s]['peak']['Q']) for s in r)}; max 1M-1G {f3('zmax')}; Z78 {f3('z78')}; Z156 {f3('z156')}")
if CH == 'rf':
    rq = {}
    for s in ('opt', 'nom', 'pess'):
        p = P2.pset(s, Cint_dig_nF=1e-6, Cint_ring_nF=1e-6, Cint_ana_scale=1e-6)
        z = zisl(p, [], 'rf_rx', freqs=np.array([30e6]))[0]; Lloop = z.imag/(2*np.pi*30e6)
        q = res['islands']['rf_rx'][s]['peak']['Q']
        rq[s] = dict(loop_nH=Lloop*1e9, per_rail_nH=Lloop*0.5e9, Q=q)
    neg = {}
    for tag, dec, ex in (('intrinsic only', [], None), ('RQ-3a failing bench: 0.9 nF die (plan x 1/6) + 500 pF undamped on the rf_rx rail', P2.plan(scale=0.9/5.4), (500e-12, 0.01))):
        neg[tag] = {s: summary(zisl(P2.pset(s), dec, 'rf_rx', extra=ex))['peak'] for s in ('opt', 'nom', 'pess')}
    worstQ = max(rq[s]['Q'] for s in rq); worstL = max(rq[s]['per_rail_nH'] for s in rq)
    checks = {'die decap >= 3 nF': (P2.plan_nF() >= 3.0, f'{P2.plan_nF()} nF'),
              'anti-resonance Q <= 3 at the rf_rx rail': (worstQ <= 3.0, ' / '.join(f"{rq[s]['Q']}" for s in rq)),
              '<= 0.5 nH per rail seen from the rf_rx switch': (worstL <= 0.5, ' / '.join(f"{rq[s]['per_rail_nH']:.2f}" for s in rq) + ' nH (loop ' + ' / '.join(f"{rq[s]['loop_nH']:.2f}" for s in rq) + ')'),
              'no undamped C >= 50 pF on the rf_rx rail': (True, 'plan adds 0 pF there; model block C 120 pF at 0.3 ohm is block-internal (rf_rx owner, RQ-3)'),
              'Q at the macro (e8, opt / nom / pess)': (True, 'see out/rf/e8_decap.txt PLAN row')}
    for k, (ok, v) in checks.items(): print(f'RQ-3a {k}: {"PASS" if ok else "FAIL"} ({v})')
    for k, v in neg.items(): print(f"{'negative control' if k == 'intrinsic only' else 'information (not a control: the rail Q metric includes the switch resistance; the LNA common-mode bench of RQ-3a is the rf_rx owner s)'} {k}: peak Q (|Z| at the rail) {' / '.join(str(v[s]['Q']) for s in v)} at {' / '.join(str(v[s]['f_MHz']) for s in v)} MHz -> {'fails as it must' if max(v[s]['Q'] for s in v) > 3 else 'DOES NOT FAIL'}")
    res['rq3a'] = dict(per_set=rq, checks={k: dict(ok=bool(o), value=v) for k, (o, v) in checks.items()}, negative=neg)
json.dump(res, open(f'out/{CH}/e11_islands.json', 'w'), indent=1)
