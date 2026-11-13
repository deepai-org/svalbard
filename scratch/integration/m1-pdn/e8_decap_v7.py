#!/usr/bin/env python3
"""E8 (PD2): decap plans on the v7 grid requirement. Wired mode (the worst digital and D2H case). For each plan:
steady-state pk-pk at the macro from the macro's own charge packets (opt 24.5 mA / 3 ns, nom 60 mA / 2.4 ns, pess
81.8 mA / 1.6 ns; matched network sets, and pess source x worst set), from D2H, the same at core_bias, and the impedance
seen by the macro (anti-resonance frequency, |Z|, Q, |Z| at 78.125 / 156.25 MHz, max over 20-200 MHz).
Hand check: pk-pk ~ Q (1 - tw/T) / C when the anti-resonance is below the clock."""
import sys, json, numpy as np
import model as M, core as C, loads as LD, pd2cfg as P2
from e2_peaks import peaks
P2.apply()
FH = np.array([78.125e6*k for k in range(1, 41)])
FZ = np.unique(np.concatenate([np.logspace(6.5, 9.3, 160), [78.125e6, 156.25e6, 312.5e6]]))
out, idig, ihost, m, rdir = LD.dc_loads('W', 'pd2w')
def synth(lines, Zc, vi):
    f0 = min(l[2] for l in lines); t = np.arange(1024)/1024/f0; w = np.zeros(1024)
    for (ag, port, f, a, ae) in lines:
        k = int(np.searchsorted(FH, f)); w += (Zc[k, vi, C.PORTS.index(port)]*a*np.exp(2j*np.pi*f*t)).real
    return float((w.max()-w.min())*1e3)
def evaluate(decap, **kw):
    r = {}; Z = {}
    for s in ('opt', 'nom', 'pess'):
        n, info, ports, vict = C.full(P2.pset(s), decap=decap, x_feed=P2.X_FEED, **kw)
        names, Zc, Zg = C.transfer(n, info, ports, vict, FH); Z[s] = (names, Zc)
        L = LD.lines('wired_onchip_pll', idig, ihost, m, rdir, s)
        dg = [l for l in L if l[0] == 'digital']; dh = [l for l in L if l[0] == 'd2h']
        r[s] = dict(dig={v: synth(dg, Zc, names.index(v)) for v in ('dig', 'core_bias', 'qvco', 'refbuf', 'slicer')},
                    d2h={v: synth(dh, Zc, names.index(v)) for v in ('dig', 'core_bias', 'host')})
        nz, Zz, _ = C.transfer(n, info, ports, vict, FZ); zs = abs(Zz[:, nz.index('dig'), C.PORTS.index('dig')])
        pk = peaks(FZ, zs)
        r[s]['z'] = dict(peak=pk[0] if pk else None, z78=float(zs[np.searchsorted(FZ, 78.125e6)]), z156=float(zs[np.searchsorted(FZ, 156.25e6)]),
                         max_20_200=float(zs[(FZ >= 20e6) & (FZ <= 200e6)].max()), max_50_400=float(zs[(FZ >= 50e6) & (FZ <= 400e6)].max()))
    # pess source on the worst of the three networks (resonance position is not monotonic in the parameters)
    L = LD.lines('wired_onchip_pll', idig, ihost, m, rdir, 'pess'); dg = [l for l in L if l[0] == 'digital']
    r['pess_worstnet_dig_at_macro'] = max(synth(dg, Z[s][1], Z[s][0].index('dig')) for s in Z)
    # digital at the PWR-DIG requirement (60 mA) with the pessimistic pulse (1.6 ns) on the worst network
    dg60 = [(a, p, f, x*60.0/idig, y*60.0/idig) for (a, p, f, x, y) in dg]
    r['req60_pesspulse_worstnet_dig_at_macro'] = max(synth(dg60, Z[s][1], Z[s][0].index('dig')) for s in Z)
    # two-phase launch (PD2-6): odd harmonics of the 78.125 MHz train scaled by the residual imbalance (0.2 = 60/40 split,
    # 0 = balanced); 60 mA, nominal (2.4 ns) and pessimistic (1.6 ns) pulse, worst of the three networks; macro and core_bias
    Ln = [l for l in LD.lines('wired_onchip_pll', idig, ihost, m, rdir, 'nom') if l[0] == 'digital']
    r['two_phase'] = {}
    for lab, src, sc in (('nompulse', Ln, 1.0), ('pesspulse', dg, 60.0/idig)):
        for e in (1.0, 0.2, 0.15, 0.1, 0.0):
            L2 = [(a, p, f, x*sc*(e if round(f/78.125e6) % 2 else 1.0), y) for (a, p, f, x, y) in src]
            r['two_phase'][f'{lab}|{e}'] = dict(macro=max(synth(L2, Z[s][1], Z[s][0].index('dig')) for s in Z),
                                                core_bias=max(synth(L2, Z[s][1], Z[s][0].index('core_bias')) for s in Z))
    return r
