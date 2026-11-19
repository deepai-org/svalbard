#!/usr/bin/env python3
"""E9 per chip: ripple spectrum at every victim tap with the chip's 5.4 nF plan, reconciled currents and the grid
requirement. opt / nom / pess sources; pess = pessimistic source x the worst of the three networks per line. Two-phase
(PD2-6): odd harmonics of the macro's 78.125 MHz train x RES (residual imbalance; 0.15 = 57.5 / 42.5 split).
pt_rf also gets the QVCO regulator requirement against -60 dBc per tone (K = -59.7 MHz/V at 2.417 GHz): allowed ripple at
the QVCO V = 2 f 10^(-60/20) / K, rejection = 20 log(input ripple / allowed); macro and D2H lines at the same frequency are
added (both are 78.125 MHz multiples in RF modes).
Usage: e9_victims.py chip=rf|wired [res=1.0] [tag=base]"""
import sys, json, numpy as np
import model as M, core as C, loads as LD, chipcfg as P2
from pd2_lines import spectrum
opt = dict(a.split('=') for a in sys.argv[1:] if '=' in a); RES = float(opt.get('res', 1.0)); tag = opt.get('tag', 'base')
P2.apply(); CH = P2.CHIP
K_VCO = 59.7e6; LIM_DBC = -60.0
MODES = {'rf': {'RXa': ['core_bias', 'refbuf', 'adc_i', 'qvco', 'lo_mmd', 'lna', 'pll_vreg2', 'por'], 'TXa': ['core_bias', 'qvco', 'lo_mmd', 'rfdriver'],
                'DXa': ['qvco', 'lna', 'refbuf', 'adc_i'], 'RXe': ['lna', 'refbuf', 'adc_i', 'core_bias']},
         'wired': {'W': ['core_bias', 'por', 'pll_vreg2', 'slicer', 'wiredtx', 'wrx_cap', 'dig'], 'U': ['core_bias', 'slicer', 'pll_vreg2']}}[CH]
psets = {s: P2.pset(s) for s in ('opt', 'nom', 'pess')}; res = {}
def ring_dj(f): return 0.045e3*(78.125e6/f)**(1.0 if f < 78.125e6 else 1.97)    # ps pk per V, regulated (pll_vreg2 extracted)
bands = [(0, 30e6), (30e6, 100e6), (100e6, 200e6), (200e6, 500e6), (500e6, 1e9), (1e9, 6e9)]
for mo, victims in MODES.items():
    sp = spectrum(victims, mo, P2.plan(), level='pd2w', psets=psets, x_feed=P2.X_FEED)
    for v in victims:
        rows = []
        for (ag, f), x in sp[v].items():
            k = RES if (ag == 'digital' and round(f/78.125e6) % 2) else 1.0
            rows.append(dict(ag=ag, f=f, rail=[x[b][0]*k for b in ('opt', 'nom', 'pess')], vss=[x[b][1]*k for b in ('opt', 'nom', 'pess')]))
        rows.sort(key=lambda r: -r['rail'][2])
        d = dict(top=[dict(ag=r['ag'], f_MHz=round(r['f']/1e6, 3), rail_mV_pk=[round(a*1e3, 3) for a in r['rail']]) for r in rows[:12]],
                 rss_mV_rms=[float(np.sqrt(sum(r['rail'][i]**2 for r in rows)/2)*1e3) for i in range(3)])
        d['band_max_mV_pk'] = {f'{a/1e6:g}-{b/1e6:g} MHz': [round(max([r['rail'][i] for r in rows if a < r['f'] <= b], default=0)*1e3, 3) for i in range(3)] for a, b in bands}
        if v == 'qvco':
            byf = {}
            for r in rows:
                key = round(r['f']/1e3)*1e3; e = byf.setdefault(key, dict(ags=set(), rail=[0, 0, 0]))
                e['ags'].add(r['ag']); e['rail'] = [a+b for a, b in zip(e['rail'], r['rail'])]
            tab = []
            for f, e in sorted(byf.items()):
                allowed = 2*f*10**(LIM_DBC/20)/K_VCO
                tab.append(dict(f_MHz=round(f/1e6, 3), aggressors=sorted(e['ags']), ripple_mV_pk=[round(a*1e3, 3) for a in e['rail']], allowed_uV=round(allowed*1e6, 1),
                                rejection_dB=[round(max(0.0, 20*np.log10(max(a, 1e-15)/allowed)), 1) for a in e['rail']]))
            d['qvco_requirement'] = [t for t in tab if t['f_MHz'] <= 1000]
        if v == 'pll_vreg2':
            d['ring_dj_regulated_ps_pk'] = [float(sum(ring_dj(r['f'])*r['rail'][i] for r in rows)) for i in range(3)]
        if v in ('adc_i', 'refbuf'):
            al = [r for r in rows if 0 < abs(r['f']-round(r['f']/40e6)*40e6) < 20e6]
            w = max(al, key=lambda r: r['rail'][2])
            d['worst_aliasing_line_40MSps'] = dict(ag=w['ag'], f_MHz=w['f']/1e6, mV_pk=[round(a*1e3, 2) for a in w['rail']],
                                                    psrr_needed_dB_for_m60dBFS=[round(max(0.0, 20*np.log10(max(a, 1e-12)/0.87)+60), 1) for a in w['rail']])
        if v == 'lna':
            inb = [r for r in rows if 2.39e9 <= r['f'] <= 2.5e9]
            if inb:
                w = max(inb, key=lambda r: r['vss'][2]); vr = [a/np.sqrt(2) for a in w['vss']]
                d['inband'] = dict(ag=w['ag'], f_MHz=w['f']/1e6, vss_uV_rms=[round(a*1e6, 1) for a in vr],
                                   rejection_needed_dB_for_m100dBm=[round(float(20*np.log10(max(a, 1e-12)/2.24e-6)), 1) for a in vr])
        res[f'{mo}|{v}'] = d
json.dump(dict(chip=CH, res=RES, victims=res), open(f'out/{CH}/e9_victims_{tag}.json', 'w'), indent=1)
f3 = lambda x: ' / '.join(f'{a:.3g}' for a in x)
print(f'{CH}: victims, residual {RES} (1.0 = single-phase macro); mV peak opt / nom / pess')
for k, d in res.items():
    print(f"== {k}: rms {f3(d['rss_mV_rms'])} mV; bands: " + '; '.join(f"{b} {f3(x)}" for b, x in d['band_max_mV_pk'].items() if x[2] > 0))
    print('   top: ' + '; '.join(f"{t['ag']}@{t['f_MHz']:g} {f3(t['rail_mV_pk'])}" for t in d['top'][:5]))
    for kk in ('ring_dj_regulated_ps_pk', 'worst_aliasing_line_40MSps', 'inband'):
        if kk in d: print(f'   {kk}: {d[kk]}')
    if 'qvco_requirement' in d:
        print('   QVCO regulator rejection for -60 dBc per tone (f MHz: ripple at the regulator input opt/nom/pess mV pk, allowed uV, rejection dB):')
        for t in sorted(d['qvco_requirement'], key=lambda t: -t['rejection_dB'][2])[:10]:
            print(f"     {t['f_MHz']:8g} {'+'.join(t['aggressors']):18s} {f3(t['ripple_mV_pk'])}  allowed {t['allowed_uV']}  -> {f3(t['rejection_dB'])}")
