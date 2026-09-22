"""Conservative affine-power error bound for a declared probe envelope.

Assume |u(t)-u0| <= tail * exp(-decay_rate*t), detector dv/dt=(p-v)/tau,
p=|u*(1-cubic*|u|**2)|**2, and initial detector state in [lo, hi].
The readout is gain*v + offset + curvature*v**2/fullscale, then rounding.
Offset is part of the fitted affine power polynomial, not an error term here.
This bounds the mathematical model; envelope/parameter bounds must be supplied
independently before it can serve as a device acceptance criterion.
"""
import math


def probe_error_bound(*, amplitude, tail, decay_rate, dwell, tau,
                      initial_interval, cubic, gain, curvature, fullscale, bits):
    lo, hi = initial_interval
    values = (amplitude, tail, decay_rate, dwell, tau, lo, hi, cubic,
              gain, curvature, fullscale)
    if not all(math.isfinite(v) for v in values):
        raise ValueError('Nonfinite envelope')
    if min(amplitude, tail, lo, cubic) < 0 or hi < lo:
        raise ValueError('Invalid nonnegative envelope')
    if min(decay_rate, dwell, tau, gain, fullscale) <= 0 or bits not in (8, 10, 12):
        raise ValueError('Invalid time, readout or resolution')
    pole = 1/tau
    retention = math.exp(-pole*dwell)

    def convolve(n):
        # Stable integral of pole*exp(-pole*(T-t))*exp(-n*a*t).
        rate = n*decay_rate
        delta = pole-rate
        if delta == 0:
            return pole*dwell*retention
        if delta > 0:
            return pole*math.exp(-rate*dwell)*(-math.expm1(-delta*dwell))/delta
        return pole*retention*math.expm1(delta*dwell)/delta

    def envelope_moment(n):
        return sum(math.comb(n, j)*amplitude**(n-j)*tail**j*convolve(j)
                   for j in range(n+1))

    target = amplitude**2
    initial = max(abs(lo-target), abs(hi-target))*retention
    settling = 2*amplitude*tail*convolve(1)+tail**2*convolve(2)
    # Triangle bound on |-2*k*|u|^4 + k^2*|u|^6|, valid for any k>=0.
    compression = 2*cubic*envelope_moment(4)+cubic**2*envelope_moment(6)
    detector_error = initial+settling+compression
    upper = target+detector_error
    readout_curvature = abs(curvature)*upper**2/fullscale
    quantization = fullscale/((1 << bits)-1)/2
    return dict(absolute_error=gain*detector_error+readout_curvature+quantization,
                initial_state=gain*initial, settling=gain*settling,
                compression=gain*compression, curvature=readout_curvature,
                quantization=quantization, detector_upper=upper,
                scope='Declared envelope and parameters; unclipped rounded readout only.')