def show(tag, r):
    z = r['pess']['z']; pk = z['peak'] or dict(f_MHz=0, Z=0, Q=0)
    print(f"{tag:46s} macro pp {r['opt']['dig']['dig']:4.0f}/{r['nom']['dig']['dig']:4.0f}/{r['pess']['dig']['dig']:4.0f} (pess x worst net {r['pess_worstnet_dig_at_macro']:4.0f}; 60 mA pess pulse {r['req60_pesspulse_worstnet_dig_at_macro']:4.0f})"
          f" | bias {r['opt']['dig']['core_bias']:3.0f}/{r['nom']['dig']['core_bias']:3.0f}/{r['pess']['dig']['core_bias']:3.0f}"
          f" | d2h@macro {r['opt']['d2h']['dig']:3.0f}/{r['nom']['d2h']['dig']:3.0f}/{r['pess']['d2h']['dig']:3.0f}"
          f" | f_ar {r['opt']['z']['peak']['f_MHz']:.0f}/{r['nom']['z']['peak']['f_MHz']:.0f}/{pk['f_MHz']:.0f} MHz Zpk {r['opt']['z']['peak']['Z']:.2f}/{r['nom']['z']['peak']['Z']:.2f}/{pk['Z']:.2f} Q {pk['Q']}"
          f" | Z78 {r['nom']['z']['z78']:.2f}/{z['z78']:.2f} Z156 {r['nom']['z']['z156']:.2f}/{z['z156']:.2f} max20-200 {r['nom']['z']['max_20_200']:.2f}/{z['max_20_200']:.2f}")
    t = r['two_phase']
    print(' '*46 + f" 60 mA on the worst network, macro pk-pk single-phase / 60-40 / residual 0.15 / balanced: nominal pulse {t['nompulse|1.0']['macro']:.0f} / {t['nompulse|0.2']['macro']:.0f} / {t['nompulse|0.15']['macro']:.0f} / {t['nompulse|0.0']['macro']:.0f}"
          f"; pessimistic pulse {t['pesspulse|1.0']['macro']:.0f} / {t['pesspulse|0.2']['macro']:.0f} / {t['pesspulse|0.15']['macro']:.0f} / {t['pesspulse|0.0']['macro']:.0f} mV"
          f" (core_bias {t['pesspulse|1.0']['core_bias']:.0f} / {t['pesspulse|0.2']['core_bias']:.0f} / {t['pesspulse|0.15']['core_bias']:.0f} / {t['pesspulse|0.0']['core_bias']:.0f})")
if __name__ == '__main__':
    lm = P2.lumps; T, R, Mm = P2.TAU_TILE, P2.TAU_ROW, P2.TAU_MIM
    PLANS = {'0 intrinsic only (negative control)': [],
             'A rows 0.45 + bond sites 0.45 (no core area)': P2.plan(mim=0, tiles=0),
             'PLAN: A + 3.0 MIM in grid + 1.5 tiles at macro': P2.plan(),
             'PLAN at the low capacitance corner (MIM, tiles x 0.88; row fill 0.30)': P2.plan(rows=0.30, sites=0.40, mim=2.64, tiles=1.32),
             'PLAN low: every part at 0.7x': P2.plan(rows=0.315, sites=0.315, mim=2.1, tiles=1.05),
             'PLAN high: every part at 1.3x': P2.plan(rows=0.585, sites=0.585, mim=3.9, tiles=1.95),
             'PLAN with MIM 2.0 (minimum)': P2.plan(mim=2.0), 'PLAN with MIM 5.0': P2.plan(mim=5.0),
             'PLAN with tiles 0.75': P2.plan(tiles=0.75), 'PLAN with tiles 2.0': P2.plan(tiles=2.0), 'PLAN with tiles 3.0': P2.plan(tiles=3.0),
             'PLAN without the bond-site tiles': P2.plan(sites=0), 'PLAN without the row fill': P2.plan(rows=0)}
    for x in (4, 6, 8):
        PLANS[f'{x} nF MOS inside the macro (reference, not buildable)'] = lm('macro', x, T)
    sel = sys.argv[1:] or list(PLANS)
    res = {}
    for k in PLANS:
        if not any(s in k for s in sel) and sys.argv[1:]: continue
        res[k] = evaluate(PLANS[k]); show(k, res[k])
    json.dump(res, open('out/e8_decap_v7.json', 'w'), indent=0)
