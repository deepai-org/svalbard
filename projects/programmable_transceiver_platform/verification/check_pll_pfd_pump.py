#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3];W=ROOT/'scratch/transceiver-pll-pfd-pump';r=json.loads((W/'result.json').read_text())
for c in r['cases']:
 name=f"phase{c['feedback_delay_ns']}"
 for s,h in c['artifacts_sha256'].items():assert hashlib.sha256((W/(name+s)).read_bytes()).hexdigest()==h
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);charges=[]
 for k in range(3,10):
  start=k*40e-9;end=(k+1)*40e-9;m=(a[:,0]>start)&(a[:,0]<end)
  t=np.r_[start,a[m,0],end];i=np.r_[np.interp(start,a[:,0],a[:,5]),a[m,5],np.interp(end,a[:,0],a[:,5])]
  charges.append(float(np.trapezoid(i,t)))
 c['exact_window_cycle_charges_c']=charges;c['mean_charge_c']=float(np.mean(charges));c['cycle_charge_spread_c']=float(np.ptp(charges))
 assert c['reset_output_max_v']<.1 and abs(c['mean_charge_c']-c['charge_per_cycle_c'])<1e-15
assert r['cases'][0]['mean_charge_c']<0<r['cases'][2]['mean_charge_c']
r['aligned_mean_current_a']=r['cases'][1]['mean_charge_c']*25e6
r['aligned_equivalent_20ua_pulse_s']=r['cases'][1]['mean_charge_c']/20e-6
r['direction_checks_pass']=True
r['limitations'].append('Aligned charge offset is preserved, not passed as matching; static clamp does not establish loop ripple or phase-noise performance.')
(ROOT/'projects/programmable_transceiver_platform/evidence/pll-pfd-pump-screen.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(dict(charge_fc=[c['mean_charge_c']*1e15 for c in r['cases']],aligned_current_ua=r['aligned_mean_current_a']*1e6,cycle_spread_fc=[c['cycle_charge_spread_c']*1e15 for c in r['cases']]),indent=2))
