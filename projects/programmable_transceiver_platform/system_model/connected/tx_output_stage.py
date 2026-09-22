"""Memoryless quadrature modulator/driver envelope in the local LO frame.

Parameters are sensitivity assumptions, not measured GF180 characteristics.
Compression acts after IQ imbalance and LO feedthrough, before carrier rotation.
No output impedance, thermal memory, harmonics at multiples of RF or supply feedback.
"""
import math
import numpy as np

def output_envelope(baseband, rotation, *, gain_imbalance_db=0., phase_error_deg=0.,
                    lo_feedthrough=0j, cubic=0.):
    values=(gain_imbalance_db, phase_error_deg, complex(lo_feedthrough).real,
            complex(lo_feedthrough).imag, cubic)
    if not all(math.isfinite(v) for v in values) or cubic<0:
        raise ValueError('Finite parameters and nonnegative compression required')
    z=np.asarray(baseband,dtype=complex);r=np.asarray(rotation,dtype=complex)
    if z.shape!=r.shape or not np.all(np.isfinite(z)) or not np.all(np.isfinite(r)):
        raise ValueError('Finite matching envelope and rotation arrays required')
    if not np.allclose(abs(r),1.,atol=1e-12,rtol=0):
        raise ValueError('Carrier rotation must have unit magnitude')
    g=10**(gain_imbalance_db/40)
    # Symmetric I/Q gains: their amplitude ratio is 10**(imbalance_db/20).
    u=g*z.real+1j/g*np.exp(1j*math.radians(phase_error_deg))*z.imag+lo_feedthrough
    compression=cubic*abs(u)**2
    if np.any(compression>=1/3):
        raise ValueError('Cubic stage beyond monotonic small-compression domain')
    return u*(1-compression)*r
