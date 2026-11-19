#!/usr/bin/env python3
"""E8 per chip: the 5.4 nF decap plan as the chip's die fit placed it, its variants and the negative controls. Case: the
chip's heaviest digital/D2H case (pt_wired W: D2H at 156.25 MHz; pt_rf DXa: D2H at div2, 78.125 MHz). Per plan:
steady-state pk-pk at the macro from the macro's own charge packets (opt 24.5 mA / 3 ns, nom PWR-DIG / 2.4 ns, pess
chip-scaled worst / 1.6 ns on matched network sets, and pess source x worst network), the same with the macro at the
unscaled 81.79 mA, D2H at the macro and core_bias, the impedance the macro sees (anti-resonance f, |Z|, Q), and the
two-phase table (PD2-6) at the PWR-DIG current with the pessimistic pulse on the worst network.
Hand check: pk-pk ~ Q (1 - tw/T) / C when the anti-resonance is below the clock.
Usage: e8_decap.py chip=rf|wired"""
import sys, json, numpy as np
import model as M, core as C, loads as LD, chipcfg as P2
from e2_peaks import peaks
P2.apply(); CH = P2.CHIP
CASE = {'rf': 'DXa', 'wired': 'W'}[CH]
FH = np.array([78.125e6*k for k in range(1, 41)])
FZ = np.unique(np.concatenate([np.logspace(6.5, 9.3, 160), [78.125e6, 156.25e6, 312.5e6]]))
out, idig, ihost, m, rdir = LD.dc_loads(CASE, 'pd2w')
IREQ = P2.DIG['req_rf' if rdir else 'req_wired_usb']; I818 = P2.DIG['worst_unscaled']
def synth(lines, Zc, vi):
    f0 = min(l[2] for l in lines); t = np.arange(1024)/1024/f0; w = np.zeros(1024)
    for (ag, port, f, a, ae) in lines:
        k = int(np.searchsorted(FH, f)); w += (Zc[k, vi, C.PORTS.index(port)]*a*np.exp(2j*np.pi*f*t)).real
    return float((w.max()-w.min())*1e3)
def evaluate(decap):
    r = {}; Z = {}
    for s in ('opt', 'nom', 'pess'):
        n, info, ports, vict = C.full(P2.pset(s), decap=decap, x_feed=P2.X_FEED)
        names, Zc, Zg = C.transfer(n, info, ports, vict, FH); Z[s] = (names, Zc)
        L = LD.lines(CASE, idig, ihost, m, rdir, s)
        dg = [l for l in L if l[0] == 'digital']; dh = [l for l in L if l[0] == 'd2h']
        r[s] = dict(dig={v: synth(dg, Zc, names.index(v)) for v in ('dig', 'core_bias')}, d2h={v: synth(dh, Zc, names.index(v)) for v in ('dig', 'core_bias', 'host')})
        nz, Zz, _ = C.transfer(n, info, ports, vict, FZ); zs = abs(Zz[:, nz.index('dig'), C.PORTS.index('dig')])
        pk = peaks(FZ, zs)
        r[s]['z'] = dict(peak=pk[0] if pk else dict(f_MHz=0, Z=0, Q=0), z78=float(zs[np.searchsorted(FZ, 78.125e6)]), z156=float(zs[np.searchsorted(FZ, 156.25e6)]),
                         max_20_200=float(zs[(FZ >= 20e6) & (FZ <= 200e6)].max()))
    dg = [l for l in LD.lines(CASE, idig, ihost, m, rdir, 'pess') if l[0] == 'digital']
    worst = lambda L, v='dig': max(synth(L, Z[s][1], Z[s][0].index(v)) for s in Z)
    r['pess_worstnet'] = worst(dg)
    r['dig818_pess_worstnet'] = worst([(a, p, f, x*I818/idig, y) for (a, p, f, x, y) in dg])
    r['two_phase'] = {}
    for e in (1.0, 0.2, 0.15, 0.1, 0.0):
        L2 = [(a, p, f, x*IREQ/idig*(e if round(f/78.125e6) % 2 else 1.0), y) for (a, p, f, x, y) in dg]
        r['two_phase'][str(e)] = dict(macro=worst(L2), core_bias=worst(L2, 'core_bias'))
    return r
