"""Completion and matched diagnostic metrics for the second-inverter experiment."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
ap=argparse.ArgumentParser();ap.add_argument('--baseline-check',action='store_true');ap.add_argument('--half',action='store_true');ap.add_argument('--feedback',choices=['30k','300k']);ap.add_argument('--interstage',action='store_true');args=ap.parse_args()
assert sum(bool(x) for x in (args.half,args.feedback,args.interstage,args.baseline_check))<=1
assert not (args.half and args.feedback)
assert not (args.baseline_check and args.feedback)
name='lo-interstage' if args.interstage else 'lo-feedback-'+args.feedback if args.feedback else 'lo-second-stage-half' if args.half else 'lo-second-stage'
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
W=R/f'scratch/transceiver-{name}';B=R/f'scratch/transceiver-{name}-prepared'
BASE=R/'scratch/transceiver-lo-receiver-replay'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(1048576),b''):h.update(block)
 return h.hexdigest()
def rises(t,y,level):
 k=np.flatnonzero((y[:-1]<level)&(y[1:]>=level))
 return t[k]+(level-y[k])*np.diff(t)[k]/np.diff(y)[k]
assert np.array_equal(rises(np.arange(5.),np.array([0.,2.,0.,2.,0.]),1.),[.5,2.5])
def metrics(path):
 with path.open() as f:h=f.readline().lower().split()
 a=np.asfortranarray(np.loadtxt(path,skiprows=1));t=a[:,0]
 assert a.shape[1]==len(h) and np.isfinite(a).all() and np.all(np.diff(t)>0)
 assert t[-1]+1e-21>=1024e-9
 mask=(t>=512e-9)&(t<=1024e-9);tt=t[mask]
 out={'stop_ns':float(t[-1]*1e9),'nodes':{},'baseband':{}}
 for leg in ('ip','in','qp','qn'):
  for name,level in [(f'v(b{leg})',1.530318),(f'v(xb{leg}.mid)',1.530318),(f'v(pre{leg})',1.530318),(f'v(o{leg})',1.65)]:
   y=a[:,h.index(name)];v=y[mask];e=rises(t,y,level);e=e[(e>=512e-9)&(e<=1024e-9)];dt=np.diff(e)
   out['nodes'][name]=dict(marker_v=level,rises=len(e),intervals_over_800ps=int(np.sum(dt>800e-12)),max_interval_ps=float(dt.max()*1e12) if len(dt) else None,min_v=float(v.min()),max_v=float(v.max()),mean_v=float(np.trapezoid(v,tt)/(tt[-1]-tt[0])))
 for leg in ('i','q'):
  v=a[mask,h.index(f'v(f{leg}p)')]-a[mask,h.index(f'v(f{leg}n)')]
  mean=np.trapezoid(v,tt)/(tt[-1]-tt[0]);angle=2*np.pi*19.53125e6*tt
  coef=2*np.trapezoid((v-mean)*np.exp(-1j*angle),tt)/(tt[-1]-tt[0])
  out['baseband'][leg]=dict(mean_v=float(mean),peak_to_peak_v=float(np.ptp(v)),reference_fundamental_peak_v=float(abs(coef)))
 if 'i(vbuf)' in h:
  current=a[mask,h.index('i(vbuf)')]
  out['buffer_supply_current_a']=dict(mean_source_current=float(np.trapezoid(current,tt)/(tt[-1]-tt[0])),min=float(current.min()),max=float(current.max()))
  out['local_bias_v']={leg:dict(min=float(a[mask,h.index(f'v(xb{leg}.local)')].min()),max=float(a[mask,h.index(f'v(xb{leg}.local)')].max())) for leg in ('ip','in','qp','qn')}
 return out
m=json.loads((B/'manifest.json').read_text())
for n,h in m['artifacts_sha256'].items():assert sha(B/n)==h
if args.interstage:
 cell=(P/'analog/lo_buffer.spice').read_text()
 changed=cell.replace('XP2 OUT MID','XCISO MID LOCAL pt_ref_reservoir_4\nRLOCAL LOCAL OUT 10k\nXP2 OUT LOCAL').replace('XN2 OUT MID','XN2 OUT LOCAL').rstrip()
 extra=' v(XBIP.LOCAL) v(XBIN.LOCAL) v(XBQP.LOCAL) v(XBQN.LOCAL) i(VBUF)'
 restored=(B/'replay.spice').read_text().replace(changed,'.include /screen/lo_buffer.spice')
 lines=restored.splitlines()
 for line in lines:
  if line.startswith(('save ','wrdata ')):assert line.endswith(extra)
 restored='\n'.join(line[:-len(extra)] if line.startswith(('save ','wrdata ')) else line for line in lines)+'\n'
 assert restored==(BASE/'replay.spice').read_text()
elif args.feedback:
 restored=(B/'replay.spice').read_text()
 for leg in ['IP','IN','QP','QN']:
  needle=f'RFB{leg} B{leg} XB{leg}.MID {args.feedback}'
  assert restored.count(needle)==1
  restored=restored.replace(needle,needle.replace(args.feedback,'100k'))
 assert restored==(BASE/'replay.spice').read_text()
else:
 cell=(P/'analog/lo_buffer.spice').read_text();changed=cell.replace('m={4*S}','m={2*S}' if args.half else 'm={8*S}').rstrip()
 assert (B/'replay.spice').read_text().replace(changed,'.include /screen/lo_buffer.spice')==(BASE/'replay.spice').read_text()
out={'completed':False,'status':'pending','preparation_sha256':sha(B/'manifest.json'),'adopted':False}
if args.baseline_check:
 old=json.loads((P/'evidence/lo-receiver-replay.json').read_text());assert old['completed']
 assert sha(BASE/'replay.dat')==old['artifacts_sha256']['.dat']
 measured=metrics(BASE/'replay.dat')
 stages=json.loads((P/'evidence/lo-replay-stages.json').read_text());assert stages['completed']
 for leg in stages['legs']:
  for n in leg['nodes']:
   v=measured['nodes'][n['node']];marker=next(x for x in n['markers'] if x['threshold_v']==v['marker_v'])
   assert v['rises']==marker['rising_edges']
   assert v['intervals_over_800ps']==len(marker['long_intervals_ns'])
   assert v['max_interval_ps']==marker['max_interval_ps']
   assert [v['min_v'],v['max_v']]==n['range_v']
 out.update(completed=True,status='baseline_metrics_cross_checked',baseline=measured)
elif (W/'result.json').exists():
 r=json.loads((W/'result.json').read_text());assert r['sources_before']==r['sources_after']
 assert (W/'replay.spice').read_bytes()==(B/'replay.spice').read_bytes()
 for ext,h in r['artifacts_sha256'].items():assert sha(W/('replay'+ext))==h
 errors=[l.strip() for l in (W/'replay.log').read_text().splitlines() if any(x in l.lower() for x in ('warning','error','aborted','timestep too small'))]
 out.update(status='terminal',returncode=r['returncode'],timed_out=r['timed_out'],errors=errors,result_sha256=sha(W/'result.json'))
 assert {'.spice','.log','.dat'} <= set(r['artifacts_sha256']) or r['returncode'] != 0 or r['timed_out']
 if r['returncode']==0 and not r['timed_out'] and not errors:
  old=json.loads((P/'evidence/lo-receiver-replay.json').read_text());assert old['completed']
  assert sha(BASE/'replay.dat')==old['artifacts_sha256']['.dat']
  out.update(completed=True,baseline=metrics(BASE/'replay.dat'),candidate=metrics(W/'replay.dat'))
out['limitations']=['Metrics are diagnostics, not automatic acceptance.', 'Replay omits autonomous feedback; MID/PRE parent identity unverified.', 'Baseline supply current was not saved: comparative power remains unmeasured.', 'Ranges do not prove pulse duty or amplitude on every cycle; follow up promising changes with cycle-local analysis.']
(P/'evidence'/('lo-second-stage-baseline-check.json' if args.baseline_check else name+'.json')).write_text(json.dumps(out,indent=2)+'\n')
print(out['status'],out['completed'])
