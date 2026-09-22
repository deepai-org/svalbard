"""Power-only affine TX I/Q calibration with bounded fixed-point correction.

Fits power(x)=x.T H x+2 h.T x+c from independent probe measurements.
A power detector cannot identify absolute RF phase; the correction leaves an
orthogonal rotation, which is immaterial to the existing scalar carrier fit.
This assumes a nonsingular positive-orientation mixer and a square-law monitor.
"""
import numpy as np

def probes(amplitude=.15):
    if not 0<amplitude<=.25:raise ValueError('Probe amplitude outside budget')
    return amplitude*np.array([0,1,-1,1j,-1j,1+1j,1-1j,-1+1j,-1-1j],complex)

def fit(probe_values,power,coefficient_bits=12,relative_gain=False,signed_observations=False):
    z=np.asarray(probe_values,complex);p=np.asarray(power,float)
    if z.ndim!=1 or z.shape!=p.shape or len(z)<6 or not np.all(np.isfinite(z)) or not np.all(np.isfinite(p)) or (not signed_observations and np.any(p<0)):
        raise ValueError('Finite aligned probe observations required; negative values require signed readout')
    if type(signed_observations) is not bool:raise ValueError('Readout policy must be boolean')
    # A signed ADC can report below-zero power estimates due to noise/offset.
    # Retain those observations; clipping them biases the quadratic fit.
    # Positive curvature and correction-range checks still apply.
    if not isinstance(coefficient_bits,int) or not 6<=coefficient_bits<=20:raise ValueError('Invalid precision')
    x=z.real;y=z.imag
    design=np.column_stack((x*x,2*x*y,y*y,2*x,2*y,np.ones(len(z))))
    if np.linalg.matrix_rank(design)!=6:raise ValueError('Unobservable probe set')
    q=np.linalg.lstsq(design,p,rcond=None)[0]
    H=np.array([[q[0],q[1]],[q[1],q[2]]]);h=q[3:5]
    eigen=np.linalg.eigvalsh(H)
    if eigen[0]<=0 or eigen[-1]/eigen[0]>4:raise ValueError('Invalid or ill-conditioned power response')
    # H = L L.T; C=L^-T ensures C.T H C=identity.
    C=np.linalg.inv(np.linalg.cholesky(H).T);b=-np.linalg.solve(H,h)
    if type(relative_gain) is not bool:raise ValueError('Gain policy must be boolean')
    # Unit determinant removes the unidentifiable common monitor gain.
    # Offset cancellation -H^-1 h is already invariant to positive power scale.
    if relative_gain:C=C/np.sqrt(np.linalg.det(C))
    step=2.**-coefficient_bits
    C=np.rint(C/step)*step;b=np.rint(b/step)*step
    if np.max(abs(C))>2 or np.max(abs(b))>.25:raise ValueError('Correction range exceeded')
    return dict(gain_policy='relative' if relative_gain else 'absolute_assumed_monitor_gain',matrix=C.tolist(),offset=b.tolist(),fractional_bits=coefficient_bits,
        fit_rms=float(np.sqrt(np.mean((design@q-p)**2))),condition=float(eigen[-1]/eigen[0]))

def correct(values,calibration,component_limit=1.):
    z=np.asarray(values,complex);C=np.asarray(calibration['matrix']);b=np.asarray(calibration['offset'])
    v=C@np.array([z.real,z.imag])+b[:,None]
    if not np.all(np.isfinite(v)) or np.max(abs(v))>component_limit:raise ValueError('Correction exceeds actuator headroom')
    return v[0]+1j*v[1]
