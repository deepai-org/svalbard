#!/usr/bin/env python3
"""E7 (PD2): static IR at every tap with the reconciled currents, the re-partitioned islands and the v7 grid requirement.
Budget 117 mV (3.267 V source - 3.15 V die floor), tap to tap. opt = low-impedance set + nominal currents (digital at
PWR-DIG... see LEVEL); nom = nominal set + nominal currents; pess = high-impedance set + worst in-envelope currents with the
digital macro at 81.79 mA. Usage: e7_static_v7.py [cov_m5=0.2] [cov_m4=0.2] [strap_mv=15] [bonds=+2:13,+g:16 ...] [tag=x]"""
import sys, json
import model as M, core as C, loads as LD, pd2cfg as P2
opt = dict(a.split('=') for a in sys.argv[1:])
grid = dict(cov_m5=float(opt.get('cov_m5', P2.GRID['cov_m5'])), cov_m4=float(opt.get('cov_m4', P2.GRID['cov_m4'])))
strap = float(opt.get('strap_mv', P2.STRAP_MV)); tag = opt.get('tag', 'base')
P2.apply()
if 'vdd' in opt: M.VDD_PADS = M.VDD_PADS+[(int(x), 'X', 2.4) for x in opt['vdd'].split(',')]
if 'gnd' in opt: M.VSS_PADS = M.VSS_PADS+[int(x) for x in opt['gnd'].split(',')]
LEVEL = {'opt': 'pd2n', 'nom': 'pd2n', 'pess': 'pd2w'}
BUD = 117.0; res = {}; worst = {}; bond = {}; ring = {}
for s in ('opt', 'nom', 'pess'):
    p = P2.pset(s, grid, strap); n, info, ports, vict = C.full(p, x_feed=P2.X_FEED)
    for case in P2.CASES:
        d = C.dc(n, info, case, LEVEL[s], x_feed=P2.X_FEED); res[f'{s}|{case}'] = d
        for b, v in d['blocks'].items():
            if b.startswith('tap:') or v['mA'] < 0.3: continue
            t = (3.267-v['rail'])*1e3
            if t > worst.get((b, s), (0,))[0]: worst[(b, s)] = (t, case, v)
        vp = [x[0] for x in M.VDD_PADS]
        sb = max((v, k) for k, v in d['bond_mA'].items() if k in vp); gb = max((v, k) for k, v in d['bond_mA'].items() if k not in vp)
        if sb[0] > bond.get(('v', s), (0,))[0]: bond[('v', s)] = (*sb, case)
        if gb[0] > bond.get(('g', s), (0,))[0]: bond[('g', s)] = (*gb, case)
        ring[s] = max(ring.get(s, 0), 1e3*(3.267-d['ring_rail_min']))
print(f'grid per net: Metal5 {grid["cov_m5"]:.2f}, Metal4 {grid["cov_m4"]:.2f}; strap budget {strap} mV; bonds VDD {[x[0] for x in M.VDD_PADS]} GND {M.VSS_PADS}')
print('tap           island     mA(worst)  total drop opt / nom / pess (mV)   pess split: to-switch / switch / strap / vss   worst case, Metal5 strap width that gives 15 mV over the modelled distance')
rows = sorted({b for (b, s) in worst}, key=lambda b: -worst.get((b, 'pess'), (0,))[0]); fails = []
summ = {}
for b in rows:
    o, nm, pe = (worst.get((b, s), (float('nan'), '', {})) for s in ('opt', 'nom', 'pess')); v = pe[2]
    br = f"{v.get('pre_switch_mV', v.get('vdd_drop_mV', 0)):5.1f} / {v.get('switch_mV', 0):5.1f} / {v.get('strap_mV', 0):5.1f} / {v['vss_mV']:5.1f}"
    if pe[0] > BUD: fails.append(b)
    summ[b] = dict(island=v['island'], mA=v['mA'], drop_mV=dict(opt=o[0], nom=nm[0], pess=pe[0]), pess_case=pe[1],
                   pess_split=dict(pre_switch=v.get('pre_switch_mV', v.get('vdd_drop_mV', 0)), switch=v.get('switch_mV', 0), strap=v.get('strap_mV', 0), vss=v['vss_mV']))
    w = P2.strap_width_um(b) if b in LD.MAP else None
    summ[b]['strap_width_um_at_modelled_distance'] = w
    print(f"{b:13s} {str(v['island']):9s} {v['mA']:7.1f}   {o[0]:6.1f} / {nm[0]:6.1f} / {pe[0]:6.1f}   {br}   {pe[1]:4s} strap {'' if w is None else f'{w:5.0f} um'} {'FAIL' if pe[0] > BUD else ''}")
print('ring drop max (mV) opt/nom/pess:', ' / '.join(f'{ring[s]:.1f}' for s in ring))
for k, lab in (('v', 'supply'), ('g', 'ground')):
    print(f'worst {lab} bond (mA): ' + ' / '.join(f"{bond[(k, s)][0]:.1f} (pad {bond[(k, s)][1]}, {bond[(k, s)][2]})" for s in ('opt', 'nom', 'pess')))
print('E7', 'FAIL ' + str(fails) if fails else 'PASS: every tap <= 117 mV at the pessimistic bound', f"(worst {max(v['drop_mV']['pess'] for v in summ.values()):.1f} mV)")
json.dump(dict(grid=grid, strap_mv=strap, taps=summ, ring_drop_mV=ring, bonds={f'{k[0]}|{k[1]}': v for k, v in bond.items()}, fails=fails),
          open(f'out/e7_static_v7_{tag}.json', 'w'), indent=1)
