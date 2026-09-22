"""Local physical-current and deterministic integration checks for thermal forcing."""
import sys,json,copy
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(P/'system_model/connected'))
from three_cap_resistor_noise import ResistorNoiseFilter,K_B
from three_cap_retuning_clock import BALANCED_FILTER
f=ResistorNoiseFilter(**BALANCED_FILTER)
for i,r in enumerate((f.r,f.r3)):
 assert np.isclose(np.sum(f.noise_amplitude[i]**2)/2,4*K_B*300/r*(1e7-100),rtol=1e-14,atol=0)
y=np.array([.01,-.02,.03,0,0,0,0.])
f0=ResistorNoiseFilter(temperature_k=0,**BALANCED_FILTER)
delta=np.array(f.rhs(17e-9,y,0))-np.array(f0.rhs(17e-9,y,0))
assert abs(delta[:3]@np.array([f.cf,f.cs,f.c3]))<1e-19
assert abs(np.dot(y[:3]*[f.cf,f.cs,f.c3],delta[:3])-delta[5])<1e-20
one=copy.copy(f);split=copy.copy(f)
one.advance(20e-9,0)
for t in (3e-9,9e-9,20e-9):split.advance(t,0)
error=float(np.max(abs(one.state[:3]-split.state[:3])))
assert error<1e-10
energy_residual=float(one.energy-one.state[5]+one.state[6])
assert abs(energy_residual)<1e-22
assert f.time==0 and np.all(f.state==0)
report=dict(status='local_checks_passed',partition_voltage_error_v=error,
 energy_residual_j=energy_residual,limitations=['Finite 64-tone spectrum only; no coupled-chip result or spectral convergence yet.'])
(P/'evidence/resistor-noise-filter-screen.json').write_text(json.dumps(report,indent=2)+'\n')
print(report)
