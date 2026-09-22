"""Predeclared short-SAR reproduction checks; never accept incomplete outputs."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
parser=argparse.ArgumentParser();parser.add_argument('--replay',action='store_true');args=parser.parse_args();name='replay' if args.replay else 'baseline'
W=R/('scratch/transceiver-sar-command-'+name);B=R/'scratch/transceiver-sar-command-replay-prepared'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def edges(t,y,rising):
 mask=(y[:-1]<1.65)&(y[1:]>=1.65) if rising else (y[:-1]>=1.65)&(y[1:]<1.65)
 k=np.flatnonzero(mask);e=t[k]+(1.65-y[k])*np.diff(t)[k]/np.diff(y)[k]
 return e[(e>=70e-9)&(e<=79e-9)]
def read(path):
 with path.open() as f:h=f.readline().lower().split()
 a=np.loadtxt(path,skiprows=1);assert a.shape[1]==len(h) and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
 return h,a
m=json.loads((B/'manifest.json').read_text())
for f,h in m['artifacts_sha256'].items():assert sha(B/f)==h
out=dict(status='pending',completed=False,reproduction_pass=False,voltage_limit_v=10e-6,edge_limit_s=10e-12,preparation_sha256=sha(B/'manifest.json'))
if (W/'result.json').exists():
 r=json.loads((W/'result.json').read_text());assert r['sources_before']==r['sources_after']
 assert (W/(name+'.spice')).read_bytes()==(B/(name+'.spice')).read_bytes()
 for ext,h in r['artifacts_sha256'].items():assert sha(W/(name+ext))==h
 log=(W/(name+'.log')).read_text().lower();errors=[line for line in log.splitlines() if any(x in line for x in ['error','warning','aborted','timestep too small'])]
 out.update(status='terminal',returncode=r['returncode'],timed_out=r['timed_out'],errors=errors,result_sha256=sha(W/'result.json'))
 if r['returncode']==0 and not r['timed_out'] and not errors:
  assert {'.spice','.log','.dat'}<=set(r['artifacts_sha256'])
  if args.replay:
   previous=P/'evidence/sar-command-baseline.json';audit=json.loads(previous.read_text());assert audit['reproduction_pass']
   reference=R/'scratch/transceiver-sar-command-baseline/baseline.dat';assert sha(reference)==audit['waveform_sha256']
  else:
   reference=R/'scratch/transceiver-adc-sar8-reference-reservoir/typical_first1.dat';assert sha(reference)==m['donor_artifacts_sha256']['.dat']
  h,a=read(W/(name+'.dat'));hb,b=read(reference);assert h==hb and a[-1,0]>=80e-9
  t=np.unique(np.r_[70e-9,a[(a[:,0]>70e-9)&(a[:,0]<79e-9),0],b[(b[:,0]>70e-9)&(b[:,0]<79e-9),0],79e-9]);volts={}
  for node in ['v(hp)','v(hn)','v(vh)','v(vl)']:
   k=h.index(node);volts[node]=float(max(abs(np.interp(t,a[:,0],a[:,k])-np.interp(t,b[:,0],b[:,k]))))
  timings=[]
  for rising in [False,True]:
   ea=edges(a[:,0],a[:,h.index('v(b7)')],rising);eb=edges(b[:,0],b[:,h.index('v(b7)')],rising)
   timings.append(dict(rising=rising,counts=[len(ea),len(eb)],maximum_error_s=float(max(abs(ea-eb))) if len(ea)==len(eb) and len(ea) else None))
  decisions=[]
  for when in [72.4e-9,77.4e-9]:
   va=float(np.interp(when,a[:,0],a[:,h.index('v(qp)')]-a[:,h.index('v(qn)')]))
   vb=float(np.interp(when,b[:,0],b[:,h.index('v(qp)')]-b[:,h.index('v(qn)')]))
   decisions.append(dict(time_ns=when*1e9,candidate_v=va,reference_v=vb,match=bool(abs(va)>2.97 and abs(vb)>2.97 and np.sign(va)==np.sign(vb))))
  edgepass=all(x['counts'][0]==x['counts'][1] and (x['maximum_error_s'] is None or x['maximum_error_s']<=10e-12) for x in timings) and sum(x['counts'][0] for x in timings)>0
  out.update(completed=True,waveform_sha256=sha(W/(name+'.dat')),reference_sha256=sha(reference),voltage_errors_v=volts,b7_edges=timings,decisions=decisions,reproduction_pass=bool(max(volts.values())<=10e-6 and edgepass and all(x['match'] for x in decisions)))
out['limitations']=['Reproduction only over70–79ns and two decisions, not full SAR correctness or internal-state identity.', 'Pending report is not evidence that a process is live; inspect runtime handle separately.']
(P/'evidence'/('sar-command-'+name+'.json')).write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out['completed'],out['reproduction_pass'])
