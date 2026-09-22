#!/usr/bin/env python3
"""Matched pre-failure analog loading; no completed-conversion claim."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-rx-adc-loading'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rows=[]
for case in ('loaded','isolated'):
 root=W/case;r=json.loads((root/'result.json').read_text());assert r['returncode']==1 and not r['timed_out'] and r['sources_before']==r['sources_after']
 for ext,h in r['artifacts_sha256'].items():assert sha(root/('connected'+ext))==h
 with (root/'connected.dat').open() as f:h=f.readline().lower().split()
 a=np.loadtxt(root/'connected.dat',skiprows=1);t=a[:,0];assert np.isfinite(a).all() and np.all(np.diff(t)>=0)
 fits=[]
 for lo,hi in [(240,400),(300,460)]:
  mask=(t>=lo*1e-9)&(t<=hi*1e-9);tw=t[mask];assert len(tw)>100 and np.all(np.diff(tw)>0)
  def v(n):return a[mask,h.index(n)]
  osc=v('v(xrx.p)')-v('v(xrx.n)');k=np.flatnonzero((osc[:-1]<0)&(osc[1:]>=0));assert len(k)>100
  edges=tw[k]-osc[k]*np.diff(tw)[k]/np.diff(osc)[k];flo=float((len(edges)-1)/(edges[-1]-edges[0]));fif=2.51542263e9-flo;assert fif>0
  # Time weighting and centered trend; harmonics distinguish LO leakage from IF.
  weights=np.r_[np.diff(tw)[0]/2,(tw[2:]-tw[:-2])/2,np.diff(tw)[-1]/2];weights/=weights.mean()
  freqs=[fif,flo,2*flo,3*flo,4*flo,2.51542263e9]
  X=np.column_stack([np.ones(len(tw)),(tw-tw.mean())/(tw[-1]-tw[0])]+[f(2*np.pi*freq*tw) for freq in freqs for f in (np.cos,np.sin)])
  channels={}
  for channel in ('i','q'):
   y=v(f'v(f{channel}p)')-v(f'v(f{channel}n)');beta=np.linalg.lstsq(X*np.sqrt(weights[:,None]),y*np.sqrt(weights),rcond=None)[0];res=y-X@beta
   channels[channel]=dict(if_peak_v=float(np.hypot(beta[2],beta[3])),if_phase_rad=float(np.arctan2(-beta[3],beta[2])),mean_common_mode_v=float(np.average((v(f'v(f{channel}p)')+v(f'v(f{channel}n)'))/2,weights=weights)),residual_rms_v=float(np.sqrt(np.average(res*res,weights=weights))))
  fits.append(dict(window_ns=[lo,hi],lo_hz=flo,if_hz=fif,if_cycles=float(fif*(tw[-1]-tw[0])),channels=channels))
 rows.append(dict(case=case,artifacts_sha256=r['artifacts_sha256'],fits=fits))
comparison=[]
for a,b in zip(rows[0]['fits'],rows[1]['fits']):
 comparison.append(dict(window_ns=a['window_ns'],lo_change_hz=a['lo_hz']-b['lo_hz'],loaded_over_isolated_amplitude={c:a['channels'][c]['if_peak_v']/b['channels'][c]['if_peak_v'] for c in ('i','q')}))
out=dict(status='partial_history_loading_diagnostic',completed_conversion=False,cases=rows,comparison=comparison,limitations=['Both full runs failed478.5ns; windows precede first hold470ns and do not verify repeated acquisition.','Only about3.2IF cycles/window; residual includes leakage/transients and is not noise or ENOB.','Ideal isolation changes back-loading; result does not qualify actual isolation hardware.','Inherited IF aliases near DC at ADC rate; no sampled-signal quality claim.'])
(P/'evidence/rx-adc-partial-loading.json').write_text(json.dumps(out,indent=2)+'\n')
print(comparison)
for r in rows:print(r['case'],[(f['window_ns'],{c:x['if_peak_v'] for c,x in f['channels'].items()}) for f in r['fits']])
