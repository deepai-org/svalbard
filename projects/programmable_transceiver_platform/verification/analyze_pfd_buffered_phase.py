#!/usr/bin/env python3
"""Distinguish source-clock phase from phase at actual PFD pins."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-pfd-offset'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((W/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after'];rows=[]
for c in r['cases']:
 n=c['name'];assert c['returncode']==0 and not c['timed_out']
 for ext,h in c['artifacts_sha256'].items():assert sha(W/(n+ext))==h
 with (W/(n+'.dat')).open() as f:h=f.readline().lower().split()
 assert h==['time','v(refraw)','v(ref)','v(fb)','v(up)','v(dn)','v(ctrl)','i(vsense)']
 a=np.loadtxt(W/(n+'.dat'),skiprows=1);assert np.isfinite(a).all() and np.all(np.diff(a[:,0])>0) and a[-1,0]+1e-21>=800e-9
 w=a[(a[:,0]>=200e-9)&(a[:,0]<=790e-9)];t=w[:,0]
 def edges(col):
  y=w[:,col]-1.65;k=np.flatnonzero((y[:-1]<0)&(y[1:]>=0));return t[k]-y[k]*np.diff(t)[k]/np.diff(y)[k]
 raw,ref,fb=[edges(i) for i in (1,2,3)];assert len(raw)==len(ref)==len(fb)>5
 start,stop=ref[0],ref[-1];x=np.r_[start,t[(t>start)&(t<stop)],stop]
 def integral(col):return float(np.trapezoid(np.interp(x,t,w[:,col]),x))
 rows.append(dict(name=n,source_reference_minus_feedback_ps=(1e12*(raw-fb)).tolist(),pfd_reference_minus_feedback_ps=(1e12*(ref-fb)).tolist(),buffer_rising_delay_ps=(1e12*(ref-raw)).tolist(),integration_window_ns=[start*1e9,stop*1e9],reference_cycles=len(ref)-1,pump_charge_c=integral(7),mean_pump_current_a=integral(7)/(stop-start),mean_up_v=integral(4)/(stop-start),mean_dn_v=integral(5)/(stop-start)))
out=dict(completed=True,provenance=r,cases=rows,limitations=['Retained buffered ideal-clock fixture; no autonomous loop, cold startup or jitter qualification.','Positive reference-minus-feedback means reference arrives later. Positive VSENSE current flows from pump into filter.','Finite phase points with control-dependent pump behavior cannot establish phase detector gain or static lock offset.'])
(P/'evidence/pfd-buffered-phase.json').write_text(json.dumps(out,indent=2)+'\n')
for c in rows:print(c['name'],'raw phase ps',np.mean(c['source_reference_minus_feedback_ps']),'PFD phase ps',np.mean(c['pfd_reference_minus_feedback_ps']),'buffer delay ps',np.mean(c['buffer_rising_delay_ps']),'mean pump A',c['mean_pump_current_a'])
