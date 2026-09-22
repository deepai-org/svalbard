#!/usr/bin/env python3
"""Compare differential VCO timing and single-ended mixer-clock timing."""
import hashlib,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
B=ROOT/'scratch/transceiver-rf-ac-clock/v3.3.dat'
def fit(p,col,level):
 a=np.loadtxt(p,skiprows=1);assert np.isfinite(a).all();a=a[a[:,0]>=40e-9];t=a[:,0];v=a[:,col]
 i=np.where((v[:-1]<level)&(v[1:]>=level))[0]
 e=t[i]+(t[i+1]-t[i])*(level-v[i])/(v[i+1]-v[i]);assert len(e)>90
 x=np.column_stack([np.ones(len(e)),np.arange(len(e)),np.sin(2*np.pi*1e8*e),np.cos(2*np.pi*1e8*e)])
 c=np.linalg.lstsq(x,e,rcond=None)[0]
 return c[2:]
rows=[]
for name,step in [('transceiver-rf-supply-ripple',2),('transceiver-rf-supply-ripple-fine',.5)]:
 p=ROOT/'scratch'/name/'ripple.dat';r=json.loads((p.parent/'result.json').read_text())
 for s,h in r['artifacts_sha256'].items():assert hashlib.sha256((p.parent/('ripple'+s)).read_bytes()).hexdigest()==h
 row=dict(maximum_step_ps=step,clock_modulation_peak_ps={label:float(np.linalg.norm(fit(p,col,level)-fit(B,col,level))*1e12) for label,col,level in [('cml_differential',1,0),('lo',2,1.65),('lob',3,1.65)]},raw_result=r)
 rows.append(row)
r=dict(status='supply_to_clock_timing_diagnostic_not_intrinsic_phase_noise',cases=rows,interpretation='Large timing modulation develops at conversion to single-ended CMOS; differential CML edge modulation is much smaller. Mechanism needs isolation; do not attribute all LO timing error to oscillator phase.',limitations=['Only one ripple frequency/amplitude; four late cycles; no PLL.', 'Fine ripple run compared to same 2ps reference; reference fit amplitude is about 0.0013ps.', 'Not mismatch, stochastic noise, full RF rail disturbance or PEX.'])
(ROOT/'projects/programmable_transceiver_platform/evidence/rf-supply-ripple-screen.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps([dict(step_ps=x['maximum_step_ps'],peaks_ps=x['clock_modulation_peak_ps']) for x in rows],indent=2))
