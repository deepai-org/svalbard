#!/usr/bin/env python3
"""E0: the full builder against a hand calculation, and the negative control ("no decap, one supply bond").
Hand case: mesh and ring made near-ideal (coverage 100x), no bond mutuals, no intrinsic C, strip caps as stiff AC grounds,
one 2 nF lump at the macro. Then L_loop = Lb/8 + Lb/10, f0 = 1/(2 pi sqrt(L_loop C)), and the DC rail at 250 mA is
3.267 - 0.25 (0.020 + (Rb + 0.055)/8 + Rb/10)."""
import numpy as np, json, sys
import model as M, core as C, loads as LD
ok = True; res = {}
p = M.pset('nom'); p.update(grid_cov=50.0, dig_cov=50.0, bond_k1=0.0, Cint_dig_nF=1e-6, Cint_ring_nF=1e-6, Cint_ana_scale=1e-6,
                            cap0201_L_nH=1e-4, ring_custom=1.0, Lsq_loop_nH=1e-4, Rs_m34=1e-4, Rs_m5=1e-4)
n, info, ports, vict = C.full(p, decap=[(2100, 3800, 2e-9, 0.02)])
Lb = p['gnd_bond_mm']*p['bond_nH_per_mm']*1e-9; Ll = Lb/8+Lb/10; f0 = 1/(2*np.pi*np.sqrt(Ll*2e-9))
f = np.logspace(7.5, 9, 601); names, Zd, Zg = C.transfer(n, info, ports, vict, f)
z = abs(Zd[:, names.index('dig'), C.PORTS.index('dig')]); fpk = f[np.argmax(z)]
Rloop = p['bond_R']/8+p['bond_R']/10+0.03/8+0.02; Qh = np.sqrt(Ll/2e-9)/Rloop
print(f"hand: L_loop {Ll*1e9:.4f} nH, f0 {f0/1e6:.1f} MHz, Z0 {np.sqrt(Ll/2e-9):.3f} ohm, Q ~ {Qh:.1f}, Zpk ~ {Qh*np.sqrt(Ll/2e-9):.2f} ohm")
print(f"model: f(|Z|max) {fpk/1e6:.1f} MHz, |Z|max {z.max():.2f} ohm")
a = abs(fpk-f0)/f0 < 0.03; b = abs(z.max()-Qh*np.sqrt(Ll/2e-9))/(Qh*np.sqrt(Ll/2e-9)) < 0.15; ok &= a and b
res['ac'] = dict(hand_f0_MHz=f0/1e6, model_f0_MHz=fpk/1e6, hand_Zpk=Qh*np.sqrt(Ll/2e-9), model_Zpk=float(z.max()), ok=bool(a and b))
# DC: all current in the digital macro (250 mA)
e = [('car', 3.267/0.020)]; dg = info['dig_nodes']
for q in dg: e += [(M.vn(*q), -0.25/len(dg)), (M.gn(*q), 0.25/len(dg))]
V = n.solve(0.0, n.inj(e)).real
rail = np.mean([V[n.idx[M.vn(*q)]]-V[n.idx[M.gn(*q)]] for q in dg])
hand = 3.267-0.25*(0.020+(p['bond_R']+0.055)/8+p['bond_R']/10)
print(f"dc rail: model {rail:.5f} V, hand {hand:.5f} V"); c = abs(rail-hand) < 1e-3; ok &= c
res['dc'] = dict(model=float(rail), hand=hand, ok=bool(c))

# Negative control: pessimistic parameters, no decap, ONE supply bond, wired mode at the evidence bound.
def judge(tag, pset='pess', level='evid', **kw):
    p = M.pset(pset); n, info, ports, vict = C.full(p, decap=kw.pop('decap', None), **kw)
    d = C.dc(n, info, 'wired_onchip_pll', level)
    worst = min(v['rail'] for v in d['blocks'].values())
    f = np.array([78.125e6*k for k in range(1, 9)]); names, Zd, Zg = C.transfer(n, info, ports, vict, f)
    out, idig, ihost, m, rdir = LD.dc_loads('wired_onchip_pll', level)
    ln = [l for l in LD.lines('wired_onchip_pll', idig, ihost, m, rdir, 'pess' if pset == 'pess' else 'opt') if l[0] == 'digital' and l[2] <= f[-1]]
    t = np.linspace(0, 12.8e-9, 800, endpoint=False)
    w = sum((Zd[k, names.index('dig'), C.PORTS.index('dig')]*ln[k][3]*np.exp(2j*np.pi*f[k]*t)).real for k in range(len(f)))
    rip = w.max()-w.min()
    imax = max(d['bond_mA'].values())
    v = dict(worst_static_rail_V=worst, macro_ripple_pk_V=float(rip), max_bond_mA=imax,
             passes=bool(worst >= 3.15 and rip <= 0.234 and imax <= 60))
    print(f"{tag:34s} worst static rail {worst:.3f} V, macro self-ripple (78 MHz comb, 8 harmonics) {rip*1e3:.0f} mV pk-pk, max bond {imax:.0f} mA -> {'pass' if v['passes'] else 'FAIL'}")
    return v
res['neg_control_no_decap_one_bond'] = judge('NEG: no decap, 1 supply bond', n_vdd_bonds=1)
res['ref_3nF_8_bonds_pess'] = judge('ref: 3 nF MOS, 8 bonds (pess set)', decap=C.decap_plan('uniform', 3.0))
res['ref_8nF_macro_8_bonds_pess'] = judge('ref: 8 nF MOS at macro, 8 bonds', decap=C.decap_plan('digital', 8.0))
res['pass_reference_opt'] = judge('PASS ref: opt set, alloc, 4 nF macro', pset='opt', level='alloc', decap=C.decap_plan('digital', 4.0))
ok &= (not res['neg_control_no_decap_one_bond']['passes']) and res['pass_reference_opt']['passes']
res['all_ok'] = bool(ok); json.dump(res, open('out/e0.json', 'w'), indent=1)
print('E0', 'PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)
