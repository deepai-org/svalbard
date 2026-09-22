"""Measured rail movement during actual comparator regeneration; no frozen-input claim."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
e=P/'evidence/adc-sar8-reference-reservoir-screen.json';audit=json.loads(e.read_text())
rows=[]
for case in audit['cases']:
 label=case['name'];p=R/'scratch/transceiver-adc-sar8-reference-reservoir'/(label+'.dat')
 assert sha(p)==case['artifacts_sha256']['.dat']
 with p.open() as f:h=f.readline().lower().split()
 a=np.loadtxt(p,skiprows=1);t=a[:,0];assert np.all(np.diff(t)>0) and np.isfinite(a).all()
 def v(n):return a[:,h.index('v('+n+')')]
 span=v('vh')-v('vl');res=v('hp')-v('hn');q=v('qp')-v('qn');events=[]
 for start,end in [(hold+.5+5*j,hold+2.4+5*j) for hold in (70,120,170) for j in range(8)]:
  k=np.flatnonzero((t[:-1]>=start*1e-9)&(t[1:]<=end*1e-9)&(abs(q[:-1])<2.97)&(abs(q[1:])>=2.97))
  assert len(k)>0
  j=k[0];resolve=t[j]+(2.97-abs(q[j]))*(t[j+1]-t[j])/(abs(q[j+1])-abs(q[j]))
  tt=np.r_[start*1e-9,t[(t>start*1e-9)&(t<resolve)],resolve]
  sv=np.interp(tt,t,span);rv=np.interp(tt,t,res)
  events.append(dict(clock_start_ns=start,first_full_swing_ns=float(resolve*1e9),regeneration_ps=float((resolve-start*1e-9)*1e12),span_start_v=float(sv[0]),span_at_resolution_v=float(sv[-1]),span_motion_v=float(np.ptp(sv)),residue_start_v=float(rv[0]),residue_at_resolution_v=float(rv[-1]),residue_motion_v=float(np.ptp(rv)),residue_sign_changes=int(np.count_nonzero(np.signbit(rv[1:])!=np.signbit(rv[:-1])))))
 rows.append(dict(variant=label,waveform_sha256=sha(p),events=events))
out=dict(source_evidence_sha256=sha(e),results=rows,limitations=['First crossing of 90% output differential is a timing diagnostic, not an effective sampling instant.','Residue motion includes reference response, comparator kickback and other coupled effects; no causal decomposition.','No noise/mismatch or complete-code accuracy qualification.'])
(P/'evidence/sar-full-aperture-baseline.json').write_text(json.dumps(out,indent=2)+'\n')
for r in rows:
 print(r['variant'],'max regeneration ps',max(x['regeneration_ps'] for x in r['events']),'min residue mV',min(abs(x['residue_start_v']) for x in r['events'])*1e3)
