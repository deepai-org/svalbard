"""Check centering against independent nodal exponential and energy balance."""
import json
import numpy as np
from scipy.linalg import expm
from chip_model import P
from three_cap_centering import ThreeCapCenteringFilter

f=ThreeCapCenteringFilter(r=10184.271638275502,cf=2.1190014980784758e-11,
    cs=2.457626702372388e-10,r3=10063.455048665259,c3=1.2479232271147656e-12)
f.state[:3]=[.8,-.7,.6];initial=f.state.copy();energy=f.energy
f.center_enabled=True
try:f.advance(1e-9,1e-6)
except ValueError:pass
else:raise AssertionError('Live pump accepted during centering')
assert np.array_equal(initial,f.state) and f.time==0
c=np.array([f.cf,f.cs,f.c3]);a=1/f.r;b=1/f.r3
conductance=np.array([[a+b,-a,-b],[-a,a,0],[-b,0,b]])+np.diag(c/f.center_tau)
matrix=-conductance/c[:,None]
# Integrate VCO voltage independently with an augmented linear matrix.
aug=np.zeros((4,4));aug[:3,:3]=matrix;aug[3,2]=1
end=4.8e-6
expected=expm(aug*end)@np.r_[initial[:3],0.]
f.advance(end,0)
np.testing.assert_allclose(f.state[:3],expected[:3],rtol=1e-6,atol=1e-12)
assert abs(f.state[3]-expected[3])<1e-16
assert max(abs(f.state[:3]))<=f.limit*np.exp(-12)
residual=f.energy+f.state[6]-energy
assert abs(residual)<1e-19
report=dict(status='passed_local_centering',node_error_v=float(max(abs(f.state[:3]-expected[:3]))),
    phase_integral_error_vs=float(abs(f.state[3]-expected[3])),energy_residual_j=float(residual),
    final_nodes_v=f.state[:3].tolist(),limitations=['Local passive centering only; full clock retune and chip integration remain untested.'])
(P/'evidence/three-cap-centering-screen.json').write_text(json.dumps(report,indent=2)+'\n')
print(report)
