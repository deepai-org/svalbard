#!/usr/bin/env python3
"""Preserve bounded observations from an aborted run without promoting it to a pass."""
import hashlib,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3];P=ROOT/'projects/programmable_transceiver_platform';W=ROOT/'scratch/transceiver-closed-loop-settling'
log=(W/'closed.log').read_text();assert 'Timestep too small' in log and 'vregen#branch' in log and 'tran simulation(s) aborted' in log
assert not (W/'result.json').exists(),'A completed result needs separate review'
a=np.loadtxt(W/'closed.dat',skiprows=1);assert a.shape[1]==18 and np.isfinite(a).all()
assert 2.76e-6<a[-1,0]<2.77e-6
# No inference from the solver's tiny-step failure neighborhood.
rows=[]
for lo,hi in ((1100,1200),(2000,2100),(2500,2600)):
 w=a[(a[:,0]>=lo*1e-9)&(a[:,0]<=hi*1e-9)];t=w[:,0];assert np.all(np.diff(t)>0)
 v=w[:,1];i=np.flatnonzero((v[:-1]<0)&(v[1:]>=0));edges=t[i]-v[i]*np.diff(t)[i]/np.diff(v)[i]
 assert len(edges)>3
 rows.append(dict(window_ns=[lo,hi],vco_frequency_hz=float(1/np.mean(np.diff(edges))),control_range_v=[float(w[:,14].min()),float(w[:,14].max())],gate_range_v=[float(w[:,10].min()),float(w[:,10].max())],pump_charge_fc=float(np.trapezoid(w[:,16],t)*1e15)))
# The long-run prefix must reproduce the successful shorter run.
b=np.loadtxt(ROOT/'scratch/transceiver-closed-loop-extended/closed.dat',skiprows=1);b=b[b[:,0]<1200e-9]
errors=[float(np.max(np.abs(np.interp(b[:,0],a[:,0],a[:,col])-b[:,col]))) for col in range(1,18)];assert max(errors)<1e-5
r=dict(status='aborted_transient_partial_evidence_not_settling_pass',requested_stop_ns=3201,actual_last_time_ns=float(a[-1,0]*1e9),failure='ngspice timestep too small at vregen#branch; no physical-failure conclusion',windows=rows,prefix_max_absolute_errors_by_column=errors,artifacts_sha256={s:hashlib.sha256((W/('closed'+s)).read_bytes()).hexdigest() for s in ('.spice','.dat','.log')},pll_lock_established=False,limitations=['Run aborted before requested horizon; investigate numerical cause and rerun before qualification.', 'Only windows ending at or before 2600ns summarized; no inference from tiny-step failure neighborhood.', 'Nominal seeded/prebiased circuit with ideal external biases; no noise/startup/process or package evidence.'])
(P/'evidence/closed-loop-settling-aborted.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
