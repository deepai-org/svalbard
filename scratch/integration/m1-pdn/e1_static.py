#!/usr/bin/env python3
"""E1: static IR at every block tap, every budget mode, three load levels, three parameter sets.
Budget: source 3.267 V (3.3 V - 1 %) minus the 3.15 V die floor = 117 mV total (PWR-DROP), tap to tap (VDD drop + VSS rise)."""
import json, numpy as np
import model as M, core as C, loads as LD
res = {}; BUD = 117.0
for s in ('opt', 'nom', 'pess'):
    p = M.pset(s); n, info, ports, vict = C.full(p, x_feed=0.0)
    for case in LD.CASES:
        for lv in ('alloc', 'evid', 'evid+'):
            d = C.dc(n, info, case, lv)
            res[f'{s}|{case}|{lv}'] = d
json.dump(res, open('out/e1_static.json', 'w'), indent=0)
def drop(v): return (3.267-v['rail'])*1e3
print('--- ring-level (board + bonds + ring), total current, max bond current; nominal set')
for case in LD.CASES:
    for lv in ('alloc', 'evid+'):
        d = res[f'nom|{case}|{lv}']
        sb = {k: v for k, v in d['bond_mA'].items() if k in [x[0] for x in M.VDD_PADS]}; gb = {k: v for k, v in d['bond_mA'].items() if k not in sb}
        print(f"{case:26s} {lv:6s} I {d['total_mA']:6.1f} mA  ring drop {1e3*(3.267-d['ring_rail_min']):5.1f}..{1e3*(3.267-d['ring_rail_max']):5.1f} mV  "
              f"max VDD bond {max(sb.values()):4.0f} mA (pad {max(sb, key=sb.get)})  max GND bond {max(gb.values()):4.0f} mA (pad {max(gb, key=gb.get)})")
print('--- worst block taps (total drop mV = VDD drop + VSS rise; budget 117): opt / nom / pess, load evid+ and alloc')
tab = {}
for k, d in res.items():
    s, case, lv = k.split('|')
    for b, v in d['blocks'].items():
        if b.startswith('tap:') or v['mA'] < 0.5: continue
        key = (b, lv, s)
        if key not in tab or drop(v) > tab[key][0]: tab[key] = (drop(v), case, v)
rows = sorted({b for (b, lv, s) in tab if all((b, l2, s2) in tab for l2 in ('evid+', 'alloc') for s2 in ('opt', 'nom', 'pess'))}, key=lambda b: -tab[(b, 'evid+', 'nom')][0])
summary = {}
for b in rows:
    o, nm, pe = (tab[(b, 'evid+', s)] for s in ('opt', 'nom', 'pess')); al = tab[(b, 'alloc', 'nom')]
    v = nm[2]
    br = (f"pre-sw {v.get('pre_switch_mV', v.get('vdd_drop_mV', 0.0)):5.1f} sw {v.get('switch_mV', 0):5.1f} strap {v.get('strap_mV', 0):6.1f} vss {v['vss_mV']:5.1f}")
    summary[b] = dict(island=v['island'], mA=v['mA'], worst_case=nm[1], drop_mV=dict(opt=o[0], nom=nm[0], pess=pe[0], alloc_nom=al[0]),
                      nom_breakdown=dict(pre_switch=v.get('pre_switch_mV', v.get('vdd_drop_mV', 0.0)), switch=v.get('switch_mV', 0), strap=v.get('strap_mV', 0), vss=v['vss_mV']))
    print(f"{b:12s} {str(v['island']):6s} {v['mA']:6.1f} mA  {o[0]:6.1f} / {nm[0]:6.1f} / {pe[0]:6.1f}  (alloc nom {al[0]:6.1f})  [{nm[1]}] nom: {br} {'FAIL' if nm[0] > BUD else ''}")
# island totals vs switch design current
print('--- island currents (mA) vs switch design current')
isl_tot = {}
for case in LD.CASES:
    for lv in ('alloc', 'evid+'):
        out, idig, ihost, m, rdir = LD.dc_loads(case, lv)
        for isl in M.ISW:
            t = sum(x[3] for x in out if x[2] == isl); k = (isl, lv)
            if k not in isl_tot or t > isl_tot[k][0]: isl_tot[k] = (t, case)
des = dict(wired=80, rf=55, pll=60, conv=30, debug=40)
for isl in M.ISW:
    print(f"{isl:6s} design {des[isl]} mA; alloc max {isl_tot[(isl, 'alloc')][0]:.1f} ({isl_tot[(isl, 'alloc')][1]}); evid+ max {isl_tot[(isl, 'evid+')][0]:.1f} ({isl_tot[(isl, 'evid+')][1]})")
# what the interior needs: blocks at their switch (no strap), sweep grid coverage, nominal otherwise
print('--- requirement sweep: worst raw-mesh drop to any island switch / the macro vs Metal5 coverage per net (nominal ring/bonds, evid+)')
req = {}
for cov in (0.02, 0.04, 0.08, 0.15, 0.25, 0.4):
    p = M.pset('nom'); p['grid_cov'] = cov; p['dig_cov'] = max(cov, 0.12)
    n, info, ports, vict = C.full(p)
    w = 0; wd = 0
    for case in LD.CASES:
        d = C.dc(n, info, case, 'evid+')
        for b, v in d['blocks'].items():
            if 'pre_switch_mV' in v: w = max(w, v['pre_switch_mV']+v['vss_mV'])
        wd = max(wd, drop(d['blocks']['digital']))
    req[cov] = dict(worst_pre_switch_plus_vss_mV=w, digital_mV=wd)
    print(f"  coverage {cov:4.2f} (sheet {p['Rs_m5']/cov:5.2f} ohm/sq): worst source->switch + VSS rise {w:6.1f} mV, digital macro {wd:6.1f} mV")
json.dump(dict(summary=summary, island_totals={f'{k[0]}|{k[1]}': v for k, v in isl_tot.items()}, coverage_req=req), open('out/e1_summary.json', 'w'), indent=1)
