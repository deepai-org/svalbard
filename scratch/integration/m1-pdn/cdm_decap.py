#!/usr/bin/env python3
"""CDM decap reach (PC-43 / PC-44): impedance between ring VDD and ring VSS at a pad site, bonds removed (a CDM discharge
does not see the board in its first ns), the chip's decap plan in place, high-resistance parameter set. Fitted as series R-L-C from Z at
20 and 60 MHz (R = Re Z at 60 MHz). The pads' requirement is >= 1 nF within
0.7 ohm (incl. the decap's own series R): pass if C >= 1 nF and R <= 0.7 ohm at the nominal and the
pessimistic set. L (ring + mesh loop) is reported; the pads' bench has none.
extra=x0,y0,x1,y1,nF,mos_frac adds a decap strip (8 lumps along it; MOS part tau 335 ps, rest MIM).
Usage: cdm_decap.py chip=rf|wired site=bidir[15].pad [site=...] [extra=...] [noplan=1]"""
import sys, json, numpy as np
import model as M, core as C, chipcfg as P2
args = [a.split('=', 1) for a in sys.argv[1:]]; P2.apply(); CH = P2.CHIP; D = dict(args)
sites = json.load(open(f'{M.PRJ}/analog/pads/generated/provider-sites.json'))['sites']
dec = [] if D.get('noplan') else P2.plan()
for k, v in args:
    if k == 'extra':
        x0, y0, x1, y1, nF, mf = map(float, v.split(',')); m = 8
        for i in range(m):
            x = x0+(i+0.5)*(x1-x0)/m if x1-x0 > y1-y0 else (x0+x1)/2; y = (y0+y1)/2 if x1-x0 > y1-y0 else y0+(i+0.5)*(y1-y0)/m
            c = nF*1e-9/m; dec += [(x, y, c*mf, P2.TAU_TILE/(c*mf)), (x, y, c*(1-mf), P2.TAU_MIM/(c*(1-mf)))]
M.BONDS[:] = []
FIT = tuple(float(x)*1e6 for x in D.get('fit', '20,60').split(','))   # MHz pair of the R-L-C fit
for s in [v for k, v in args if k == 'site']:
    sx, sy = sites[s]['bond_center_um']; ij = M.near(sx, sy); row = []
    for pk in ('nom', 'pess'):
        n, info = M.build(P2.pset(pk), decap=dec)
        rhs = n.inj([(M.vn(*ij), 1.0), (M.gn(*ij), -1.0)])[:, None]
        zs = {}
        for f in FIT:
            V = n.solve(2*np.pi*f, rhs)[:, 0]; zs[f] = V[n.idx[M.vn(*ij)]]-V[n.idx[M.gn(*ij)]]
        (w1, z1), (w2, z2) = [(2*np.pi*f, z) for f, z in zs.items()]
        # Im Z = w L - 1/(w C): two equations, two unknowns
        A = np.array([[w1, -1/w1], [w2, -1/w2]]); L, invC = np.linalg.solve(A, [z1.imag, z2.imag])
        row.append((pk, z2.real, 1/invC, L))
    ok = all(r <= 0.7 and c >= 1e-9 for _, r, c, L in row)
    print(f"{CH} {s} ({sx:.0f}, {sy:.0f}): " + '; '.join(f"{pk}: series R {r:.2f} ohm, C {c*1e9:.2f} nF, L {L*1e9:.2f} nH" for pk, r, c, L in row) + f" -> {'PASS' if ok else 'MISS'} (>= 1 nF within 0.7 ohm)")
