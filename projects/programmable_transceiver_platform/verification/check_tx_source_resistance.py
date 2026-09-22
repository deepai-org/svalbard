#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-tx-source-resistance';B=R/'scratch/transceiver-tx-buffered-lo'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
if not (W/'result.json').exists():
 print('Pending terminal result; no completed comparison claimed.');raise SystemExit(0)
m=json.loads((W/'manifest.json').read_text());r=json.loads((W/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before']
assert [c['name'] for c in r['cases']]==['nmos_r50','nmos_r500','tg_r50','tg_r500'];rows=[]
for c in r['cases']:
 name=c['name'];baseline=c['baseline'];src=B/(baseline+'.spice');assert sha(src)==c['baseline_deck_sha256'];d=(W/(name+'.spice')).read_text();res=c['resistance_ohm'];assert res in (50,500)
 add=f'RSP LOSRC LOIN {res}\nRSN LOBSRC LOBIN {res}\n';assert d.count(add)==1
 restored=d.replace(add,'').replace('VLO LOSRC 0 PULSE','VLO LOIN 0 PULSE').replace('VLOB LOBSRC 0 PULSE','VLOB LOBIN 0 PULSE').replace('/work/'+name+'.dat','/work/'+baseline+'.dat');assert restored==src.read_text()
 assert sha(W/(name+'.spice'))==c['deck_sha256_before']
 for ext,h in c['artifacts_sha256'].items():assert sha(W/(name+ext))==h
 assert c['returncode']==0 and not c['timed_out'] and 'aborted' not in (W/(name+'.log')).read_text().lower()
 with (W/(name+'.dat')).open() as f:h=f.readline().lower().split()
 assert h==['time']+'v(op) v(on) v(rfp) v(rfn) v(lo) v(lob) i(vlo) i(vlob) i(vdd) i(vdrv) v(loin) v(lobin) i(vlobuf)'.split()
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert np.isfinite(a).all() and a.shape[1]==len(h) and np.all(np.diff(a[:,0])>0) and a[-1,0]>=10e-9
 t=np.r_[6e-9,a[(a[:,0]>6e-9)&(a[:,0]<10e-9),0],10e-9]
 def v(k):return np.interp(t,a[:,0],a[:,h.index(k)])
 def integ(y):return float(np.trapezoid(y,t))
 rf=v('v(rfp)')-v('v(rfn)');w=2*np.pi*2.5e9;fund=2/4e-9*abs(integ(rf*np.cos(w*t))+1j*integ(rf*np.sin(w*t)))
 supply=-v('i(vlobuf)')
 rows.append(dict(name=name,completed=True,input_range_v=[float(v('v(loin)').min()),float(v('v(loin)').max())],rf_fundamental_peak_v=float(fund),lo_range_v=[float(v('v(lo)').min()),float(v('v(lo)').max())],lob_range_v=[float(v('v(lob)').min()),float(v('v(lob)').max())],lo_complement_sum_error_peak_v=float(abs(v('v(lo)')+v('v(lob)')-3.3).max()),buffer_pair_average_current_a=integ(supply)/4e-9,buffer_pair_peak_current_a=float(supply.max()),buffer_pair_average_supply_power_w=3.3*integ(supply)/4e-9,input_sources_peak_absolute_current_a=max(float(np.max(np.abs(v('i(vlo)')))),float(np.max(np.abs(v('i(vlob)')))))))

out=dict(status='completed_source_resistance_diagnostic',cases=rows,provenance=r,limitations=['50/500ohm source scenarios do not emulate or bound an actual oscillator; no autonomous timing or phase-noise qualification.', 'Separate ideal buffer supply; no shared-supply/package coupling or layout.', 'Fixed codes and one load scenario, nominal model only; no EVM, modulated spectrum or timestep convergence claim.'])
(P/'evidence/tx-source-resistance.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(rows,indent=2))
