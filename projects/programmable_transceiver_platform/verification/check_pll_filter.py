#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3];W=ROOT/'scratch/transceiver-pll-filter';r=json.loads((W/'result.json').read_text())
for c in r['cases']:
 name=f"phase{c['feedback_delay_ns']}"
 for suffix,h in c['artifacts_sha256'].items():assert hashlib.sha256((W/(name+suffix)).read_bytes()).hexdigest()==h
 a=np.loadtxt(W/(name+'.dat'),skiprows=1)
 def sample(t,col):return float(np.interp(t,a[:,0],a[:,col]))
 start=120e-9;end=800e-9;m=(a[:,0]>start)&(a[:,0]<end);t=np.r_[start,a[m,0],end];i=np.r_[sample(start,5),a[m,5],sample(end,5)]
 q=float(np.trapezoid(i,t));dq=2e-12*(sample(end,6)-sample(start,6))+50e-12*(sample(end,7)-sample(start,7))
 c['integrated_charge_c']=q;c['capacitor_charge_change_c']=dq;c['charge_balance_error_c']=q-dq
 c['charge_balance_pass']=abs(q-dq)<max(abs(q)*.01,1e-16)
 c['control_start_v']=sample(start,6);c['control_end_v']=sample(end,6);c['control_change_v']=c['control_end_v']-c['control_start_v']
 w=a[(a[:,0]>=760e-9)&(a[:,0]<=800e-9)];t=w[:,0];fit=np.polyfit(t-t.mean(),w[:,6],1);res=w[:,6]-np.polyval(fit,t-t.mean())
 c['last_cycle_raw_peak_to_peak_v']=float(np.ptp(w[:,6]));c['last_cycle_linear_detrended_peak_to_peak_v']=float(np.ptp(res))
 assert c['charge_balance_pass']
assert r['cases'][0]['control_change_v']<0<r['cases'][2]['control_change_v']
r['limitations'].extend(['No VCO loading or feedback; filter values not a stability design.', 'Detrended peak-to-peak is a deterministic waveform diagnostic, not phase noise or random jitter.'])
(ROOT/'projects/programmable_transceiver_platform/evidence/pll-filter-screen.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps([{k:c[k] for k in ('feedback_delay_ns','control_change_v','last_cycle_linear_detrended_peak_to_peak_v','charge_balance_error_c')} for c in r['cases']],indent=2))
