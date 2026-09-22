"""Localize replay crossing gaps without equating a timing marker to conduction."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-lo-receiver-replay';E=P/'evidence/lo-receiver-replay.json'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(1048576),b''):h.update(x)
 return h.hexdigest()
e=json.loads(E.read_text());out=dict(completed=False,status='pending',parent_check_sha256=sha(E),legs=[])
def crossings(t,y,threshold):
 k=np.flatnonzero((y[:-1]<threshold)&(y[1:]>=threshold));return t[k]+(threshold-y[k])*np.diff(t)[k]/np.diff(y)[k]
# Known triangle crossings validate direction, interpolation and threshold handling.
assert np.array_equal(crossings(np.arange(5.),np.array([0.,2.,0.,2.,0.]),1.),np.array([.5,2.5]))
if e['completed']:
 for ext,h in e['artifacts_sha256'].items():assert sha(W/('replay'+ext))==h
 with (W/'replay.dat').open() as f:h=f.readline().lower().split()
 a=np.loadtxt(W/'replay.dat',skiprows=1);t=a[:,0];assert a.shape[1]==len(h) and np.isfinite(a).all() and np.all(np.diff(t)>0) and t[-1]+1e-21>=1024e-9
 mask=(t>=512e-9)&(t<=1024e-9)
 for leg in ('ip','in','qp','qn'):
  nodes=[]
  for node in ('v(b'+leg+')','v(xb'+leg+'.mid)','v(pre'+leg+')','v(o'+leg+')'):
   y=a[:,h.index(node)];markers=[]
   for threshold in (1.530318,1.65):
    edges=crossings(t,y,threshold);edges=edges[(edges>=512e-9)&(edges<=1024e-9)];periods=np.diff(edges);gaps=np.flatnonzero(periods>800e-12)
    markers.append(dict(threshold_v=threshold,rising_edges=len(edges),max_interval_ps=float(periods.max()*1e12) if len(periods) else None,long_intervals_ns=[[float(edges[k]*1e9),float(edges[k+1]*1e9)] for k in gaps]))
   nodes.append(dict(node=node,range_v=[float(y[mask].min()),float(y[mask].max())],markers=markers))
  out['legs'].append(dict(leg=leg,nodes=nodes))
 out.update(completed=True,status='replay_only_stage_diagnostics',parent_replay_use_approved=e['diagnostic_use_approved'])
out['limitations']=['Replay-only stage diagnostics; reproduction approval remains separate and cannot be inferred from completion.', 'Markers are timing observations, not physical switching/conduction thresholds; phase-bin migration and threshold choice matter.', 'Missing saved parent MID/PRE prevents direct parent comparison for those nodes.']
(P/'evidence/lo-replay-stages.json').write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out['completed'])
