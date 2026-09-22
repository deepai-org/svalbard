"""Bound affine power-fit coefficients from bounded independent probe errors.

For p=Dq+e, |e_i|<=epsilon_i, least-squares qhat=D+ p gives
|qhat-q|<=|D+| epsilon. Frobenius norm bounds spectral error in H.
These are affine-model bounds, not a certificate for nonlinear RF or EVM.
"""
import numpy as np

def bound(probes,powers,absolute_errors,calibration):
    z=np.asarray(probes,complex);p=np.asarray(powers,float)
    errors=np.broadcast_to(np.asarray(absolute_errors,float),p.shape)
    if z.ndim!=1 or z.shape!=p.shape or len(z)<6 or not np.all(np.isfinite(z)) or not np.all(np.isfinite(p)) or not np.all(np.isfinite(errors)) or np.any(errors<0):
        raise ValueError('Invalid bounded observations')
    x=z.real;y=z.imag;D=np.column_stack((x*x,2*x*y,y*y,2*x,2*y,np.ones(len(z))))
    if np.linalg.matrix_rank(D)!=6:raise ValueError('Unobservable probes')
    inv=np.linalg.pinv(D);q=inv@p;delta=abs(inv)@errors
    H=np.array([[q[0],q[1]],[q[1],q[2]]]);h=q[3:5]
    dh=float(np.linalg.norm(delta[3:5]));dH=float(np.sqrt(delta[0]**2+2*delta[1]**2+delta[2]**2))
    C=np.asarray(calibration['matrix'],float);b=np.asarray(calibration['offset'],float)
    if C.shape!=(2,2) or b.shape!=(2,) or not np.all(np.isfinite(C)) or not np.all(np.isfinite(b)):
        raise ValueError('Invalid actuator')
    K=C.T@H@C;dK=float(np.linalg.norm(C,2)**2*dH)
    eig=np.linalg.eigvalsh(K);lower=float(eig[0]-dK);upper=float(eig[1]+dK)
    h_lower=float(np.linalg.eigvalsh(H)[0]-dH)
    robust=lower>0 and h_lower>0
    residual=float(np.linalg.norm(H@b+h)+dH*np.linalg.norm(b)+dh)
    return dict(coefficient_error_bounds=delta.tolist(),hessian_spectral_error_bound=dH,
        corrected_gram_eigenvalue_bounds=[lower,upper],robust_positive_definite=bool(robust),
        relative_axis_spread_bound=float((np.sqrt(upper)-np.sqrt(lower))/(np.sqrt(upper)+np.sqrt(lower))) if robust else None,
        residual_output_offset_bound=residual/np.sqrt(h_lower) if robust else None,
        waveform_verified=False,scope='Affine model and declared per-probe error only; residual offset is in monitor-scaled amplitude units.')
