"""Exhaustive 9-probe error-box corners and weak-resolution controls."""
import itertools,json
import numpy as np
from chip_model import P
from tx_iq_calibration import probes,fit
from tx_output_stage import output_envelope
from tx_fit_uncertainty import bound

def main():
    z=probes();truth=abs(output_envelope(z,np.ones(len(z)),gain_imbalance_db=.5,phase_error_deg=5.,lo_feedthrough=.0025))**2
    rows=[]
    for bits,gain in ((10,.003),(10,.56),(12,.56)):
        step=.1/((1<<bits)-1);measured=np.rint(truth*gain/step)*step
        cal=fit(z,measured,relative_gain=True);r=bound(z,measured,step/2,cal)
        x=z.real;y=z.imag;D=np.column_stack((x*x,2*x*y,y*y,2*x,2*y,np.ones(len(z))));inv=np.linalg.pinv(D)
        C=np.array(cal['matrix']);lo,hi=r['corrected_gram_eigenvalue_bounds']
        for signs in itertools.product((-1,1),repeat=len(z)):
            q=inv@(measured+step/2*np.array(signs));H=np.array([[q[0],q[1]],[q[1],q[2]]])
            eig=np.linalg.eigvalsh(C.T@H@C)
            assert eig[0]>=lo-1e-12 and eig[-1]<=hi+1e-12
        rows.append(dict(bits=bits,gain=gain,bound=r,corners=512))
    assert not rows[0]['bound']['robust_positive_definite']
    assert rows[-1]['bound']['robust_positive_definite']
    assert rows[-1]['bound']['relative_axis_spread_bound']<.01
    # Declared non-quantization uncertainty must weaken rather than improve the bound.
    cal=fit(z,truth*.56,relative_gain=True)
    a=bound(z,truth*.56,1e-5,cal);b=bound(z,truth*.56,1e-3,cal)
    assert b['hessian_spectral_error_bound']>a['hessian_spectral_error_bound']
    report=dict(status='passed',cases=rows,limitations=['Error-box corners verify linear coefficient enclosures; not transistor uncertainty or RF waveform certification.',
        'Settling, readout curvature, additive detector noise and model discrepancy must be included in the declared observation bounds.',
        'No managed acceptance gate yet; a defensible total error allocation is still required.'])
    (P/'evidence/connected-tx-fit-uncertainty.json').write_text(json.dumps(report,indent=2)+'\n')
    print([(r['bits'],r['gain'],r['bound']['robust_positive_definite'],r['bound']['relative_axis_spread_bound']) for r in rows])
if __name__=='__main__':main()
