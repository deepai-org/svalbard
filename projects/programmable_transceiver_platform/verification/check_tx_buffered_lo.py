#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-tx-buffered-lo';B=R/'scratch/transceiver-tx-lo-switching'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((W/'manifest.json').read_text());r=json.loads((W/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before']
assert [c['name'] for c in r['cases']]==['nmos_c128','nmos_c255','tg_c128','tg_c255'];rows=[]
add='.include /screen/lo_buffer.spice\nVLOBUF VLOBUF 0 3.3\nXLP LOIN LO VLOBUF 0 pt_lo_buffer S=1\nXLN LOBIN LOB VLOBUF 0 pt_lo_buffer S=1\n';extra='v(LOIN) v(LOBIN) i(VLOBUF)';assert m['extra_vectors']==extra
for c in r['cases']:
 name=c['name'];src=B/(name+'.spice');assert sha(src)==c['baseline_deck_sha256'];d=(W/(name+'.spice')).read_text();assert d.count(add)==1
 restored=d.replace(add,'').replace('VLO LOIN 0 PULSE','VLO LO 0 PULSE').replace('VLOB LOBIN 0 PULSE','VLOB LOB 0 PULSE').replace(' '+extra+'\n','\n');assert restored==src.read_text()
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
 rows.append(dict(name=name,completed=True,rf_fundamental_peak_v=float(fund),lo_range_v=[float(v('v(lo)').min()),float(v('v(lo)').max())],lob_range_v=[float(v('v(lob)').min()),float(v('v(lob)').max())],lo_complement_sum_error_peak_v=float(abs(v('v(lo)')+v('v(lob)')-3.3).max()),buffer_pair_average_current_a=integ(supply)/4e-9,buffer_pair_peak_current_a=float(supply.max()),buffer_pair_average_supply_power_w=3.3*integ(supply)/4e-9,input_sources_peak_absolute_current_a=max(float(np.max(np.abs(v('i(vlo)')))),float(np.max(np.abs(v('i(vlob)')))))))

out=dict(status='completed_buffered_LO_diagnostic',cases=rows,provenance=r,limitations=['Two ideal complementary full-rail clocks still drive buffer inputs; no oscillator, quadrature or phase-noise qualification.', 'Separate ideal buffer supply; no shared-supply/package coupling or layout.', 'Fixed codes and one load scenario, nominal model only; no EVM, modulated spectrum or timestep convergence claim.'])
(P/'evidence/tx-buffered-lo.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(rows,indent=2))
