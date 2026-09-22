"""Cycle-local loaded replay diagnostics; no autonomous/noise qualification."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';e=P/'evidence/lo-interstage.json';d=json.loads(e.read_text());assert d['completed']
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
p=R/'scratch/transceiver-lo-interstage/replay.dat';r=json.loads((p.parent/'result.json').read_text());assert sha(p)==r['artifacts_sha256']['.dat']
with p.open() as f:header=f.readline().lower().split()
names=['v(oip)','v(oin)','v(oqp)','v(oqn)'];a=np.loadtxt(p,skiprows=1,usecols=[0]+[header.index(n) for n in names]);t=a[:,0];assert np.isfinite(a).all() and np.all(np.diff(t)>0)
def crossings(t,y,rising):
 k=np.flatnonzero((y[:-1]<1.65)&(y[1:]>=1.65) if rising else (y[:-1]>=1.65)&(y[1:]<1.65))
 return t[k]+(1.65-y[k])*np.diff(t)[k]/np.diff(y)[k]
rows=[]
for j,name in enumerate(names,1):
 y=a[:,j];up=crossings(t,y,True);down=crossings(t,y,False);up=up[(up>=512e-9)&(up<=1024e-9)];cycles=[]
 for start,end in zip(up[:-1],up[1:]):
  falls=down[(down>start)&(down<end)]
  assert len(falls)==1
  left,right=np.searchsorted(t,[start,end]);v=np.r_[1.65,y[left:right],1.65]
  cycles.append(dict(period_ps=float((end-start)*1e12),high_ps=float((falls[0]-start)*1e12),low_ps=float((end-falls[0])*1e12),duty=float((falls[0]-start)/(end-start)),peak_v=float(v.max()),trough_v=float(v.min())))
 row=dict(node=name,complete_cycles=len(cycles),metrics={k:dict(min=min(c[k] for c in cycles),max=max(c[k] for c in cycles)) for k in cycles[0]});rows.append(row)
out=dict(completed=True,source_evidence_sha256=sha(e),waveform_sha256=sha(p),threshold_v=1.65,window_ns=[512,1024],legs=rows,limitations=['Only complete threshold-defined cycles inside the window; partial boundary cycles excluded.','Voltage extrema and widths are diagnostics, not established mixer-drive acceptance limits.','Replay omits oscillator back-loading, phase-noise and startup variation.'])
(P/'evidence/lo-interstage-cycles.json').write_text(json.dumps(out,indent=2)+'\n')
for row in rows:print(row)
