"""Native-grid LO threshold crossings; no transistor conduction claim."""
import argparse,hashlib,json
ap=argparse.ArgumentParser();ap.add_argument("--upstream",action="store_true");args=ap.parse_args()
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-latest-rf-loop-selective';E=P/'evidence/latest-rf-loop-selective.json'
e=json.loads(E.read_text());assert e['completed'];digest=hashlib.sha256();rows=[]
names=['v(oip)','v(oin)','v(oqp)','v(oqn)','v(p)','v(n)']
if args.upstream:names+=['v(bip)','v(bin)','v(bqp)','v(bqn)','v(ip)','v(in)','v(qp)','v(qn)']
with (W/'latest.dat').open('rb') as f:
 header=f.readline();digest.update(header);h=header.decode().lower().split();cols=[0]+[h.index(n) for n in names]
 for line in f:
  digest.update(line)
  if float(line.split(None,1)[0])<7.423e-6:continue
  parts=line.split();assert len(parts)==len(h);rows.append([float(parts[k]) for k in cols])
assert digest.hexdigest()==e['provenance']['artifacts_sha256']['.dat'];a=np.array(rows);t=a[:,0];assert np.isfinite(a).all() and np.all(np.diff(t)>0)
def crossing(y,level,up):
 k=np.flatnonzero(((y[:-1]<level)&(y[1:]>=level)) if up else ((y[:-1]>level)&(y[1:]<=level)))
 return t[k]+(level-y[k])*np.diff(t)[k]/np.diff(y)[k]
out=dict(completed=True,waveform_sha256=digest.hexdigest(),window_ns=[7424,7936],signals=[])
for i,n in enumerate(names[:4],1):
 y=a[:,i];rise=crossing(y,1.65,True);fall=crossing(y,1.65,False);cycles=[]
 for lo,hi in zip(rise[:-1],rise[1:]):
  if lo<7424e-9 or hi>7936e-9:continue
  f=fall[(fall>lo)&(fall<hi)];cycles.append(dict(start_ns=float(lo*1e9),period_ps=float((hi-lo)*1e12),fall_count=len(f),high_fraction=float((f[0]-lo)/(hi-lo)) if len(f)==1 else None))
 good=[x for x in cycles if x['high_fraction'] is not None];assert good
 periods=[x['period_ps'] for x in good];duty=[x['high_fraction'] for x in good]
 out['signals'].append(dict(node=n,cycles=len(cycles),cycles_with_nonunique_fall=len(cycles)-len(good),period_range_ps=[min(periods),max(periods)],duty_range=[min(duty),max(duty)],cycle_records=cycles))
if args.upstream:
 ring=crossing(a[:,5]-a[:,6],0,True);periods=np.diff(ring);keep=(ring[:-1]>=7424e-9)&(ring[1:]<=7936e-9)
 out['ring_control']=dict(cycles=int(keep.sum()),period_range_ps=[float(periods[keep].min()*1e12),float(periods[keep].max()*1e12)])
 gaps=[]
 for row in out['signals']:
  node=row['node'];suffix=node[3:-1]
  for cycle in row['cycle_records']:
   if cycle['period_ps']<=800:continue
   lo=cycle['start_ns']*1e-9;hi=lo+cycle['period_ps']*1e-12;mask=(t>=lo)&(t<=hi)
   obs={}
   for n in ('v(b'+suffix+')','v('+suffix+')',node):
    y=a[:,1+names.index(n)];yy=y[mask];assert len(yy)>1
    obs[n]=dict(min_v=float(yy.min()),max_v=float(yy.max()),mean_v=float(np.trapezoid(yy,t[mask])/(t[mask][-1]-t[mask][0])))
   gaps.append(dict(output=node,window_ns=[lo*1e9,hi*1e9],ring_rises_inside=int(((ring>lo)&(ring<hi)).sum()),nodes=obs))
 out['long_gaps_over_two_nominal_periods']=gaps
out['limitations']=['1.65V is a timing marker, not a mixer conduction threshold.', 'Native exported waveform with linear crossing interpolation; no extra SPICE timestep convergence demonstrated.', 'Large period gaps indicate missing threshold crossings, not necessarily stopped oscillator or physical logic errors.']
(P/'evidence'/('latest-lo-upstream.json' if args.upstream else 'latest-lo-edges.json')).write_text(json.dumps(out,indent=2)+'\n')
for x in out['signals']:print({k:v for k,v in x.items() if k!='cycle_records'})

if args.upstream:print('ring',out['ring_control']);print('long gaps',len(gaps));print('first gaps',gaps[:2])
