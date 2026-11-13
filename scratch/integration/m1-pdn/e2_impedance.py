#!/usr/bin/env python3
"""E2 (M1 + M4): impedance seen by the digital macro and transfer impedance to the victim taps vs frequency.
Anti-resonances (frequency, |Z|, Q) against 78.125 / 156.25 / 312.5 MHz, the wired ring band 600-810 MHz and 2.4 GHz,
for each decap plan and the opt / nom / pess parameter sets; then a continuous decap sweep 0-8 nF."""
import json, numpy as np
import model as M, core as C
F = np.unique(np.concatenate([np.logspace(5.5, 9.8, 260), [78.125e6, 156.25e6, 312.5e6, 625e6, 810e6, 2.4e9]]))
MARK = [78.125e6, 156.25e6, 312.5e6, 625e6, 810e6, 2.4e9]
PLANS = {
 'none (intrinsic only, v6 as placed)': lambda: C.decap_plan('none'),
 '1 nF MOS tiles, spread': lambda: C.decap_plan('uniform', 1.0),
 '3 nF MOS tiles, spread': lambda: C.decap_plan('uniform', 3.0),
 '3 nF MOS in/at the macro': lambda: C.decap_plan('digital', 3.0),
 '3 nF MIM spread (tau 5 ps)': lambda: C.decap_plan('mim_uniform', 3.0),
 'AP4-9 low: 1.7 nF MIM over blocks + 0.45 nF fill': lambda: C.decap_plan('ap49', frac=0.30, dig_fill_nF=0.45),
 'AP4-9 high: 5.7 nF MIM over blocks + 1.0 nF fill': lambda: C.decap_plan('ap49', frac=1.0, dig_fill_nF=1.0),
 'AP4-9 low + 1.5 nF MOS in the macro': lambda: C.decap_plan('ap49', frac=0.30, dig_fill_nF=1.95),
}
def peaks(f, z):
    out = []
    for k in range(1, len(f)-1):
        if z[k] > z[k-1] and z[k] >= z[k+1] and 5e6 < f[k] < 5e9:
            h = z[k]/np.sqrt(2); a = k
            while a > 0 and z[a] > h: a -= 1
            b = k
            while b < len(f)-1 and z[b] > h: b += 1
            out.append(dict(f_MHz=round(f[k]/1e6, 1), Z=round(float(z[k]), 2), Q=round(float(f[k]/(f[b]-f[a])), 1)))
    return sorted(out, key=lambda d: -d['Z'])[:3]
res = {}
for plan, mk in PLANS.items():
    for s in ('opt', 'nom', 'pess'):
        for strip in ((True, False) if plan.startswith(('none', '3 nF MOS tiles', 'AP4-9 low: ')) else (True,)):
            p = M.pset(s); n, info, ports, vict = C.full(p, decap=mk(), strip_caps=strip)
            names, Zd, Zg = C.transfer(n, info, ports, vict, F)
            zs = abs(Zd[:, names.index('dig'), C.PORTS.index('dig')])
            r = dict(self_peaks=peaks(F, zs), self_at={f'{m/1e6:g}': round(float(zs[np.searchsorted(F, m)]), 3) for m in MARK},
                     max_20_200=round(float(zs[(F >= 20e6) & (F <= 200e6)].max()), 2), max_50_400=round(float(zs[(F >= 50e6) & (F <= 400e6)].max()), 2),
                     to_victims={v: {f'{m/1e6:g}': round(float(abs(Zd[np.searchsorted(F, m), names.index(v), C.PORTS.index('dig')])), 3) for m in MARK} for v in names})
            res[f"{plan}|{s}|{'strip' if strip else 'nostrip'}"] = r
            print(f"{plan[:48]:48s} {s:4s} {'strip' if strip else 'NOstrip':7s} pk {r['self_peaks'][:2]}  |Z| 78/156/312/625/2400: "
                  f"{r['self_at']['78.125']:.2f} {r['self_at']['156.25']:.2f} {r['self_at']['312.5']:.2f} {r['self_at']['625']:.2f} {r['self_at']['2400']:.2f}  max20-200 {r['max_20_200']} max50-400 {r['max_50_400']}")
# continuous decap sweep (MOS, in/at the macro and spread 50/50), three parameter sets: where does the anti-resonance sit?
print('--- sweep of total added decap (half in the macro, half spread; MOS ESR): anti-resonance and |Z| at the clock lines')
sw = {}
for c in (0, 0.25, 0.5, 1, 1.5, 2, 3, 4, 6, 8):
    for s in ('opt', 'nom', 'pess'):
        p = M.pset(s); d = C.decap_plan('uniform', c/2)+C.decap_plan('digital', c/2)
        n, info, ports, vict = C.full(p, decap=d); names, Zd, Zg = C.transfer(n, info, ports, vict, F)
        zs = abs(Zd[:, names.index('dig'), C.PORTS.index('dig')]); pk = peaks(F, zs)
        sw[f'{c}|{s}'] = dict(peaks=pk, at={f'{m/1e6:g}': round(float(zs[np.searchsorted(F, m)]), 3) for m in MARK})
    print(f"  +{c:4.2f} nF: " + '  '.join(f"{s}: f_ar {sw[f'{c}|{s}']['peaks'][0]['f_MHz']:6.1f} MHz {sw[f'{c}|{s}']['peaks'][0]['Z']:5.2f} ohm Q {sw[f'{c}|{s}']['peaks'][0]['Q']:4.1f} |Z78| {sw[f'{c}|{s}']['at']['78.125']:.2f} |Z156| {sw[f'{c}|{s}']['at']['156.25']:.2f}" for s in ('opt', 'nom', 'pess')))
json.dump(dict(plans=res, sweep=sw), open('out/e2_impedance.json', 'w'), indent=0)
