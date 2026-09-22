"""Predict floating-load clock motion from independent clamped charge and AC C."""
import hashlib,json
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parents[1];R=P.parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
paths={name:P/'evidence'/name for name in ['adc-kickback-fine-clamped.json','adc-cdac-kickback.json','adc-top-load-matrix.json','adc-top-load.json','fast-cdac-passive-fit.json']}
d={name:json.loads(p.read_text()) for name,p in paths.items()}
transform=np.array([[1.,1.],[1.,-1.]])/np.sqrt(2)
models=d['fast-cdac-passive-fit.json']['results']
def matrices(model):
    c0=model['shunt_capacitance_f'];g0=model['shunt_conductance_s']
    branches=model['branches'];n=1+len(branches)
    A=np.zeros((n,n));B=np.zeros(n);B[0]=1/c0
    A[0,0]=-g0/c0
    for k,branch in enumerate(branches,1):
        conductance=1/branch['resistance_ohm'];cap=branch['capacitance_f']
        A[0,0]-=conductance/c0;A[0,k]=conductance/c0
        A[k,0]=conductance/cap;A[k,k]=-conductance/cap
    return A,B

def response(current,dt):
    modal=current@transform;out=np.zeros_like(modal)
    for mode,model in enumerate(models):
        A,B=matrices(model);n=len(B);left=np.eye(n)-dt*A/2
        transition=np.linalg.solve(left,np.eye(n)+dt*A/2)
        drive=np.linalg.solve(left,dt*B/2)
        state=np.zeros(n)
        for k in range(1,len(current)):
            state=transition@state+drive*(modal[k-1,mode]+modal[k,mode])
            out[k,mode]=state[0]
    return out@transform.T
# Independently verify state-space driving impedance against circuit admittance.
for model in models:
    A,B=matrices(model)
    for frequency in [1e6,1e9,1e11]:
        s=2j*np.pi*frequency
        admittance=model['shunt_conductance_s']+s*model['shunt_capacitance_f']
        for branch in model['branches']:
            admittance+=s*branch['capacitance_f']/(1+s*branch['tau_s'])
        impedance=np.linalg.solve(s*np.eye(len(B))-A,B)[0]
        assert np.isclose(impedance,1/admittance,rtol=1e-8)
assert np.array_equal(response(np.zeros((10,2)),1e-13),np.zeros((10,2)))
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
report=dict(status='independent_fixture_prediction_comparison',source_sha256={n:sha(p) for n,p in paths.items()},script_sha256=sha(Path(__file__)),results=rows,limitations=['No fitted voltage gain or time shift; current sign and timing use SPICE source conventions.', 'Passive AC-fit modal network; omitted modal coupling, nonlinear switching and reference dynamics.', 'Clamped and floating input trajectories differ, including sampler-induced initial bias.', 'Two nominal inputs with fixed-code127 transistor CDAC and ideal rails; not full SAR or new process conditions.'])
(P/'evidence/fast-cdac-broadband-prediction.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(rows,indent=2))
