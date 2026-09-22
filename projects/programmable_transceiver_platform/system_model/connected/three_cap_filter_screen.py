"""Independent affine matrix-exponential and energy checks for three-cap filter."""
import copy,json
import numpy as np
from scipy.linalg import expm
from chip_model import P
from three_cap_filter import ThreeCapFilter

def main():
    f=ThreeCapFilter(25000,12e-12,30e-12,20000,3e-12)
    # Independently assemble C*dV/dt+G*V=I for constant non-rolloff current.
    C=np.diag([f.cf,f.cs,f.c3]);a=1/f.r;b=1/f.r3
    G=np.array([[a+b,-a,-b],[-a,a,0],[-b,0,b]])
    matrix=np.zeros((4,4));matrix[:3,:3]=-np.linalg.solve(C,G)
    matrix[:3,3]=np.linalg.solve(C,[20e-6,0,0])
    expected=(expm(matrix*50e-9)@np.array([0,0,0,1.]))[:3]
    f.advance(50e-9,20e-6);error=float(np.max(abs(f.state[:3]-expected)));assert error<1e-9
    f.advance(200e-9,0);f.advance(250e-9,-20e-6)
    residual=float(f.energy-f.state[5]+f.state[6]);assert abs(residual)<1e-20
    fine=ThreeCapFilter(f.r,f.cf,f.cs,f.r3,f.c3)
    for t,current in [(50e-9,20e-6),(200e-9,0),(250e-9,-20e-6)]:fine.advance(t,current,max_step=.5e-9)
    refinement=float(np.max(abs(f.state[:3]-fine.state[:3])));assert refinement<1e-9
    near=ThreeCapFilter(f.r,f.cf,f.cs,f.r3,f.c3);near.state[:3]=.95
    e0=near.energy;near.advance(10e-9,20e-6)
    assert near.state[4]<20e-6*10e-9
    assert abs(near.energy-e0-near.state[5]+near.state[6])<1e-20
    invalid=copy.copy(f);invalid.state[0]=1.;before=invalid.state.copy()
    try:invalid.advance(invalid.time+1e-9,0)
    except ValueError:pass
    else:raise AssertionError('Invalid state accepted')
    assert np.array_equal(before,invalid.state)
    report=dict(status='passed_local',matrix_exponential_error_v=error,energy_residual_j=residual,step_refinement_error_v=refinement,
        limitations=['Local transient filter only; no PLL integration, resistor noise or physical qualification.','Finite model pump rolloff is assumed; no transistor current-law validation.'])
    (P/'evidence/three-cap-filter-screen.json').write_text(json.dumps(report,indent=2)+'\n');print(report)
if __name__=='__main__':main()
