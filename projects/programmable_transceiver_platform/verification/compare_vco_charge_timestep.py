"""Compare signed-minus-quiet responses using ordinal edges, without time alignment."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
reports=[P/'evidence'/n for n in ('vco-charge-kick.json','vco-charge-kick-fine.json')]
d=[json.loads(p.read_text()) for p in reports]
out=dict(completed=False,status='pending',report_sha256={p.name:sha(p) for p in reports},comparisons=[],limitations=['Two numerical resolutions do not prove convergence or silicon accuracy.','Output-buffer perturbation at one phase is not intrinsic oscillator noise.'])
if all(any(c['name']=='quiet' and c['completed'] for c in x['cases']) for x in d):
 edges=[];decks=[]
 for suffix,report in zip(('v2','fine'),d):
  root=R/'scratch'/('transceiver-vco-charge-kick-'+suffix);group={};sources={}
  for c in report['cases']:
   name=c['name']
   if not c['completed']:continue
   assert c['same_edge_count']
   for ext,h in c['artifacts_sha256'].items():assert sha(root/(name+ext))==h
   with (root/(name+'.dat')).open() as f:header=f.readline().lower().split()
   a=np.loadtxt(root/(name+'.dat'),skiprows=1);t=a[:,0];y=a[:,header.index('cml')];k=np.flatnonzero((y[:-1]<0)&(y[1:]>=0))
   group[name]=t[k]-y[k]*np.diff(t)[k]/np.diff(y)[k]
   sources[name]=(root/(name+'.spice')).read_text()
  edges.append(group);decks.append(sources)
 matched=set(edges[0]) & set(edges[1])
 for name in sorted(matched):
  assert decks[1][name].replace('tran .5p 41n 0 .5p uic','tran 2p 41n 0 2p uic')==decks[0][name]
  assert len(edges[0][name])==len(edges[1][name])
 for name in ('positive','negative'):
  if name not in matched:continue
  coarse=edges[0][name]-edges[0]['quiet'];fine=edges[1][name]-edges[1]['quiet'];base=edges[0]['quiet'];windows=[]
  for lo,hi in [(10,19),(20,21),(21,25),(30,40)]:
   mask=(base>=lo*1e-9)&(base<=hi*1e-9);assert mask.any()
   windows.append(dict(window_ns=[lo,hi],coarse_peak_ps=float(abs(coarse[mask]).max()*1e12),fine_peak_ps=float(abs(fine[mask]).max()*1e12),max_response_difference_ps=float(abs(fine[mask]-coarse[mask]).max()*1e12)))
  out['comparisons'].append(dict(case=name,windows=windows))
 out.update(completed=all(x['completed'] for x in d),status='matched_timestep_response_comparison' if all(x['completed'] for x in d) else 'partial_matched_timestep_response_comparison')
(P/'evidence/vco-charge-timestep.json').write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out['comparisons'])
