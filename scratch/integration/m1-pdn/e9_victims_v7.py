#!/usr/bin/env python3
"""E9 (PD2): ripple spectrum at every victim tap with the decap plan, the reconciled currents and the v7 grid requirement,
and what each victim needs. Sources: opt / nom / pess as E3 (pess = pessimistic source x the worst of the three networks
per line). 'two-phase' scales the odd harmonics of the macro's 78.125 MHz train by RES (PD2-6: launch charge split
over both half-cycles, residual imbalance RES = 0.2 for a 60/40 split).
Usage: e9_victims_v7.py [res=1.0] [vdd=13,..] [gnd=..] [tag=..]"""
import sys, json, numpy as np
import model as M, core as C, loads as LD, pd2cfg as P2
from pd2_lines import spectrum
opt = dict(a.split('=') for a in sys.argv[1:]); RES = float(opt.get('res', 1.0)); tag = opt.get('tag', 'base')
P2.apply()
if 'vdd' in opt: M.VDD_PADS = M.VDD_PADS+[(int(x), 'X', 2.4) for x in opt['vdd'].split(',')]
if 'gnd' in opt: M.VSS_PADS = M.VSS_PADS+[int(x) for x in opt['gnd'].split(',')]
K_VCO = 59.7e6; F_LO = 2.417e9
MODES = {'W': ['core_bias', 'por', 'pll_vreg2', 'slicer', 'wiredtx', 'dig'], 'RXa': ['core_bias', 'refbuf', 'adc_i', 'qvco', 'lo_mmd', 'lna', 'pll_vreg2'],
         'TXa': ['core_bias', 'qvco', 'lo_mmd', 'rfdriver', 'refbuf'], 'DXa': ['qvco', 'lna', 'refbuf', 'adc_i'], 'RXe': ['lna', 'refbuf', 'adc_i']}
psets = {s: P2.pset(s) for s in ('opt', 'nom', 'pess')}
res = {}
def ring_dj(f): return 0.045e3*(78.125e6/f)**(1.0 if f < 78.125e6 else 1.97)    # ps pk per V, regulated (pll_vreg2 extracted)
for mo, victims in MODES.items():
    sp = spectrum(victims, mo, P2.plan(), level='pd2w', psets=psets, x_feed=P2.X_FEED)
    for v in victims:
        rows = []
        for (ag, f), x in sp[v].items():
            k = RES if (ag == 'digital' and round(f/78.125e6) % 2) else 1.0
            rows.append(dict(ag=ag, f=f, rail=[x[b][0]*k for b in ('opt', 'nom', 'pess')], vss=[x[b][1]*k for b in ('opt', 'nom', 'pess')]))
        rows.sort(key=lambda r: -r['rail'][2])
        d = dict(top=[dict(ag=r['ag'], f_MHz=round(r['f']/1e6, 3), rail_mV_pk=[round(a*1e3, 3) for a in r['rail']]) for r in rows[:12]],
                 rss_mV_rms=[float(np.sqrt(sum(r['rail'][i]**2 for r in rows)/2)*1e3) for i in range(3)],
                 sum_mV_pk=[float(sum(r['rail'][i] for r in rows)*1e3) for i in range(3)])
        # band summary (worst line per band)
        bands = [(0, 30e6), (30e6, 100e6), (100e6, 200e6), (200e6, 500e6), (500e6, 1e9), (1e9, 6e9)]
        d['band_max_mV_pk'] = {f'{a/1e6:g}-{b/1e6:g} MHz': [round(max([r['rail'][i] for r in rows if a < r['f'] <= b], default=0)*1e3, 3) for i in range(3)] for a, b in bands}
        if v == 'qvco':
            need = {}
            for r in rows:
                for i in range(3):
                    s = 20*np.log10(max(1e-30, K_VCO*r['rail'][i]/(2*r['f'])))
                    key = f"{r['ag']}@{r['f']/1e6:g}"
                    need.setdefault(key, [0, 0, 0])[i] = round(float(s), 1)
            w = sorted(need.items(), key=lambda kv: -kv[1][2])[:8]
            d['spur_dBc_unregulated'] = dict(w)
            d['psrr_needed_dB_for_m80dBc'] = {k: [round(max(0.0, x+80), 1) for x in vv] for k, vv in w}
            d['jitter_ps_rms_unregulated'] = [float(np.sqrt(sum((K_VCO*r['rail'][i]/(np.sqrt(2)*r['f']))**2 for r in rows if r['f'] > 3e5))/(2*np.pi*F_LO)*1e12) for i in range(3)]
        if v == 'pll_vreg2':
            d['ring_dj_regulated_ps_pk'] = [float(sum(ring_dj(r['f'])*r['rail'][i] for r in rows)) for i in range(3)]
            d['ring_dj_bypass_ps_pk'] = [x*0.55/0.045 for x in d['ring_dj_regulated_ps_pk']]
        if v in ('adc_i', 'refbuf'):
            al = [(r, abs(r['f']-round(r['f']/40e6)*40e6)) for r in rows if 0 < abs(r['f']-round(r['f']/40e6)*40e6) < 20e6]
            w = max(al, key=lambda t: t[0]['rail'][2])[0]
            d['worst_aliasing_line'] = dict(ag=w['ag'], f_MHz=w['f']/1e6, mV_pk=[round(a*1e3, 2) for a in w['rail']],
                                            psrr_needed_dB_for_m60dBFS=[round(max(0.0, 20*np.log10(max(a, 1e-12)/0.87)+60), 1) for a in w['rail']])
        if v == 'lna':
            inb = [r for r in rows if 2.39e9 <= r['f'] <= 2.5e9]
            if inb:
                w = max(inb, key=lambda r: r['vss'][2]); vr = [a/np.sqrt(2) for a in w['vss']]
                d['inband'] = dict(ag=w['ag'], f_MHz=w['f']/1e6, vss_uV_rms=[round(a*1e6, 1) for a in vr],
                                   input_ref_dBm_25dB_rejection=[round(float(10*np.log10((a*10**(-25/20))**2/50*1e3+1e-30)), 1) for a in vr],
                                   rejection_needed_dB_for_m100dBm=[round(float(20*np.log10(max(a, 1e-12)/2.24e-6)), 1) for a in vr])
        res[f'{mo}|{v}'] = d
json.dump(res, open(f'out/e9_victims_v7_{tag}.json', 'w'), indent=1)
def f3(x): return ' / '.join(f'{a:.3g}' for a in x)
for k, d in res.items():
    print(f"== {k}: rail ripple rms {f3(d['rss_mV_rms'])} mV; worst-case sum {f3(d['sum_mV_pk'])} mV pk; bands (mV pk, worst line): " +
          '; '.join(f"{b} {f3(x)}" for b, x in d['band_max_mV_pk'].items() if x[2] > 0))
    print('   top lines: ' + '; '.join(f"{t['ag']}@{t['f_MHz']:g} {f3(t['rail_mV_pk'])}" for t in d['top'][:6]))
    for kk in ('psrr_needed_dB_for_m80dBc', 'jitter_ps_rms_unregulated', 'ring_dj_regulated_ps_pk', 'ring_dj_bypass_ps_pk', 'worst_aliasing_line', 'inband'):
        if kk in d: print(f'   {kk}: {d[kk]}')
