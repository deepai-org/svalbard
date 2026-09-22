"""Passive fixed-pole AC approximation; no transient fitting or qualification."""
import hashlib,json
from pathlib import Path
import numpy as np
from scipy.optimize import nnls
P=Path(__file__).resolve().parents[1]
path=P/'evidence/adc-cdac-load-matrix-wide.json';d=json.loads(path.read_text())
f=np.array(d['frequencies_hz']);s=2j*np.pi*f
Y=np.array(d['conductance_matrix_s'])+s[:,None,None]*np.array(d['capacitance_matrix_ff'])*1e-15
transform=np.array([[1.,1.],[1.,-1.]])/np.sqrt(2)
modal=transform.T@Y@transform
# Positive shunt G/C and positive series-RC branches guarantee passive admittance.
tau=np.logspace(-14,-8,37)
def basis(s):
 return np.column_stack([np.ones(len(s))*1e-3,s*1e-12]+[s*1e-12/(1+s*t) for t in tau])
b=basis(s);train=np.arange(len(f))%2==0
rows=[]
for index,name in enumerate(['common','differential']):
 y=modal[:,index,index];scale=np.maximum(abs(y),1e-12)
 design=b[train]/scale[train,None];target=y[train]/scale[train]
 coef,residual=nnls(np.vstack([design.real,design.imag]),np.r_[target.real,target.imag],maxiter=10000)
 predicted=b@coef;relative=abs(predicted-y)/abs(y)
 branches=[dict(capacitance_f=float(v*1e-12),tau_s=float(t),resistance_ohm=float(t/(v*1e-12))) for t,v in zip(tau,coef[2:]) if v>1e-12]
 rows.append(dict(mode=name,shunt_conductance_s=float(coef[0]*1e-3),shunt_capacitance_f=float(coef[1]*1e-12),branches=branches,training_max_relative_error=float(max(relative[train])),held_out_max_relative_error=float(max(relative[~train])),relative_error=relative.tolist()))
# A single RC branch must obey zero-DC admittance and positive real conductance.
stest=2j*np.pi*np.array([1e6,1e9]);test=stest*2e-12/(1+stest*1e-10)
assert np.all(test.real>0) and np.allclose(1/test,50+1/(stest*2e-12))
report=dict(status='passive_ac_fit_not_transient_validated',source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),frequencies_hz=f.tolist(),training_indices=np.flatnonzero(train).tolist(),results=rows,maximum_modal_cross_coupling_fraction=float(max(abs(modal[:,0,1])/np.linalg.norm(modal,axis=(1,2)))),limitations=['Alternate frequency points withheld from fitting; same nominal fixed-code fixture, not independent operating conditions.', 'Off-diagonal modal coupling omitted and reported; code127 is not exactly symmetric.', 'Nonnegative RC network is passive/stable but not uniquely identified or accurate beyond the measured band.', 'No transient waveform used for fitting; comparison still required before model adoption.'])
(P/'evidence/fast-cdac-passive-fit.json').write_text(json.dumps(report,indent=2)+'\n')
print([(r['mode'],len(r['branches']),r['training_max_relative_error'],r['held_out_max_relative_error']) for r in rows])
print('modal coupling fraction',report['maximum_modal_cross_coupling_fraction'])
