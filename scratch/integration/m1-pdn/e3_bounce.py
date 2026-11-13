#!/usr/bin/env python3
"""E3/E4: bounce at the sensitive taps per mode, decap plan and bound, then victim impact.
pess = pessimistic aggressor spectrum x the WORST of the opt/nom/pess network sets per line (resonance position is not
monotonic in the parameters); opt = optimistic spectrum x the BEST set per line.
Usage: e3_bounce.py [tag] [key=value build options: host_split=1 | pll_split=1 | x_feed=0.8 | strip=0 | nvdd=N]"""
import json, sys, numpy as np
import model as M, core as C, loads as LD
tag = sys.argv[1] if len(sys.argv) > 1 else 'base'
opt = dict(a.split('=') for a in sys.argv[2:])
kw = {}
if opt.get('host_split') == '1': kw['host_split'] = (18, 74, 9, 19, 73)      # D2H rail on 2 supply + 3 ground bonds of its own
if opt.get('pll_split') == '1': kw['split'] = {'pll': 64}                      # pll/LO island fed by bond 64 (PWR_AUX_1) only
if 'strip' in opt: kw['strip_caps'] = opt['strip'] == '1'
if 'nvdd' in opt: kw['n_vdd_bonds'] = int(opt['nvdd'])
xf = float(opt.get('x_feed', 0.0))
MODES = ['wired_onchip_pll', 'usb', 'rf_autonomous', 'rf_tx_autonomous', 'rf_duplex_external_clock']
PLANS = {'none': lambda: C.decap_plan('none'), '1nF_spread': lambda: C.decap_plan('uniform', 1.0),
         '3nF_spread': lambda: C.decap_plan('uniform', 3.0), 'ap49_low': lambda: C.decap_plan('ap49', frac=0.30, dig_fill_nF=0.45),
         'ap49_high': lambda: C.decap_plan('ap49', frac=1.0, dig_fill_nF=1.0),
         'ap49_low+1.5nF_macro': lambda: C.decap_plan('ap49', frac=0.30, dig_fill_nF=1.95)}
if tag != 'base': PLANS = {k: PLANS[k] for k in ('none', '3nF_spread', 'ap49_low')}
allL = {}
for mo in MODES:
    out, idig, ihost, m, rdir = LD.dc_loads(mo, 'evid+')
    allL[mo] = {b: LD.lines(mo, idig, ihost, m, rdir, b) for b in ('pess', 'nom', 'opt')}
F = np.array(sorted({l[2] for mo in MODES for l in allL[mo]['pess']}))
K_VCO = 59.7e6; F_LO = 2.417e9
def ring_dj(f):   # ps pk per volt of raw-rail ripple, regulated (pll_vreg2 extracted: 2.71 ps at 60 mV / 78 MHz, 0.69 ps at 156 MHz)
    return 0.045e3*(78.125e6/f)**(1.0 if f < 78.125e6 else 1.97)
res = {}
T_N = 1024
def synth(lines, Zc, vi):
    """Time-domain steady-state ripple of one periodic aggressor at a victim: returns (pk-pk, droop below the mean) in V."""
    if not lines: return 0.0, 0.0
    f0 = min(l[2] for l in lines); t = np.arange(T_N)/T_N/f0; w = np.zeros(T_N)
    for (ag, port, f, a, ae) in lines:
        k = int(np.searchsorted(F, f)); w += (Zc[k, vi, C.PORTS.index(port)]*a*np.exp(2j*np.pi*f*t)).real
    return float(w.max()-w.min()), float(-w.min())
