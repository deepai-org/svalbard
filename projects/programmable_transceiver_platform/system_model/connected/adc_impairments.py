"""Optional analog ADC transfer and input-referred noise before code quantization.
Parameters describe circuit behavior, never on-chip protocol profiles.
A cubic is a sensitivity model, not a claim about the measured GF180 ADC cause.
"""
import math
import random

class ADCImpairments:
    def __init__(self, noise_rms=0., cubic=0., seed=1, *,
                 sampling_r_ohm=None, sampling_c_f=None, acquisition_s=None,
                 odd_chebyshev=None):
        if not math.isfinite(noise_rms) or noise_rms < 0:
            raise ValueError('ADC noise RMS must be finite and nonnegative')
        if not math.isfinite(cubic) or cubic <= -1/3:
            raise ValueError('ADC transfer must remain monotonic over normalized full scale')
        coefficients=tuple(odd_chebyshev) if odd_chebyshev is not None else ()
        if coefficients:
            if len(coefficients)!=3 or not all(math.isfinite(v) for v in coefficients):
                raise ValueError('Supply finite Chebyshev coefficients for orders3,5,7')
            if cubic!=0:
                raise ValueError('Choose cubic or Chebyshev transfer, not both')
            # Sufficient monotonicity bound on[-1,1], since |Tn prime|<=n^2.
            if sum(n*n*abs(a) for n,a in zip((3,5,7),coefficients))>=1:
                raise ValueError('Chebyshev transfer exceeds supported monotonicity bound')
        self.odd_chebyshev=coefficients
        timing=(sampling_r_ohm,sampling_c_f,acquisition_s)
        if any(v is not None for v in timing):
            if any(v is None or not math.isfinite(v) or v<=0 for v in timing):
                raise ValueError('Sampling resistance, capacitance and acquisition time must all be positive and finite')
            tau=sampling_r_ohm*sampling_c_f
            if not math.isfinite(tau) or tau<=0:
                raise ValueError('Sampling RC time constant must be positive and finite')
            self.acquisition_fraction=-math.expm1(-acquisition_s/tau)
        else:
            self.acquisition_fraction=1.
        self.sampling_r_ohm=sampling_r_ohm
        self.sampling_c_f=sampling_c_f
        self.acquisition_s=acquisition_s
        self.held=0j
        self.noise_rms=noise_rms
        self.cubic=cubic
        self.rng=random.Random(seed)

    def sample(self, value):
        if not math.isfinite(value.real) or not math.isfinite(value.imag):
            raise ValueError('Nonfinite ADC input')
        # Exact RC update for a target held constant during the acquisition
        # window. This is a reduced scenario, not intra-window waveform integration.
        self.held=value if self.acquisition_fraction==1. else self.held+self.acquisition_fraction*(value-self.held)
        value=self.held
        def axis(x):
            # Tangent continuation outside full scale avoids an unphysical turn
            # in a negative cubic. Actual rail clipping remains the quantizer's job.
            a=abs(x)
            y=x+self.cubic*x*x*x if a<=1 else math.copysign(1+self.cubic+(a-1)*(1+3*self.cubic),x)
            if self.odd_chebyshev:
                c3,c5,c7=self.odd_chebyshev
                if a<=1:
                    x2=x*x
                    y=x+c3*x*(4*x2-3)+c5*x*(16*x2*x2-20*x2+5)+c7*x*(64*x2**3-112*x2*x2+56*x2-7)
                else:
                    y=math.copysign(1+c3+c5+c7+(a-1)*(1+9*c3+25*c5+49*c7),x)
            return y+(self.rng.gauss(0,self.noise_rms) if self.noise_rms else 0.)
        return complex(axis(value.real),axis(value.imag))
