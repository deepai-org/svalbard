#!/usr/bin/env python3
"""Actual gate logic timing and charge bins; thresholds are not conduction tests."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-pump-clamped'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
ap=P/'evidence/pump-clamped.json';audit=json.loads(ap.read_text());rows=[]
for case in audit['cases']:
 if not case['completed']:continue
 n=case['name'];record=next(c for c in audit['provenance']['cases'] if c['name']==n)
 for ext,h in record['artifacts_sha256'].items():assert sha(W/(n+ext))==h
 a=np.loadtxt(W/(n+'.dat'),skiprows=1);assert np.all(np.diff(a[:,0])>0)
 # Slice with margin to include interpolation samples at complete-cycle bounds.
 start,stop=np.array(case['integration_window_ns'])*1e-9
 w=a[(a[:,0]>start-1e-9)&(a[:,0]<stop+1e-9)];t=w[:,0]
 def crossings(col):
  y=w[:,col]-1.65;k=np.flatnonzero((y[:-1]*y[1:]<0));return t[k]-y[k]*np.diff(t)[k]/np.diff(y)[k]
 # Split at every command threshold crossing, preserving total current integral.
 edges=np.concatenate([crossings(col) for col in (3,4,7)])
 x=np.unique(np.r_[start,t[(t>start)&(t<stop)],edges[(edges>start)&(edges<stop)],stop])
 current=np.interp(x,t,w[:,6]);mid=(x[:-1]+x[1:])/2;dt=np.diff(x)
 charge=(current[:-1]+current[1:])*.5*dt
 up=np.interp(mid,t,w[:,3])>1.65;dn=np.interp(mid,t,w[:,4])>1.65;pmos_command=np.interp(mid,t,w[:,7])<1.65
 masks={'both_commands':pmos_command&dn,'pmos_command_only':pmos_command&~dn,'nmos_command_only':~pmos_command&dn,'neither_command':~pmos_command&~dn}
 q={key:float(charge[mask].sum()) for key,mask in masks.items()}
 assert abs(sum(q.values())-case['pump_charge_c'])<1e-22
 count=case['reference_cycles']
 rows.append(dict(name=n,cycles=count,mean_up_high_width_ps=float(dt[up].sum()/count*1e12),mean_dn_high_width_ps=float(dt[dn].sum()/count*1e12),mean_upb_low_width_ps=float(dt[pmos_command].sum()/count*1e12),mean_gate_command_width_difference_ps=float((dt[pmos_command].sum()-dt[dn].sum())/count*1e12),charge_per_cycle_c={k:v/count for k,v in q.items()},net_charge_per_cycle_c=float(charge.sum()/count),pmos_vsg_range_v=[float((w[:,8]-w[:,7]).min()),float((w[:,8]-w[:,7]).max())],nmos_vgs_range_v=[float((w[:,4]-w[:,9]).min()),float((w[:,4]-w[:,9]).max())]))
out=dict(completed=audit['completed'] and len(rows)==2,audit_sha256=sha(ap),cases=rows,limitations=['1.65V command bins label logic states, not physical channel conduction.','Total pump current includes switching/displacement effects; bins do not identify which device caused charge.','Ideal output clamp and ideal reference/bias sources; no autonomous PLL qualification.','Partial results lack terminal matrix-level after-run provenance until both cases finish.'])
(P/'evidence/pump-switch-timing.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(dict(completed=out['completed'],cases=rows),indent=2))
