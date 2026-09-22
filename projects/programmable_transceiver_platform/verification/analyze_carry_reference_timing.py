"""Localize reference motion against known carry/comparator timing."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-cdac-carry-real-reference'
source=P/'evidence/cdac-carry-real-reference.json';d=json.loads(source.read_text());rows=[]
for case in d['cases']:
 p=W/(case['name']+'.dat');assert hashlib.sha256(p.read_bytes()).hexdigest()==case['artifacts_sha256']['.dat']
 a=np.loadtxt(p,skiprows=1);t=a[:,0];signals={'high':a[:,6],'low':a[:,7],'span':a[:,6]-a[:,7],'common':(a[:,6]+a[:,7])/2}
 windows=[]
 for label,lo,hi in [('before_carry',1.8,2),('gate_ramp',2,2.1),('before_clock',2.1,2.2),('clock_ramp',2.2,2.3),('evaluation',2.3,4.4)]:
  tt=np.r_[lo*1e-9,t[(t>lo*1e-9)&(t<hi*1e-9)],hi*1e-9];metrics={}
  for name,y in signals.items():
   v=np.interp(tt,t,y);baseline=np.interp(1.9e-9,t,y)
   metrics[name]=dict(min_v=float(v.min()),max_v=float(v.max()),minimum_time_ns=float(tt[np.argmin(v)]*1e9),maximum_time_ns=float(tt[np.argmax(v)]*1e9),max_departure_from_precarry_v=float(max(abs(v-baseline))))
  windows.append(dict(label=label,interval_ns=[lo,hi],rails=metrics))
 rows.append(dict(name=case['name'],initial_rails_v={n:float(y[0]) for n,y in signals.items()},precarry_rails_v={n:float(np.interp(1.9e-9,t,y)) for n,y in signals.items()},windows=windows))
report=dict(status='reference_event_timing_diagnostic',source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),results=rows,limitations=['Timing correlation alone does not identify current paths or prove gate overlap causality.', 'Only reference supply current was saved, not individual rail load currents.', 'Initial operating point and precarry baseline are distinct from target accuracy.', 'Ideal controls and one nominal carry; not bounded full-SAR/reference behavior.'])
(P/'evidence/cdac-carry-reference-timing.json').write_text(json.dumps(report,indent=2)+'\n')
for r in rows:
 print(r['name'],r['precarry_rails_v'])
 for w in r['windows']:print(w['label'],w['rails']['span']['min_v'],w['rails']['span']['minimum_time_ns'])