def show(tag, r):
    z = r['pess']['z']; pk = z['peak']; t = r['two_phase']
    print(f"{tag:44s} macro pp {r['opt']['dig']['dig']:4.0f}/{r['nom']['dig']['dig']:4.0f}/{r['pess']['dig']['dig']:4.0f} (pess x worst net {r['pess_worstnet']:4.0f}; at 81.8 mA {r['dig818_pess_worstnet']:4.0f})"
          f" | bias {r['opt']['dig']['core_bias']:3.0f}/{r['nom']['dig']['core_bias']:3.0f}/{r['pess']['dig']['core_bias']:3.0f}"
          f" | d2h@macro {r['opt']['d2h']['dig']:3.0f}/{r['nom']['d2h']['dig']:3.0f}/{r['pess']['d2h']['dig']:3.0f} d2h@bias {r['opt']['d2h']['core_bias']:3.0f}/{r['nom']['d2h']['core_bias']:3.0f}/{r['pess']['d2h']['core_bias']:3.0f}"
          f" | f_ar {r['opt']['z']['peak']['f_MHz']:.0f}/{r['nom']['z']['peak']['f_MHz']:.0f}/{pk['f_MHz']:.0f} MHz Zpk {r['opt']['z']['peak']['Z']:.2f}/{r['nom']['z']['peak']['Z']:.2f}/{pk['Z']:.2f} Q {r['opt']['z']['peak']['Q']}/{r['nom']['z']['peak']['Q']}/{pk['Q']}"
          f" | Z78 {r['nom']['z']['z78']:.2f}/{z['z78']:.2f} Z156 {r['nom']['z']['z156']:.2f}/{z['z156']:.2f}")
    print(' '*44 + f" {IREQ:.0f} mA (PWR-DIG), pess pulse, worst network, macro pk-pk single-phase / 60-40 / residual 0.15 / 0.1 / balanced: "
          + ' / '.join(f"{t[e]['macro']:.0f}" for e in t) + '  (core_bias ' + ' / '.join(f"{t[e]['core_bias']:.0f}" for e in t) + ')')
if __name__ == '__main__':
    print(f'{CH}: case {CASE}, digital {P2.DIG["nominal"]} / {P2.DIG["worst"]} mA area-scaled (81.79 unscaled), PWR-DIG {IREQ} mA; decap as built '
          + ', '.join(f'{k} {v}' for k, v in P2.DECAP.items() if k.endswith('nF')))
    PLANS = {'0 intrinsic only (negative control)': [],
             'A rows + bond sites only (negative control)': P2.plan(mim=0, bank=0, tiles=0),
             'PLAN 5.4 nF as packed': P2.plan(),
             'PLAN every part x 0.7': P2.plan(scale=0.7),
             'PLAN every part x 1.3': P2.plan(scale=1.3),
             'PLAN without the grid MIM': P2.plan(mim=0),
             'PLAN without the tiles': P2.plan(tiles=0),
             '8 nF MOS inside the macro (reference)': P2.lumps('macro', 8.0, P2.TAU_TILE)}
    res = {}
    for k, d in PLANS.items():
        res[k] = evaluate(d); show(k, res[k])
    ok = res['0 intrinsic only (negative control)']['two_phase']['0.15']['macro'] > 150 and res['A rows + bond sites only (negative control)']['two_phase']['0.15']['macro'] > 150
    print(f'E8 {CH} negative controls', 'fail as they must' if ok else 'DO NOT FAIL (bench broken)')
    json.dump(dict(chip=CH, case=CASE, plans=res), open(f'out/{CH}/e8_decap.json', 'w'), indent=0)
