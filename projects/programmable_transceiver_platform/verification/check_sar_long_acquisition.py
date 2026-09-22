"""Compare original and deliberately extended track interval; no rate qualification."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';B=R/'scratch/transceiver-sar-long-acquisition-prepared';W=R/'scratch/transceiver-sar-long-acquisition'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((B/'manifest.json').read_text());assert sha(B/'baseline.spice')==m['artifacts_sha256']['baseline.spice']
s=(B/'baseline.spice').read_text().replace('tran 5p 100n 0 5p','tran 5p 209.9n 0 5p')
for old,new in m['control_changes']:assert s.count(new)==1;s=s.replace(new,old)
assert s==(R/'scratch/transceiver-sar-reference-clamped-prepared/baseline.spice').read_text()
e=P/'evidence/sar-reference-clamped.json';assert sha(e)==m['baseline_evidence_sha256'];base=json.loads(e.read_text());assert base['completed'] and base['clamps_verified']
out=dict(completed=False,status='pending',adopted=False,preparation_sha256=sha(B/'manifest.json'),limitations=m['limitations'])
def measure(p,hold):
 with p.open() as f:h=f.readline().lower().split()
 a=np.loadtxt(p,skiprows=1);t=a[:,0];assert len(h)==a.shape[1] and np.isfinite(a).all() and np.all(np.diff(t)>0) and t[-1]>=(hold+9.9)*1e-9
 def at(n,ns):return float(np.interp(ns*1e-9,t,a[:,h.index('v('+n+')')]))
 errors={n:float(np.max(abs(a[:,h.index('v('+n+')')]-target))) for n,target in [('vh',2.15),('vl',1.15)]};assert max(errors.values())<=1e-9
 points=[]
 for offset in (-2,-1,-.1,0,.1,.5):
  ns=hold+offset;driver=at('ip',ns)-at('in',ns);held=at('hp',ns)-at('hn',ns)
  points.append(dict(offset_ns=offset,driver_error_v=driver-.4,tracking_difference_v=held-driver,held_error_v=held-.4))
 return dict(hold_ns=hold,clamp_errors_v=errors,points=points,decisions=[dict(time_ns=hold+dt,comparator_v=at('qp',hold+dt)-at('qn',hold+dt)) for dt in (2.4,7.4)])
if (W/'result.json').exists():
 r=json.loads((W/'result.json').read_text());assert r['sources_before']==r['sources_after']
 assert sha(W/'baseline.spice')==sha(B/'baseline.spice')
 for ext,d in r['artifacts_sha256'].items():assert sha(W/('baseline'+ext))==d
 errors=[l for l in (W/'baseline.log').read_text().splitlines() if any(k in l.lower() for k in ('warning','error','aborted','timestep too small'))]
 out.update(status='terminal',returncode=r['returncode'],timed_out=r['timed_out'],errors=errors)
 if r['returncode']==0 and not r['timed_out'] and not errors:
  donor=R/'scratch/transceiver-sar-reference-clamped/baseline.dat';assert sha(donor)==base['waveform_sha256']
  out.update(completed=True,result_sha256=sha(W/'result.json'),waveform_sha256=sha(W/'baseline.dat'),baseline=measure(donor,70),extended=measure(W/'baseline.dat',90))
(P/'evidence/sar-long-acquisition.json').write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out['completed'])
if out['completed']:
 for key in ('baseline','extended'):print(key,out[key]['points'][3])
