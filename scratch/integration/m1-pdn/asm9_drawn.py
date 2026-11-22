#!/usr/bin/env python3
"""ASM-9: static IR and EM at 85 C with the grid as the assembly draws it (scratch/integration/assembly-<chip>, README
'Power grid coverage per net': pt_rf M4 7.3-7.8 % / M5 10.5-11.0 %, pt_wired M4 8.0-8.5 % / M5 11.5-11.9 %; core ring
2 x 14 um on Metal4 + Metal5) instead of the G1 / G8 requirement. Pessimistic set, worst currents with the digital macro
at the unscaled 81.8 mA (pd2u: pt_wired W 432 mA with POST on), all bonds and each single open supply bond.
EM at 85 C (DRM 14.2): core ring per net 14 um Metal4 x 2.09 + 14 um Metal5 x 4.5 mA/um = 92 mA; supply cell 125 mA.
The core ring's share of each boundary-edge current is its conductance share against the provider rails at that edge.
Usage: asm9_drawn.py chip=rf|wired [m4=0.073] [m5=0.105] [ring=14] [tovdd=site,..] [move=rect:x0,y0;..] [tag=..] [regions=1 [set=SE:15;ME:12]] [pset=nom: nominal set and nominal currents]"""
import sys, json, numpy as np
import model as M, core as C, chipcfg as P2
D = dict(a.split('=', 1) for a in sys.argv[1:]); P2.apply(); CH = P2.CHIP
DEF = {'rf': (0.073, 0.105), 'wired': (0.080, 0.115)}[CH]
m4, m5, ring = float(D.get('m4', DEF[0])), float(D.get('m5', DEF[1])), float(D.get('ring', 14))
RING_LIM = ring*2.09+ring*4.5; CELL = 125.0
CASE = {'rf': ['RXa', 'TXa', 'DXa', 'DXe'], 'wired': ['W', 'U']}[CH]
sites_xy = json.load(open(f'{M.PRJ}/analog/pads/generated/provider-sites.json'))['sites']
for k, v in D.items():          # experiments: tovdd=site[,site] converts bonds/sites to VDD; move=rect:x0,y0 shifts a rectangle
    if k == 'tovdd':
        for st in v.split(','):
            b = [b for b in M.BONDS if b['site'] == st]
            if b: b[0]['net'] = 'VDD'; b[0]['cap'] = False
            else:
                x, y = sites_xy[st]['bond_center_um']; M.BONDS.append(dict(site=st, x=x, y=y, net='VDD', side='?', ring=max(b['ring'] for b in M.BONDS)+1, inst='x', cap=False))
    if k == 'move':
        for it in v.split(';'):
            nm, xy = it.split(':'); x0, y0 = map(float, xy.split(',')); r = M.RECTS[nm]; w, h = r[2]-r[0], r[3]-r[1]; M.RECTS[nm] = [x0, y0, x0+w, y0+h]
REG = None
if D.get('regions'):     # drawn per-region coverage: scratch/integration/assembly-<chip>/place.json pdn_regions_pct, 3 x 3 over the core
    REG = json.load(open(f'{M.ROOT}/scratch/integration/assembly-{CH}/place.json'))['pdn_regions_pct']
    for it in D.get('set', '').split(';'):          # overrides: set=SE:15;ME:12  (every net and layer of that region at least this %)
        if it:
            r, v = it.split(':'); REG[r] = {k: max(x, float(v)) for k, x in REG[r].items()}
def cov_region(x, y, net, layer):
    cx = min(2, int(3*(x-M.CORE[0])/(M.CORE[2]-M.CORE[0]))); cy = min(2, int(3*(y-M.CORE[1])/(M.CORE[3]-M.CORE[1])))
    return REG['SMN'[cy]+'WCE'[cx]][f'{net.upper()}_{layer}']/100.0
