"""Receiver replay reproduction diagnostics, with no time realignment or inferred pass."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
ap=argparse.ArgumentParser();ap.add_argument('--self-check',action='store_true');args=ap.parse_args()
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';B=R/'scratch/transceiver-lo-receiver-replay-prepared';W=R/'scratch/transceiver-lo-receiver-replay'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(1048576),b''):h.update(x)
 return h.hexdigest()
m=json.loads((B/'manifest.json').read_text())
for n,h in m['artifacts_sha256'].items():assert sha(B/n)==h
ref=np.load(B/'parent_samples.npy');rh=m['sample_columns'];assert ref.shape[1]==len(rh) and np.isfinite(ref).all() and np.all(np.diff(ref[:,0])>0)
def compare(a,h):
 t=a[:,0];mask=(t>=max(512e-9,ref[0,0]))&(t<=min(1024e-9,ref[-1,0]));tt=t[mask];assert len(tt)>2 and ref[0,0]<=tt[0] and ref[-1,0]>=tt[-1]
 nodes={}
 def edges(t,y):
  k=np.flatnonzero((y[:-1]<1.65)&(y[1:]>=1.65));return t[k]+(1.65-y[k])*np.diff(t)[k]/np.diff(y)[k]
 for n in rh[1:]:
  yy=a[:,h.index(n)];base=ref[:,rh.index(n)];delta=yy[mask]-np.interp(tt,ref[:,0],base)
  item=dict(max_abs_difference_v=float(abs(delta).max()),time_weighted_rms_difference_v=float(np.sqrt(np.trapezoid(delta**2,tt)/(tt[-1]-tt[0]))))
  if n in ('v(oip)','v(oin)','v(oqp)','v(oqn)'):
   x=edges(t,yy);z=edges(ref[:,0],base);x=x[(x>=512e-9)&(x<=1024e-9)];z=z[(z>=512e-9)&(z<=1024e-9)]
   item.update(replay_rises=len(x),parent_rises=len(z),ordinal_max_displacement_ps=float(abs(x-z).max()*1e12) if len(x)==len(z) and len(x) else None)
  nodes[n]=item
 return nodes
out=dict(completed=False,status='pending',preparation_sha256=sha(B/'manifest.json'),diagnostic_use_approved=False)
if args.self_check:
 nodes=compare(ref,rh);assert all(x['max_abs_difference_v']==0 for x in nodes.values());out.update(completed=True,status='parent_self_comparison_only',nodes=nodes)
elif (W/'result.json').exists():
 r=json.loads((W/'result.json').read_text());assert r['sources_before']==r['sources_after']
 for ext,h in r['artifacts_sha256'].items():assert sha(W/('replay'+ext))==h
 assert (W/'replay.spice').read_text()==(B/'replay.spice').read_text()
 errors=[x.strip() for x in (W/'replay.log').read_text().splitlines() if any(k in x.lower() for k in ('warning','error','aborted','timestep too small'))]
 out.update(status='terminal',returncode=r['returncode'],timed_out=r['timed_out'],errors=errors,artifacts_sha256=r['artifacts_sha256'])
 if (W/'replay.dat').exists():
  with (W/'replay.dat').open() as f:h=f.readline().lower().split()
  a=np.loadtxt(W/'replay.dat',skiprows=1);assert a.shape[1]==len(h) and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
  out['actual_stop_ns']=float(a[-1,0]*1e9)
  if r['returncode']==0 and not r['timed_out'] and not errors and a[-1,0]+1e-21>=1024e-9:out.update(completed=True,nodes=compare(a,h))
out['limitations']=['Completion and self-check do not approve replay accuracy; inspect deviations and missing events before use.', 'No time shifts or nearest-edge rematching; unequal counts prevent ordinal displacement claims.', 'Removed feedback/loading and incomplete internal initialization remain explicit fixture differences.']
(P/'evidence'/('lo-receiver-replay-self-check.json' if args.self_check else 'lo-receiver-replay.json')).write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out['completed'])
