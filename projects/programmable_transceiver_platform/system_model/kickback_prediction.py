"""Predict floating-load clock motion from independent clamped charge and AC C."""
import hashlib,json
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parents[1];R=P.parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
paths={name:P/'evidence'/name for name in ['adc-kickback-fine-clamped.json','adc-floating-kickback.json','adc-top-load-matrix.json','adc-top-load.json']}
d={name:json.loads(p.read_text()) for name,p in paths.items()}
c=np.array(d['adc-top-load-matrix.json']['capacitance_matrix_ff'][0])*1e-15
c+=np.eye(2)*256*d['adc-top-load.json']['unit_capacitance_ff']*1e-15
assert np.all(np.linalg.eigvalsh(c)>0)
assert np.allclose(np.linalg.solve(np.diag([2.,4.]),[2.,8.]),[1.,2.])
arrays={}
for name,folder in [('adc-kickback-fine-clamped.json','transceiver-adc-kickback-fine'),('adc-floating-kickback.json','transceiver-adc-floating-kickback')]:
 for case in d[name]['cases']:
  if abs(case['differential_v'])!=.001:continue
  p=R/'scratch'/folder/(case['name']+'.dat');assert sha(p)==case['artifacts_sha256']['.dat']
  arrays[name,case['differential_v'],case['clocked']]=np.loadtxt(p,skiprows=1)
rows=[]
for diff in [-.001,.001]:
 a=arrays['adc-kickback-fine-clamped.json',diff,True];b=arrays['adc-kickback-fine-clamped.json',diff,False]
 f=arrays['adc-floating-kickback.json',diff,True];g=arrays['adc-floating-kickback.json',diff,False]
 t=np.unique(np.r_[2e-9,a[(a[:,0]>2e-9)&(a[:,0]<4.9e-9),0],f[(f[:,0]>2e-9)&(f[:,0]<4.9e-9),0],4.9e-9])
 current=np.column_stack([np.interp(t,a[:,0],a[:,k])-np.interp(t,b[:,0],b[:,k]) for k in [1,2]])
 charge=np.vstack([np.zeros(2),np.cumsum((current[1:]+current[:-1])*.5*np.diff(t)[:,None],axis=0)])
 predicted=np.linalg.solve(c,charge.T).T
 observed=np.column_stack([np.interp(t,f[:,0],f[:,k])-np.interp(t,g[:,0],g[:,k]) for k in [1,2]])
 metrics={}
 for mode,weight in [('differential',np.array([1.,-1.])),('common_mode',np.array([.5,.5]))]:
  x=predicted@weight;y=observed@weight;error=x-y
  metrics[mode]=dict(predicted_peak_v=float(max(abs(x))),observed_peak_v=float(max(abs(y))),max_error_v=float(max(abs(error))),time_weighted_rms_error_v=float(np.sqrt(np.trapezoid(error**2,t)/(t[-1]-t[0]))))
 rows.append(dict(input_differential_v=diff,metrics=metrics))
report=dict(status='independent_fixture_prediction_comparison',source_sha256={n:sha(p) for n,p in paths.items()},script_sha256=sha(Path(__file__)),results=rows,limitations=['No fitted voltage gain or time shift; current sign and timing use SPICE source conventions.', 'Reset-state matrix approximated constant during evaluation; conductive/leakage terms omitted.', 'Clamped and floating input trajectories differ, including sampler-induced initial bias.', 'Two nominal inputs with grounded MIM arrays, not switched CDAC or new process conditions.'])
(P/'evidence/fast-kickback-prediction.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(rows,indent=2))
