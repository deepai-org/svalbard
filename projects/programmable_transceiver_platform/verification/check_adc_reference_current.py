#!/usr/bin/env python3
"""Validate probe replay and reproduction before reference-current interpretation."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-adc-reference-current';B=R/'scratch/transceiver-adc-shared-iq-damping2k'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((W/'manifest.json').read_text());assert sha(W/'frames.spice')==m['deck_sha256_before']==m['preparation']['prepared_deck_sha256']
assert sha(B/'frames.spice')==m['preparation']['baseline_deck_sha256']
out=dict(status='pending',completed=False,reproduction_verified=False)
if (W/'result.json').exists():
 r=json.loads((W/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before']
 for ext,h in r['artifacts_sha256'].items():assert sha(W/('frames'+ext))==h
 br=json.loads((B/'result.json').read_text())
 for ext,h in br['artifacts_sha256'].items():assert sha(B/('frames'+ext))==h
 def read(p):
  with p.open() as f:h=f.readline().lower().split()
  a=np.loadtxt(p,skiprows=1);assert a.shape[1]==len(h) and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
  return h,a
 h,a=read(W/'frames.dat');bh,ba=read(B/'frames.dat');assert h[:len(bh)]==bh
 done=r['returncode']==0 and not r['timed_out'] and a[-1,0]+1e-21>=209.9e-9 and 'aborted' not in (W/'frames.log').read_text().lower()
 out.update(status='terminal',completed=bool(done),provenance=r,baseline_artifacts_sha256=br['artifacts_sha256'])
 if done:
  same_time=np.array_equal(a[:,0],ba[:,0]);errors={};passed=True
  for i,name in enumerate(bh[1:],1):
   baseline=ba[:,i] if same_time else np.interp(a[:,0],ba[:,0],ba[:,i])
   error=float(np.max(abs(a[:,i]-baseline)));limit=m['current_reproduction_tolerance_a'] if name.startswith('i(') else m['voltage_reproduction_tolerance_v']
   errors[name]=error;passed=passed and error<=limit
  out.update(same_time_grid=same_time,original_vector_max_errors=errors,reproduction_verified=bool(passed),voltage_tolerance_v=m['voltage_reproduction_tolerance_v'],current_tolerance_a=m['current_reproduction_tolerance_a'])
  sensor_errors={}
  for rail in ['h','l']:
   for suffix in ['drv','res']:
    x=a[:,h.index('v(v'+rail+suffix+')')]-a[:,h.index('v(v'+rail+')')]
    sensor_errors[rail+suffix]=float(abs(x).max())
  assert max(sensor_errors.values())<1e-9;out['zero_voltage_sensor_max_errors_v']=sensor_errors
out['limitations']=['Currents must not be interpreted as a matched replay until reproduction_verified.','If time grids differ comparison uses linear interpolation; no extrapolated horizon permitted by completion requirement.','Ideal biases/supplies and selected input histories remain; no reference qualification.']
(P/'evidence/adc-reference-current-replay.json').write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out['completed'],out['reproduction_verified'])
