"""Measured128->64 command skew and reference state at next decision."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
source=P/'evidence/adc-sar8-reference-reservoir-screen.json';d=json.loads(source.read_text());rows=[]
def crossing(t,y,lo,hi,rising):
 condition=(y[:-1]<1.65)&(y[1:]>=1.65) if rising else (y[:-1]>=1.65)&(y[1:]<1.65)
 k=np.flatnonzero(condition&(t[:-1]>=lo)&(t[:-1]<hi));assert len(k)==1;i=k[0]
 return t[i]+(1.65-y[i])*(t[i+1]-t[i])/(y[i+1]-y[i])
assert crossing(np.array([0.,1.]),np.array([0.,3.3]),0,1,True)==.5
for case in d['cases']:
 p=R/'scratch/transceiver-adc-sar8-reference-reservoir'/(case['name']+'.dat');assert hashlib.sha256(p.read_bytes()).hexdigest()==case['artifacts_sha256']['.dat']
 with p.open() as f:h=f.readline().lower().split()
 names=['v(sd6)','v(sd7)','v(clk)','v(vh)','v(vl)','v(b7)','v(b7b)'];a=np.loadtxt(p,skiprows=1,usecols=[0]+[h.index(n) for n in names]);t=a[:,0]
 for frame in case['frames']:
  hold=frame['hold_ns']*1e-9
  if np.interp(hold+5.275e-9,t,a[:,1])<1.65 or np.interp(hold+5.275e-9,t,a[:,2])>=1.65:continue
  falling=crossing(t,a[:,2],hold+2e-9,hold+5e-9,False)
  rising=crossing(t,a[:,1],hold+2e-9,hold+5e-9,True)
  decision=crossing(t,a[:,3],hold+5e-9,hold+6e-9,True)
  b7=crossing(t,a[:,6],hold+2e-9,hold+5e-9,False)
  rows.append(dict(case=case['name'],hold_ns=frame['hold_ns'],sd7_fall_ns=falling*1e9,sd6_rise_ns=rising*1e9,command_skew_ps=(rising-falling)*1e12,b7_fall_ns=b7*1e9,decision_clock_midpoint_ns=decision*1e9,last_command_to_clock_ps=(decision-rising)*1e12,span_at_clock_v=float(np.interp(decision,t,a[:,4]-a[:,5]))))
report=dict(status='actual_sar_timing_scope_audit',source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),cases=rows,limitations=['50% voltage crossings are timing markers, not conduction boundaries.', 'B6 was not saved; SD6 command and actual B7 output must not be conflated.', 'Clock midpoint is not a complete comparator aperture model.', 'Three selected nominal128->64 transitions do not bound all code histories.'])
(P/'evidence/sar-transition-timing-audit.json').write_text(json.dumps(report,indent=2)+'\n');print(rows)