dec = P2.plan(); B0 = list(M.BONDS)
def ring_seg(n, info, p):
    """max core-ring current (mA) over the boundary edges, per net"""
    V = info['V_dc']; out = {}
    for nm in (M.vn, M.gn):
        w = 0.0
        for i in range(M.NX):
            for j in range(M.NY):
                for a, b in (((i, j), (i+1, j)), ((i, j), (i, j+1))):
                    if b[0] >= M.NX or b[1] >= M.NY: continue
                    horiz = b[0] > a[0]
                    edge = (not horiz and a[0] in (0, M.NX-1)) or (horiz and a[1] in (0, M.NY-1))
                    if not edge: continue
                    L = M.PX if horiz else M.PY
                    w_rail = (124.0+14.0) if nm is M.vn else (101.4+14.0)
                    g_rail = w_rail*(2/p['Rs_m34']+1/p['Rs_m5']); g_core = ring/p['Rs_m34']+ring/p['Rs_m5']
                    i_tot = abs(V[n.idx[nm(*a)]]-V[n.idx[nm(*b)]])*(g_rail+g_core)/L   # mesh in parallel ignored: conservative
                    w = max(w, i_tot*g_core/(g_rail+g_core)*1e3)
        out[nm.__name__] = w
    return out
res = {}; worst = {}
print(f"{CH}: {'per-region coverage ' + str(D.get('set', 'as drawn')) if REG else ''}")
print(f'{CH}: drawn grid M4 {m4:.3f} / M5 {m5:.3f} per net, core ring 2 x {ring:g} um M4+M5 (EM limit {RING_LIM:.0f} mA per net), pess set, digital 81.8 mA')
for drop in [None]+[b['site'] for b in B0 if b['net'] == 'VDD']:
    M.BONDS[:] = [b for b in B0 if b['site'] != drop]
    p = P2.pset(D.get('pset', 'pess'), dict(cov_m5=m5, cov_m4=m4), core_ring_w=ring, ring_core_w=ring)
    if REG: p['cov_region'] = cov_region
    n, info, ports, vict = C.full(p, decap=dec, x_feed=P2.X_FEED)
    site = {b['ring']: (b['site'], b['net']) for b in M.BONDS}
    for case in CASE:
        d = C.dc(n, info, case, 'pd2u' if D.get('pset', 'pess') == 'pess' else 'pd2n', x_feed=P2.X_FEED); rs = ring_seg(n, info, p)
        taps = {b: (3.267-v['rail'])*1e3 for b, v in d['blocks'].items() if v['mA'] > 0.3 and not b.startswith('tap:')}
        tb = max(taps, key=taps.get); bv = max((x, site[k][0]) for k, x in d['bond_mA'].items())
        key = drop or 'all bonds'; r = res.setdefault(key, dict(tap=(0,), bond=(0,), ring=0.0, taps={}))
        if taps[tb] > r['tap'][0]: r['tap'] = (taps[tb], tb, case)
        if bv[0] > r['bond'][0]: r['bond'] = (*bv, case)
        r['ring'] = max(r['ring'], max(rs.values()))
        for b, t in taps.items(): r['taps'][b] = max(r['taps'].get(b, 0), t)
for k, r in res.items():
    print(f"{k:18s} worst tap {r['tap'][0]:6.1f} mV ({r['tap'][1]}, {r['tap'][2]}) {'PASS' if r['tap'][0] <= 117 else 'FAIL'} | worst bond {r['bond'][0]:5.1f} mA ({r['bond'][1]}) {'PASS' if r['bond'][0] <= CELL else 'FAIL'} | core ring {r['ring']:5.1f} mA of {RING_LIM:.0f} {'PASS' if r['ring'] <= RING_LIM else 'FAIL'}")
a = res['all bonds']['taps']; print('taps over 117 mV with all bonds:', {b: round(t, 1) for b, t in sorted(a.items(), key=lambda x: -x[1]) if t > 117} or 'none')
print('top taps, all bonds:', ', '.join(f'{b} {t:.1f}' for b, t in sorted(a.items(), key=lambda x: -x[1])[:6]))
json.dump(dict(chip=CH, m4=m4, m5=m5, ring=ring, res={k: dict(v, taps={b: round(t, 2) for b, t in v['taps'].items()}) for k, v in res.items()}),
          open(f"out/{CH}/asm9_{D.get('tag', 'drawn')}_m4{m4}_m5{m5}_r{ring:g}.json", 'w'), indent=0)
