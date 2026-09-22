#!/usr/bin/env python3
"""Reproduce idle and signed excess-energy comparison from the pulse fixtures."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';rows=[]
for variant,folder in [('baseline','transceiver-reference-load-step'),('output2','transceiver-reference-output2-step')]:
 W=R/'scratch'/folder;r=json.loads((W/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after']
 for c in r['cases']:
  p=W/(c['name']+'.dat');assert hashlib.sha256(p.read_bytes()).hexdigest()==c['artifacts_sha256']['.dat']
  with p.open() as f:assert f.readline().lower().split()==['time','v(out)','v(xbuf.x)','v(xbuf.t)','i(vdd)','v(target)']
  a=np.loadtxt(p,skiprows=1);assert np.isfinite(a).all() and a[-1,0]>=200e-9;t=a[:,0];i=-a[:,4]
  pre=(t>=10e-9)&(t<=19e-9);event=(t>=20e-9)&(t<=100e-9);idle=np.trapezoid(i[pre],t[pre])/(t[pre][-1]-t[pre][0])
  rows.append(dict(variant=variant,name=c['name'],idle_current_ma=float(idle*1e3),idle_power_mw=float(3.3*idle*1e3),event_window_ns=[20,100],excess_supply_energy_pj=float(3.3*np.trapezoid(i[event]-idle,t[event])*1e12),waveform_sha256=c['artifacts_sha256']['.dat']))
out=dict(status='measured_reference_loadstep_supply_tradeoff',cases=rows,limitations=['Excess energy is signed ideal-supply energy above unloaded baseline, not total dissipated heat.', 'Pulse response not repeated ADC duty cycle or full-chip supply/coexistence verification.'])
(P/'evidence/reference-output2-power-comparison.json').write_text(json.dumps(out,indent=2)+'\n')
print('Verified',len(rows),'pulse power records')
