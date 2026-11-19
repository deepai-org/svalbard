#!/usr/bin/env python3
"""E7 per chip: static IR at every tap with the reconciled currents, the chip's islands, switches and bonds, and the grid
requirement. Budget 117 mV (3.267 V source - 3.15 V die floor), tap to tap. opt = low-impedance set + nominal currents;
nom = nominal set + nominal currents; pess = high-impedance set + worst in-window currents with the digital macro at its
chip-scaled worst (chipcfg.dc_loads pd2w); 'pess 81.8' = the same with the macro at the unscaled 81.79 mA (pd2u).
Bond currents against the 125 mA per supply cell rating (85 C, spec/power-delivery.md bonds section).
Usage: e7_static.py chip=rf|wired [cov_m5=0.15] [cov_m4=0.15] [strap_mv=15] [tag=base]"""
import sys, json
import model as M, core as C, loads as LD, chipcfg as P2
opt = dict(a.split('=') for a in sys.argv[1:])
P2.apply(); CH = P2.CHIP
grid = dict(cov_m5=float(opt.get('cov_m5', P2.GRID['cov_m5'])), cov_m4=float(opt.get('cov_m4', P2.GRID['cov_m4'])))
strap = float(opt.get('strap_mv', P2.STRAP_MV)); tag = opt.get('tag', 'base')
LEVEL = {'opt': 'pd2n', 'nom': 'pd2n', 'pess': 'pd2w', 'pess818': 'pd2u'}; NET = {'pess818': 'pess'}
BUD = 117.0; CELL_MA = 125.0; worst = {}; bond = {}; ring = {}; bonds_all = {}
dec = P2.plan()
for s in LEVEL:
    p = P2.pset(NET.get(s, s), grid, strap); n, info, ports, vict = C.full(p, decap=dec, x_feed=P2.X_FEED)
    for case in P2.CASES:
        d = C.dc(n, info, case, LEVEL[s], x_feed=P2.X_FEED)
        for b, v in d['blocks'].items():
            if b.startswith('tap:') or v['mA'] < 0.3: continue
            t = (3.267-v['rail'])*1e3
            if t > worst.get((b, s), (0,))[0]: worst[(b, s)] = (t, case, v)
        vp = {x['ring'] for x in M.BONDS if x['net'] == 'VDD'}
        for k, v in d['bond_mA'].items():
            if v > bonds_all.get((k, s), (0,))[0]: bonds_all[(k, s)] = (v, case)
        sb = max((v, k) for k, v in d['bond_mA'].items() if k in vp); gb = max((v, k) for k, v in d['bond_mA'].items() if k not in vp)
        if sb[0] > bond.get(('v', s), (0,))[0]: bond[('v', s)] = (*sb, case)
        if gb[0] > bond.get(('g', s), (0,))[0]: bond[('g', s)] = (*gb, case)
        ring[s] = max(ring.get(s, 0), 1e3*(3.267-d['ring_rail_min']))
site = {x['ring']: (x['site'], x['net'], x['inst']) for x in M.BONDS}
print(f'{CH}: grid per net Metal5 {grid["cov_m5"]:.2f}, Metal4 {grid["cov_m4"]:.2f}; strap budget {strap} mV; decap plan {P2.plan_nF()} nF; '
      f'digital {P2.DIG["nominal"]} / {P2.DIG["worst"]} mA (area-scaled), 81.79 unscaled in the last column')
print('tap           island     mA(worst)  drop opt / nom / pess / pess-81.8 (mV)   pess split: to-switch / switch / strap / vss   case, Metal5 strap width for 15 mV over the packed distance')
rows = sorted({b for (b, s) in worst}, key=lambda b: -worst.get((b, 'pess'), (0,))[0]); fails = []; summ = {}
for b in rows:
    o, nm, pe, pu = (worst.get((b, s), (float('nan'), '', {})) for s in LEVEL); v = pe[2]
    br = f"{v.get('pre_switch_mV', v.get('vdd_drop_mV', 0)):5.1f} / {v.get('switch_mV', 0):5.1f} / {v.get('strap_mV', 0):5.1f} / {v['vss_mV']:5.1f}"
    if pe[0] > BUD or pu[0] > BUD: fails.append(b)
    w = P2.strap_width_um(*LD.MAP[b]) if b in LD.MAP else None
    summ[b] = dict(island=v['island'], mA=v['mA'], drop_mV=dict(opt=o[0], nom=nm[0], pess=pe[0], pess_dig818=pu[0]), pess_case=pe[1],
                   pess_split=dict(pre_switch=v.get('pre_switch_mV', v.get('vdd_drop_mV', 0)), switch=v.get('switch_mV', 0), strap=v.get('strap_mV', 0), vss=v['vss_mV']),
                   strap_width_um=w)
    print(f"{b:13s} {str(v['island']):9s} {v['mA']:7.1f}   {o[0]:6.1f} / {nm[0]:6.1f} / {pe[0]:6.1f} / {pu[0]:6.1f}   {br}   {pe[1]:4s} {'' if w is None else f'{w:5.0f} um'} {'FAIL' if b in fails else ''}")
print('ring drop max (mV) opt / nom / pess / pess-81.8:', ' / '.join(f'{ring[s]:.1f}' for s in ring))
for k, lab in (('v', 'supply'), ('g', 'ground')):
    print(f'worst {lab} bond (mA, of {CELL_MA:.0f} per cell): ' + ' / '.join(f"{bond[(k, s)][0]:.1f} ({site[bond[(k, s)][1]][0]}, {bond[(k, s)][2]})" for s in LEVEL))
print('bond currents at pess-81.8 (mA): ' + ', '.join(f"{site[k][0]} {site[k][1]} {v[0]:.0f}" for (k, s), v in sorted(bonds_all.items(), key=lambda kv: -kv[1][0]) if s == 'pess818'))
em = max(v[0] for (k, s), v in bonds_all.items()) <= CELL_MA
print(f'E7 {CH}', 'FAIL ' + str(fails) if fails else 'PASS: every tap <= 117 mV at the pessimistic bound (also with the macro at 81.8 mA)',
      f"(worst {max(v['drop_mV']['pess'] for v in summ.values()):.1f} / {max(v['drop_mV']['pess_dig818'] for v in summ.values()):.1f} mV); bonds",
      'PASS' if em else 'FAIL', f'<= {CELL_MA:.0f} mA per cell')
json.dump(dict(chip=CH, grid=grid, strap_mv=strap, taps=summ, ring_drop_mV=ring, bonds={f'{k[0]}|{k[1]}': v for k, v in bond.items()},
               bond_mA={f'{site[k][0]}|{s}': v for (k, s), v in bonds_all.items()}, fails=fails),
          open(f'out/{CH}/e7_static_{tag}.json', 'w'), indent=1)