for plan, mk in PLANS.items():
    Zc = {}; Zg = {}
    for s in ('opt', 'nom', 'pess'):
        n, info, ports, vict = C.full(M.pset(s), decap=mk(), x_feed=xf, **kw)
        names, Zc[s], Zg[s] = C.transfer(n, info, ports, vict, F)
    for mo in MODES:
        for b in ('pess', 'nom', 'opt'):
            pick = max if b == 'pess' else min if b == 'opt' else (lambda it: list(it)[1])
            L = allL[mo][b]; r = {}
            for vi, v in enumerate(names):
                # per-line magnitudes, worst (pess) or best (opt) network set per line
                ln = []
                for (ag, port, f, a, ae) in L:
                    k = int(np.searchsorted(F, f)); pi = C.PORTS.index(port)
                    zd = pick(abs(Zc[s][k, vi, pi]) for s in Zc); zg = pick(abs(Zg[s][k, vi, pi]) for s in Zc)
                    ln.append((ag, f, a*zd, ae*zg, a*zg))
                vd = np.array([x[2] for x in ln]); fr = np.array([x[1] for x in ln])
                # waveform of the two pulse-train aggressors, per network set
                td = {}
                for ag in ('digital', 'd2h'):
                    q = [synth([l for l in L if l[0] == ag], Zc[s], vi) for s in Zc]
                    td[ag] = dict(pkpk_mV=pick(x[0] for x in q)*1e3, droop_mV=pick(x[1] for x in q)*1e3)
                other = float(sum(x[2] for x in ln if x[0] not in ('digital', 'd2h')))
                top = sorted(ln, key=lambda x: -x[2])[:5]
                r[v] = dict(digital=td['digital'], d2h=td['d2h'], other_lines_sum_mV=other*1e3,
                            droop_bound_mV=td['digital']['droop_mV']+td['d2h']['droop_mV']+other*1e3,
                            rail_rss_mV=float(np.sqrt((vd**2).sum()/2)*1e3),
                            top=[(x[0], round(x[1]/1e6, 2), round(x[2]*1e3, 3)) for x in top])
                if v == 'host':
                    q = [synth([l for l in L if l[0] == 'd2h'], Zg[s], vi) for s in Zc]
                    r[v]['d2h_vss_vs_board_pkpk_mV'] = pick(x[0] for x in q)*1e3
                if v == 'qvco':
                    spur = 20*np.log10(np.maximum(1e-30, K_VCO*vd/(2*fr))); w = int(np.argmax(spur))
                    jit = np.sqrt(np.sum((K_VCO*vd[fr > 3e5]/(np.sqrt(2)*fr[fr > 3e5]))**2))/(2*np.pi*F_LO)*1e12
                    r[v].update(worst_spur_dBc=float(spur[w]), worst_spur_line=(ln[w][0], ln[w][1]/1e6, ln[w][2]*1e3),
                                psrr_needed_for_m80dBc_dB=float(max(0, spur[w]+80)), jitter_ps_rms=float(jit),
                                psrr_needed_for_0p46ps_dB=float(max(0, 20*np.log10(max(jit, 1e-9)/0.46))),
                                spurs={f'{ln[i][0]}@{ln[i][1]/1e6:g}': round(float(spur[i]), 1) for i in np.argsort(-spur)[:6]})
                if v == 'pll_vreg2':
                    dj = sum(ring_dj(f)*x for f, x in zip(fr, vd))
                    r[v].update(ring_dj_regulated_ps_pk=float(dj), ring_dj_bypass_ps_pk=float(dj*0.55/0.045))
                if v in ('adc_i', 'refbuf'):
                    w = int(np.argmax(vd)); al = abs(fr[w]-round(fr[w]/40e6)*40e6)
                    need = 20*np.log10(max(vd[w], 1e-12)/0.87)+60
                    r[v].update(worst_line=(ln[w][0], fr[w]/1e6, vd[w]*1e3), alias_MHz=float(al/1e6), psrr_needed_for_m60dBFS_dB=float(max(0, need)))
                if v == 'lna':
                    inb = [(x[0], x[1], x[3], x[4]) for x in ln if 2.39e9 <= x[1] <= 2.5e9]
                    if inb:
                        w = max(inb, key=lambda x: x[2]); vr = w[2]/np.sqrt(2)
                        r[v].update(inband_line=(w[0], w[1]/1e6), vss_inband_uV_rms_env=float(vr*1e6), vss_inband_uV_rms_exact=float(w[3]/np.sqrt(2)*1e6),
                                    input_ref_dBm_cmrr25=float(10*np.log10((vr*10**(-25/20))**2/50*1e3+1e-30)),
                                    input_ref_dBm_cmrr30=float(10*np.log10((vr*10**(-30/20))**2/50*1e3+1e-30)))
            res[f'{plan}|{mo}|{b}'] = r
json.dump(res, open(f'out/e3_{tag}.json', 'w'), indent=0)
def g(plan, mo, b, v, k):
    x = res[f'{plan}|{mo}|{b}'][v]
    for kk in k.split('.'): x = x.get(kk, float('nan')) if isinstance(x, dict) else float('nan')
    return x
for mo in MODES:
    print(f'=== {mo}  (opt / nom / pess)   [{tag}]')
    for plan in PLANS:
        s = f'  {plan:20s}'
        for v, k, lab in (('dig', 'digital.pkpk_mV', 'macro dig pp'), ('dig', 'd2h.pkpk_mV', 'macro d2h pp'), ('dig', 'droop_bound_mV', 'macro droop'),
                          ('core_bias', 'droop_bound_mV', 'bias droop'), ('qvco', 'rail_rss_mV', 'qvco rms'),
                          ('qvco', 'worst_spur_dBc', 'spur dBc'), ('qvco', 'jitter_ps_rms', 'jit ps'), ('pll_vreg2', 'ring_dj_regulated_ps_pk', 'ringDJ ps'),
                          ('refbuf', 'droop_bound_mV', 'refbuf droop'), ('refbuf', 'psrr_needed_for_m60dBFS_dB', 'adcPSRR'), ('slicer', 'droop_bound_mV', 'slicer droop'),
                          ('lna', 'input_ref_dBm_cmrr25', 'lna dBm'), ('host', 'd2h.pkpk_mV', 'host rail d2h pp'), ('host', 'd2h_vss_vs_board_pkpk_mV', 'host gnd bounce pp')):
            s += f' | {lab} {g(plan, mo, "opt", v, k):.3g}/{g(plan, mo, "nom", v, k):.3g}/{g(plan, mo, "pess", v, k):.3g}'
        print(s)
