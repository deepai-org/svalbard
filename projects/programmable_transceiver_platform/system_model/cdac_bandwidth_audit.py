"""Wideband linear-model discrepancy and finite clock-current spectrum."""
import hashlib,json
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parents[1];R=P.parents[1]
paths=[P/'evidence'/n for n in ['adc-cdac-load-matrix-wide.json','adc-top-load-matrix.json','fast-cdac-impedance.json','adc-kickback-fine-clamped.json']]
wide,top,rc,clock=[json.loads(p.read_text()) for p in paths]
f=np.array(wide['frequencies_hz']);w=2*np.pi*f
actual=np.array(wide['conductance_matrix_s'])+1j*w[:,None,None]*np.array(wide['capacitance_matrix_ff'])*1e-15
predicted=1j*w[:,None,None]*np.array(top['capacitance_matrix_ff'][0])*1e-15
for k,r in enumerate(rc['results']):
 predicted[:,k,k]+=1/(r['low_frequency_series_resistance_ohm']+1/(1j*w*r['low_frequency_series_capacitance_f']))
rel=np.linalg.norm(predicted-actual,axis=(1,2))/np.linalg.norm(actual,axis=(1,2))
arrays=[]
for flag in [True,False]:
 case=next(c for c in clock['cases'] if c['differential_v']==.001 and c['clocked']==flag)
 path=R/'scratch/transceiver-adc-kickback-fine'/(case['name']+'.dat')
 assert hashlib.sha256(path.read_bytes()).hexdigest()==case['artifacts_sha256']['.dat']
 arrays.append(np.loadtxt(path,skiprows=1))
a,b=arrays;dt=1e-12;t=2e-9+np.arange(2900)*dt
current=np.column_stack([np.interp(t,a[:,0],a[:,k])-np.interp(t,b[:,0],b[:,k]) for k in [1,2]])
spectra={}
for mode,weights in [('differential',np.array([1.,-1.])),('common_mode',np.array([.5,.5]))]:
 x=current@weights;fft=np.fft.rfft(x);energy=abs(fft)**2;energy[1:-1]*=2
 assert np.isclose(energy.sum()/len(x),np.sum(x*x),rtol=1e-12)
 freq=np.fft.rfftfreq(len(x),dt)
 spectra[mode]={str(edge):float(energy[freq>edge].sum()/energy.sum()) for edge in [1e9,10e9,100e9]}
report=dict(status='bandwidth_scope_diagnostic',source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},frequencies_hz=f.tolist(),relative_matrix_error=rel.tolist(),current_energy_fraction_above_hz=spectra,limitations=['Rectangular finite2–4.9ns record, approximately345MHz frequency resolution; spectral leakage present.', 'Current energy is not voltage error or a required-bandwidth guarantee.', 'High-frequency PDK evaluation is a model diagnostic, not validated100GHz process capability.', 'Constant reset input capacitance and one-RC array are deliberately tested approximations.'])
(P/'evidence/fast-cdac-bandwidth.json').write_text(json.dumps(report,indent=2)+'\n')
print('relative matrix error at1/10/100GHz',[float(rel[np.argmin(abs(f-edge))]) for edge in [1e9,10e9,100e9]])
print(spectra)
