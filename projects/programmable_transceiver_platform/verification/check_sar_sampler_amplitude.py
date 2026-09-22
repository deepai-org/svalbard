"""Matched amplitude comparison; no scoring of incomplete simulation output."""
import hashlib,json,math
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rows=[]
for banks,source in [(1,'sar-reference-clamped'),(2,'sar-sampler-double')]:
 B=R/f'scratch/transceiver-sar-amplitude-bank{banks}-prepared';W=R/f'scratch/transceiver-sar-amplitude-bank{banks}';m=json.loads((B/'manifest.json').read_text());assert sha(B/'baseline.spice')==m['artifacts_sha256']['baseline.spice']
 s=(B/'baseline.spice').read_text()
 for old,new in m['input_changes']:assert s.count(new)==1;s=s.replace(new,old)
 assert s==(R/('scratch/transceiver-'+source+'-prepared/baseline.spice')).read_text()
 row=dict(banks=banks,completed=False,status='pending',preparation_sha256=sha(B/'manifest.json'))
 if (W/'result.json').exists():
  r=json.loads((W/'result.json').read_text());assert r['sources_before']==r['sources_after'] and sha(W/'baseline.spice')==sha(B/'baseline.spice')
  for ext,d in r['artifacts_sha256'].items():assert sha(W/('baseline'+ext))==d
  errors=[l for l in (W/'baseline.log').read_text().splitlines() if any(k in l.lower() for k in ('warning','error','aborted','timestep too small'))]
  row.update(status='terminal',returncode=r['returncode'],timed_out=r['timed_out'],errors=errors)
  if r['returncode']==0 and not r['timed_out'] and not errors:
   with (W/'baseline.dat').open() as f:h=f.readline().lower().split()
   a=np.loadtxt(W/'baseline.dat',skiprows=1);t=a[:,0];assert len(h)==a.shape[1] and np.isfinite(a).all() and np.all(np.diff(t)>0) and t[-1]>=209.9e-9-1e-20
   for n,v in [('vh',2.15),('vl',1.15)]:assert np.max(abs(a[:,h.index('v('+n+')')]-v))<=1e-9
   def at(n,ns):return float(np.interp(ns*1e-9,t,a[:,h.index('v('+n+')')]))
   frames=[]
   for hold,target in [(70,.1),(120,-.1),(170,.1)]:
    bits=[at('d'+str(k),hold+39) for k in range(8)];valid=all(v<.33 or v>2.97 for v in bits);code=sum(int(v>1.65)*2**k for k,v in enumerate(bits));ideal=math.floor(128-128*target)
    points=[dict(offset_ns=dt,driver_error_v=at('ip',hold+dt)-at('in',hold+dt)-target,held_error_v=at('hp',hold+dt)-at('hn',hold+dt)-target) for dt in (0,.1,.5)]
    decisions=[]
    for j in range(8):
     q=at('qp',hold+2.4+5*j)-at('qn',hold+2.4+5*j);res=at('hp',hold+.5+5*j)-at('hn',hold+.5+5*j)
     decisions.append(dict(bit=7-j,preclock_residue_v=res,full_swing=bool(abs(q)>2.97),polarity_agrees=bool(np.sign(q)==np.sign(res))))
    frames.append(dict(hold_ns=hold,final_code=code,final_bits_valid=valid,ideal_source_code=ideal,code_error=code-ideal,acquisition=points,decisions=decisions))
   row.update(completed=True,frames=frames,waveform_sha256=sha(W/'baseline.dat'),result_sha256=sha(W/'result.json'))
 rows.append(row)
# The two prepared circuits must differ only by the declared extra sampler bank.
s1=(R/'scratch/transceiver-sar-amplitude-bank1-prepared/baseline.spice').read_text();s2=(R/'scratch/transceiver-sar-amplitude-bank2-prepared/baseline.spice').read_text();assert s2.replace('XS_EXTRA IP IN HP HN SC SCB VDD 0 wifi_if_transmission_gate\n','')==s1
out=dict(completed=all(r['completed'] for r in rows),adopted=False,cases=rows,limitations=['Nominal ideal rails and ideal clocks; two amplitudes do not qualify a transfer curve.','Correct selected final codes can coexist with offset, settling and input-history errors.'])
(P/'evidence/sar-sampler-amplitude.json').write_text(json.dumps(out,indent=2)+'\n')
for r in rows:print(r['banks'],r['status'],[f['final_code'] for f in r.get('frames',[])])
