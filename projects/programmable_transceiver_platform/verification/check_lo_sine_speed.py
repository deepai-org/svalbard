"""Ideal-source LO chain timing diagnostics, not actual receiver reproduction."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-lo-sine-speed'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
out=dict(completed=False,status='pending',cases=[])
if (W/'result.json').exists():
 r=json.loads((W/'result.json').read_text());assert r['sources_before']==r['sources_after'];out['status']='terminal'
 for c in r['cases']:
  n=c['name'];row=dict(name=n,completed=False);out['cases'].append(row)
  for ext,h in c['artifacts_sha256'].items():assert sha(W/(n+ext))==h
  errors=[l for l in (W/(n+'.log')).read_text().splitlines() if any(k in l.lower() for k in ('error','warning','aborted'))];row.update(returncode=c['returncode'],errors=errors,artifacts_sha256=c['artifacts_sha256'])
  if c['returncode']!=0 or errors:continue
  with (W/(n+'.dat')).open() as f:h=f.readline().lower().split()
  assert h==['time','v(in)','v(xb.mid)','v(pre)','v(out)','i(vdd)'];a=np.loadtxt(W/(n+'.dat'),skiprows=1);t=a[:,0];assert np.isfinite(a).all() and np.all(np.diff(t)>0)
  if t[-1]+1e-21<100e-9:continue
  signals={};mask=(t>=50e-9)&(t<=100e-9)
  for col,node in ((1,'input'),(2,'mid'),(3,'pre'),(4,'output')):
   threshold=1.530318 if col==1 else 1.65;y=a[:,col];k=np.flatnonzero((y[:-1]<threshold)&(y[1:]>=threshold));edges=t[k]+(threshold-y[k])*np.diff(t)[k]/np.diff(y)[k];edges=edges[(edges>=50e-9)&(edges<=100e-9)]
   signals[node]=dict(range_v=[float(y[mask].min()),float(y[mask].max())],rises=len(edges),period_range_ps=[float(np.diff(edges).min()*1e12),float(np.diff(edges).max()*1e12)] if len(edges)>1 else None)
  row.update(completed=True,signals=signals)
 out['completed']=len(out['cases'])==2 and all(c['completed'] for c in out['cases'])
out['limitations']=['Ideal sinusoidal source with fixed bias and50fF output only; no AC coupling/self-bias/mixer loading or actual ring modulation.', 'Passing this screen cannot qualify the autonomous receiver or identify a unique cause of its missing pulses.']
(P/'evidence/lo-sine-speed.json').write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out['completed']);print(out['cases'])
