#!/usr/bin/env python3
"""Local sampling-time sensitivity on always-tracking diagnostic waveforms."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';rows=[];hashes={}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for case in ('loaded-driver','loaded-driver-damping','loaded-driver-damping2k'):
 w=R/('scratch/transceiver-adc-'+case);r=json.loads((w/'result.json').read_text());assert r['returncode']==0 and not r['timed_out'] and r['source_sha256_before']==r['source_sha256_after']
 for ext,h in r['artifacts_sha256'].items():assert sha(w/('loaded'+ext))==h
 hashes[case]=r['artifacts_sha256']
 with (w/'loaded.dat').open() as f:h=f.readline().lower().split()
 a=np.loadtxt(w/'loaded.dat',skiprows=1);t=a[:,0]*1e9
 assert np.isfinite(a).all() and np.all(np.diff(t)>0) and t[-1]>=100-1e-10
 y=a[:,h.index('v(hp)')]-a[:,h.index('v(hn)')]
 for start,target in [(60,-.4),(80,.4)]:
  center=start+10;nominal=float(np.interp(center,t,y));windows=[]
  for radius in (.1,.5,1.):
   lo,hi=center-radius,center+radius
   ts=np.r_[lo,t[(t>lo)&(t<hi)],hi];ys=np.interp(ts,t,y)
   windows.append(dict(radius_ns=radius,plate_range_v=[float(ys.min()),float(ys.max())],max_absolute_target_error_v=float(abs(ys-target).max()),max_change_from_nominal_v=float(abs(ys-nominal).max()),endpoint_secant_v_per_ns=float((ys[-1]-ys[0])/(2*radius))))
  rows.append(dict(case=case,step_ns=start,nominal_time_ns=center,target_v=target,nominal_plate_v=nominal,nominal_error_v=nominal-target,windows=windows))
out=dict(status='verified_saved_waveform_time_sensitivity',cases=rows,artifacts_sha256=hashes,limitations=['Always-on sampler; hypothetical observation times, not actual clock-edge perturbations or aperture-jitter simulation.','Selected symmetric timing neighborhoods are diagnostic scenarios, not guaranteed clock uncertainty bounds.','No physical hold feedthrough, conversion switching or RF-filter source impedance in this reduction.','Secant is deterministic trajectory slope, not intrinsic noise.'])
(P/'evidence/adc-aperture-neighborhood.json').write_text(json.dumps(out,indent=2)+'\n')
for r in rows:print(r['case'],r['step_ns'],'nominal_mV',r['nominal_error_v']*1e3,'max_error_mV',[round(w['max_absolute_target_error_v']*1e3,3) for w in r['windows']])
