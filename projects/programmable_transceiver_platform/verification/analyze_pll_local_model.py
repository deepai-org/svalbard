#!/usr/bin/env python3
"""Conditional averaged-loop audit; not a substitute for autonomous simulation."""
import argparse,hashlib,json
ap=argparse.ArgumentParser();ap.add_argument("--follower",action="store_true");args=ap.parse_args()
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parents[1]
paths=[P/('evidence/pump-follower-phase.json' if args.follower else 'evidence/pump-steering-phase.json'),P/'evidence/vco-split-lower.json',P/'evidence/vco-split-tuning.json',P/'analog/pll/loop_filter.spice']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
pump=json.loads(paths[0].read_text());assert pump['completed']
c={x['name']:x for x in pump['cases']}
# Charge/edge-time slope is equivalent to pump current in the averaged model.
iph=(c['late']['mean_charge_per_cycle_c']-c['early']['mean_charge_per_cycle_c'])/((np.mean(c['early']['reference_minus_feedback_ps'])-np.mean(c['late']['reference_minus_feedback_ps']))*1e-12)
assert iph>0
assert 'RZ=10k CZ=50p CP=2p' in paths[3].read_text()
points={}
for p in paths[1:3]:
 for c in json.loads(p.read_text())['cases']:points[c['control_v']]=c['frequency_hz']
points=sorted(points.items());rows=[]
R=1e4;CZ=50e-12;CP=2e-12;N=128
for (v0,f0),(v1,f1) in zip(points[:-1],points[1:]):
 kv=(f1-f0)/(v1-v0);K=iph*kv/N
 def loop(w):
  s=1j*w;z=(1+s*R*CZ)/(s*(CP+CZ)+s*s*R*CP*CZ);return K*z/s
 lo,hi=1.,1e11
 assert abs(loop(lo))>1 and abs(loop(hi))<1
 for _ in range(100):
  mid=np.sqrt(lo*hi)
  if abs(loop(mid))>1:lo=mid
  else:hi=mid
 w=np.sqrt(lo*hi);phase=np.angle(loop(w),deg=True)
 if phase>0:phase-=360
 poles=np.roots([R*CP*CZ,CP+CZ,K*R*CZ,K])
 rows.append(dict(control_interval_v=[v0,v1],vco_secant_gain_hz_per_v=kv,unity_gain_hz=w/(2*np.pi),phase_margin_deg=180+phase,closed_loop_poles_per_s=[[float(x.real),float(x.imag)] for x in poles],all_poles_left_half_plane=bool(np.all(poles.real<0))))
out=dict(status='conditional_averaged_model_not_loop_qualification',effective_pump_current_a=iph,divider=N,cases=rows,inputs_sha256={str(p.relative_to(P)):sha(p) for p in paths},limitations=['Pump slope is a two-point clamped-output measurement; follower variant includes real driver but ideal bias currents.','VCO slopes are secants from older loaded fixtures, not derivatives of the final connected circuit.','Model omits sampling delay, nonlinear acquisition, pump compliance/offset, follower input loading, noise, process and parasitics.','Stable averaged poles do not prove transistor-loop stability, lock or cold startup.'])
(P/('evidence/pll-local-model-follower.json' if args.follower else 'evidence/pll-local-model.json')).write_text(json.dumps(out,indent=2)+'\n')
print('effective pump uA',iph*1e6)
for row in rows:print(row['control_interval_v'],row['unity_gain_hz'],row['phase_margin_deg'],row['all_poles_left_half_plane'])
