"""Compare signed charge and rail direction around the known worst decision."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';E=P/'evidence/reference-hybrid-output2-frames.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
e=json.loads(E.read_text());assert e['completed'];rows=[]
for name,root in [('baseline',R/'scratch/transceiver-cdac-probe-reltol/probed'),('candidate',R/'scratch/transceiver-reference-hybrid-output2-frames')]:
 for ext,h in e['cases'][name]['artifacts_sha256'].items():assert sha(root/('frames'+ext))==h
 with (root/'frames.dat').open() as f:h=f.readline().lower().split()
 names=['v(vh)','v(vl)','i(vrefh_del)','i(vrefh_res)','i(vrefl_del)','i(vrefl_res)']
 a=np.loadtxt(root/'frames.dat',skiprows=1,usecols=[0]+[h.index(n) for n in names]);t=a[:,0];assert np.isfinite(a).all() and np.all(np.diff(t)>0) and t[-1]+1e-21>=209.9e-9
 for lo,hi in [(122.5,125.35),(125.2,125.35)]:
  tt=np.r_[lo*1e-9,t[(t>lo*1e-9)&(t<hi*1e-9)],hi*1e-9];w=np.column_stack([np.interp(tt,t,a[:,k]) for k in range(1,7)])
  rails=[]
  for rail,voltage,delivery,reservoir in [('h',0,2,3),('l',1,4,5)]:
   y=w[:,voltage];d=w[:,delivery];c=w[:,reservoir];load=d-c
   rails.append(dict(rail=rail,start_v=float(y[0]),end_v=float(y[-1]),change_v=float(y[-1]-y[0]),motion_v=float(np.ptp(y)),delivery_charge_c=float(np.trapezoid(d,tt)),reservoir_charge_c=float(np.trapezoid(c,tt)),load_charge_c=float(np.trapezoid(load,tt)),load_min_a=float(load.min()),load_max_a=float(load.max())))
  rows.append(dict(case=name,window_ns=[lo,hi],rails=rails))
out=dict(completed=True,parent_sha256=sha(E),windows=rows,limitations=['Signed current conventions inherited from verified delivery/reservoir probes; negative reservoir charge means net discharge under that convention.', 'Observation of this event does not uniquely establish a compensation or transistor failure mechanism.', 'No approximation of nonlinear MIM capacitance by a constant C; rail movement and integrated current reported separately.'])
(P/'evidence/reference-output2-event.json').write_text(json.dumps(out,indent=2)+'\n')
for x in rows:print(x)
