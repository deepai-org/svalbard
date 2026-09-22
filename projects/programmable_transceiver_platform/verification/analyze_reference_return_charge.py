"""Measure both signs of actual ADC reference demand, without applying a DC limit to pulses."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';E=P/'evidence/reference-hybrid-frames.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
audit=json.loads(E.read_text());assert audit['completed'];rows=[]
for name,root in [('baseline',R/'scratch/transceiver-cdac-probe-reltol/probed'),('hybrid',R/'scratch/transceiver-reference-hybrid-frames')]:
 case=audit['cases']['baseline' if name=='baseline' else 'candidate']
 for ext,h in case['artifacts_sha256'].items():assert sha(root/('frames'+ext))==h
 with (root/'frames.dat').open() as f:h=f.readline().lower().split()
 names=['i(vrefh_del)','i(vrefh_res)','i(vrefl_del)','i(vrefl_res)'];a=np.loadtxt(root/'frames.dat',skiprows=1,usecols=[0]+[h.index(n) for n in names]);t=a[:,0];assert np.isfinite(a).all() and np.all(np.diff(t)>0) and t[-1]+1e-21>=209.9e-9
 for rail,col in [('h',1),('l',3)]:
  demand=a[:,col]-a[:,col+1]
  lo,hi=60e-9,209.9e-9;inside=(t>lo)&(t<hi);tt=np.r_[lo,t[inside],hi];yy=np.interp(tt,t,demand)
  # Split at every zero crossing before integrating signs, avoiding trapezoid cancellation.
  k=np.flatnonzero(yy[:-1]*yy[1:]<0);cross=tt[k]-yy[k]*np.diff(tt)[k]/np.diff(yy)[k];fine=np.sort(np.r_[tt,cross]);y=np.interp(fine,tt,yy)
  positive=float(np.trapezoid(np.maximum(y,0),fine));negative=float(-np.trapezoid(np.minimum(y,0),fine));net=float(np.trapezoid(y,fine));assert abs(positive-negative-net)<1e-22
  rows.append(dict(case=name,rail=rail,window_ns=[60,209.9],max_withdrawal_a=float(yy.max()),max_return_a=float(-yy.min()),withdrawn_charge_c=positive,returned_charge_c=negative,net_charge_c=net))
out=dict(completed=True,parent_evidence_sha256=sha(E),cases=rows,limitations=['Demand equals delivery current minus reservoir current using retained probe conventions; includes capacitive switching.', 'A brief return-current peak is not equivalent to sustained DC injection; reservoir and time-dependent driver response must be retained.', 'No physical current-limit, reverse-load requirement or acceptance threshold inferred from these waveforms.'])
(P/'evidence/reference-return-charge.json').write_text(json.dumps(out,indent=2)+'\n');print(rows)
