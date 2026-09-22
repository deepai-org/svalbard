"""Independent radial-power verification; deliberately not a waveform certificate."""
import math
import numpy as np

def verification_probes():
    # Rotated phases/radii differ from the nine training coordinates.
    phase=.173+2*np.pi*np.arange(16)/16
    return np.concatenate(([0j],.08*np.exp(1j*phase),.22*np.exp(1j*phase)))

def assess(values,powers,*,absolute_error_bound,relative_power_limit=.04,leakage_limit=1e-4):
    z=np.asarray(values,complex);p=np.asarray(powers,float)
    if z.ndim!=1 or p.shape!=z.shape or len(z)<17 or not np.all(np.isfinite(z)) or not np.all(np.isfinite(p)) or np.any(p<0):
        raise ValueError('Finite aligned nonnegative measurements required')
    if not all(math.isfinite(v) and v>=0 for v in (absolute_error_bound,relative_power_limit,leakage_limit)):
        raise ValueError('Invalid verification limits')
    ideal=abs(z)**2;active=ideal>0
    if not np.any(~active) or not np.any(active):raise ValueError('Zero and nonzero probes required')
    error=float(max((abs(p[active]-ideal[active])+absolute_error_bound)/ideal[active]))
    leakage=float(max(p[~active])+absolute_error_bound)
    return dict(power_verified=error<=relative_power_limit and leakage<=leakage_limit,
        worst_relative_power_error_bound=error,leakage_power_bound=leakage,
        waveform_verified=False,scope='Radial power only; cannot detect phase-only distortion or I/Q conjugation.')
