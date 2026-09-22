"""Predict floating-load clock motion from independent clamped charge and AC C."""
import hashlib,json
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parents[1];R=P.parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
paths={name:P/'evidence'/name for name in ['adc-kickback-fine-clamped.json','adc-cdac-kickback.json','adc-top-load-matrix.json','adc-top-load.json','fast-cdac-impedance.json']}
d={name:json.loads(p.read_text()) for name,p in paths.items()}
c=np.array(d['adc-top-load-matrix.json']['capacitance_matrix_ff'][0])*1e-15
rc=d['fast-cdac-impedance.json']['results']
ca=np.diag([r['low_frequency_series_capacitance_f'] for r in rc])
g=np.diag([1/r['low_frequency_series_resistance_ohm'] for r in rc])
ctinv=np.linalg.inv(c);cainv=np.linalg.inv(ca)
A=np.block([[-ctinv@g,ctinv@g],[cainv@g,-cainv@g]])
B=np.vstack([ctinv,np.zeros((2,2))])
def response(current,dt):
    left=np.eye(4)-dt*A/2
    transition=np.linalg.solve(left,np.eye(4)+dt*A/2)
    drive=np.linalg.solve(left,dt*B/2)
    state=np.zeros(4);out=np.zeros((len(current),2))
    for k in range(1,len(current)):
        state=transition@state+drive@(current[k-1]+current[k])
        out[k]=state[:2]
    return out
assert np.array_equal(response(np.zeros((10,2)),1e-13),np.zeros((10,2)))
assert np.all(np.linalg.eigvalsh(c)>0)
assert np.allclose(np.linalg.solve(np.diag([2.,4.]),[2.,8.]),[1.,2.])
arrays={}
for name,folder in [('adc-kickback-fine-clamped.json','transceiver-adc-kickback-fine'),('adc-cdac-kickback.json','transceiver-adc-cdac-kickback')]:
 for case in d[name]['cases']:
  if abs(case['differential_v'])!=.001:continue
  p=R/'scratch'/folder/(case['name']+'.dat');assert sha(p)==case['artifacts_sha256']['.dat']
  arrays[name,case['differential_v'],case['clocked']]=np.loadtxt(p,skiprows=1)
rows=[]
for diff in [-.001,.001]:
 a=arrays['adc-kickback-fine-clamped.json',diff,True];b=arrays['adc-kickback-fine-clamped.json',diff,False]
 f=arrays['adc-cdac-kickback.json',diff,True];g=arrays['adc-cdac-kickback.json',diff,False]
 t=np.linspace(2e-9,4.9e-9,290001)
 current=np.column_stack([np.interp(t,a[:,0],a[:,k])-np.interp(t,b[:,0],b[:,k]) for k in [1,2]])
 charge=np.vstack([np.zeros(2),np.cumsum((current[1:]+current[:-1])*.5*np.diff(t)[:,None],axis=0)])
 predicted=response(current,t[1]-t[0])
 coarse=response(current[::2],t[2]-t[0])
 refinement=float(np.max(abs(coarse-predicted[::2])))
 observed=np.column_stack([np.interp(t,f[:,0],f[:,k])-np.interp(t,g[:,0],g[:,k]) for k in [1,2]])
 metrics={}
 for mode,weight in [('differential',np.array([1.,-1.])),('common_mode',np.array([.5,.5]))]:
  x=predicted@weight;y=observed@weight;error=x-y
  metrics[mode]=dict(predicted_peak_v=float(max(abs(x))),observed_peak_v=float(max(abs(y))),max_error_v=float(max(abs(error))),time_weighted_rms_error_v=float(np.sqrt(np.trapezoid(error**2,t)/(t[-1]-t[0]))))
 rows.append(dict(input_differential_v=diff,metrics=metrics,step_refinement_max_port_difference_v=refinement))
report=dict(status='independent_fixture_prediction_comparison',source_sha256={n:sha(p) for n,p in paths.items()},script_sha256=sha(Path(__file__)),results=rows,limitations=['No fitted voltage gain or time shift; current sign and timing use SPICE source conventions.', 'Reset input matrix plus one series RC per CDAC side; nonlinear switching and reference dynamics omitted.', 'Clamped and floating input trajectories differ, including sampler-induced initial bias.', 'Two nominal inputs with fixed-code127 transistor CDAC and ideal rails; not full SAR or new process conditions.'])
(P/'evidence/fast-cdac-kickback-prediction.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(rows,indent=2))
