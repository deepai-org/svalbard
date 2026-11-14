#!/usr/bin/env python3
"""M2 full-die transfer matrix on the v6 outline floorplan (scratch/chip-assembly-v6/run/floorplan-v6.json).
Aggressor footprint forced to 1 V (ground-bounce referred to the common ground) -> floating-probe surface potential on each
victim footprint (dB; near = worst 10 % of cells, mean).  D2H route: 1 A injected uniformly along the strip -> ohm (normalised,
x rho/h).  Cases are the two-sided knobs of submesh.py."""
import json, sys, numpy as np, submesh as sm
fp = json.load(open('/home/ubuntu/svalbard/scratch/chip-assembly-v6/run/floorplan-v6.json'))
R = {p['name']: p['rect'] for p in fp['fixed']}; R.update({k: v['rect'] for k, v in fp['placed'].items()})
import os
NZ = int(os.environ.get('SUBMESH_NZ', '12')); TAG = os.environ.get('SUBMESH_TAG', '')
DIE = (3932.0, 5122.0); CORE = (452, 452, 3480, 4670)
def union(*n): return [min(R[k][0] for k in n), min(R[k][1] for k in n), max(R[k][2] for k in n), max(R[k][3] for k in n)]
AGG = {'digital': R['digital'], 'pll_cdr': R['pll_cdr'], 'pll_tx+vreg2': union('pll_tx', 'pll_vreg2'), 'rfdriver': R['rfdriver'],
       'pad_rf_tx': R['pad_rf_tx'], 'wired_fe(ctle+detect+term)': union('ctle', 'detect', 'term_buffer'), 'pad_hs_rx': R['pad_hs_rx'],
       'clk_obs16': R['clk_obs16'], 'lo_mmd': R['lo_mmd']}
ROUTES = {'d2h_east_corridor(x2750-2800,y476-3030)': [2750, 476, 2800, 3030], 'd2h_over_adc(x2000-2050,y476-3030)': [2000, 476, 2050, 3030]}
VIC = ['adc_i', 'adc_q', 'lna', 'pad_rf_rx', 'core_bias', 'por', 'rxmix_i', 'rxmix_q', 'bbfilter_i', 'bbfilter_q', 'lo_pfdcp', 'lo_mmd', 'dac_i', 'dac_q', 'pll_cdr']
CASES = {'sparse_float': dict(tie='sparse', back=False, surf=1.0), 'sparse_float_skin3': dict(tie='sparse', back=False, surf=3.0),
         'sparse_backgnd': dict(tie='sparse', back=True, surf=1.0), 'dense_float': dict(tie='dense', back=False, surf=1.0),
         'dense_backgnd': dict(tie='dense', back=True, surf=1.0)}
out = {}
for cn, c in CASES.items():
    m = sm.Mesh(*DIE, nz=NZ, surf=c['surf']); nx, ny = m.nx, m.ny
    vm = {v: m.cells(R[v]) for v in VIC}
    allv = np.zeros((nx, ny), bool)
    for v in VIC: allv |= vm[v]
    if c['tie'] == 'dense': base = np.ones((nx, ny))
    else:
        base = np.zeros((nx, ny))
        for k, r in R.items(): base[m.cells(r)] = 0.3
        core = m.cells(CORE); base[~core] = 0.3
    out[cn] = {}
    for an, ar in list(AGG.items())+list(ROUTES.items()):
        f = m.cells(ar); tie = base.copy(); tie[allv & ~f] = 0.0
        if an in ROUTES:
            tie[f & ~allv] = base[f & ~allv]; inj = np.zeros((nx, ny)); inj[f] = 1.0/f.sum()
            v = m.solve(tie, inject=inj, back=c['back'])
            r = {vn: dict(near_ohm_norm=float(np.percentile(v[vm[vn]], 90)), mean_ohm_norm=float(v[vm[vn]].mean())) for vn in VIC}
        else:
            v = m.solve(tie, force=f, back=c['back'])
            r = {vn: dict(near_db=sm.db(np.percentile(v[vm[vn] & ~f], 90)), mean_db=sm.db(v[vm[vn] & ~f].mean())) for vn in VIC if (vm[vn] & ~f).any() and vn != an}
            # realistic lower bound: every victim keeps its own taps (to an ideal quiet ground) -> residual local potential
            t2 = base.copy(); t2[allv & ~f] = 0.3 if c['tie'] == 'sparse' else 1.0
            v2 = m.solve(t2, force=f, back=c['back'])
            for vn in r: r[vn]['tied_near_db'] = sm.db(np.percentile(v2[vm[vn] & ~f], 90)); r[vn]['tied_mean_db'] = sm.db(v2[vm[vn] & ~f].mean())
        out[cn][an] = r
        print(cn, an, {k: ((w['near_db'], w['tied_near_db']) if an not in ROUTES else round(w['near_ohm_norm'], 4)) for k, w in r.items()}, flush=True)
    json.dump(out, open(f'v6_matrix{TAG}.json', 'w'), indent=1)
