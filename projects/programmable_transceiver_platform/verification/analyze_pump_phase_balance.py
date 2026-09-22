#!/usr/bin/env python3
"""Two-point phase-response comparison; estimated zero is not measured lock."""
import hashlib,json
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parents[1]
files=[P/'evidence/pump-follower-phase.json',P/'evidence/pump-control-range.json'];groups={}
for f in files:
 d=json.loads(f.read_text())
 for c in d['cases']:
  if not c.get('completed'):continue
  n=c['name'];voltage=float(n.split('_')[0][1:]) if n.startswith('v') else 1.08
  phase=n.split('_')[-1]
  groups.setdefault(voltage,{})[phase]=c
rows=[]
for voltage,c in sorted(groups.items()):
 if set(c)!={'early','late'}:continue
 early,late=c['early'],c['late']
 x=np.array([np.mean(early['reference_minus_feedback_ps']),np.mean(late['reference_minus_feedback_ps'])])*1e-12
 y=np.array([early['mean_charge_per_cycle_c'],late['mean_charge_per_cycle_c']])
 slope=(y[1]-y[0])/(x[1]-x[0]);intercept=y[0]-slope*x[0];zero=-intercept/slope
 rows.append(dict(control_v=voltage,phase_points_ps=(x*1e12).tolist(),charge_points_fc=(y*1e15).tolist(),equivalent_current_a=float(-slope),linear_zero_reference_minus_feedback_ps=float(zero*1e12),zero_inside_sampled_interval=bool(min(x)<=zero<=max(x)),measured_opposite_charge_signs=bool(y[0]*y[1]<0),limitations='Two-point secant only; zero estimate is not a simulated operating point, nonlinear transfer, acquisition or equilibrium proof.'))
out=dict(status='diagnostic_secants_not_lock',cases=rows,inputs_sha256={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files})
followup=P/'evidence/pump-range-followup.json'
if followup.exists():
 f=json.loads(followup.read_text());extended=next((c for c in f['cases'] if c['name']=='v0.98_late600' and c['completed']),None)
 if extended is not None and .98 in groups and 'late' in groups[.98]:
  original=groups[.98]['late'];q0=original['mean_charge_per_cycle_c'];q1=extended['mean_charge_per_cycle_c']
  out['low_control_late_phase_comparison']=dict(control_v=.98,phase_lag_ps=[300,600],measured_charge_fc=[q0*1e15,q1*1e15],opposite_measured_signs=bool(q0*q1<0),interpretation='Opposite measured charge signs support shifted balance; continuity, an actual zero, equilibrium stability and autonomous acquisition remain unverified.')
  out['inputs_sha256'][str(followup.relative_to(P))]=hashlib.sha256(followup.read_bytes()).hexdigest()
(P/'evidence/pump-phase-balance.json').write_text(json.dumps(out,indent=2)+'\n')
for row in rows:print(row)
