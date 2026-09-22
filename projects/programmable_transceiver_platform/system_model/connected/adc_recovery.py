"""Assumed input-referred overload memory at sampled ADC decisions.

Each conversion deposits gain times excess beyond +/-1 into a bounded residual;
that residual decays continuously between decisions. This is an uncertainty
model for sampled overload, not a GF180 comparator characterization.
"""
import math

class ADCRecovery:
    def __init__(self,tau_s=0.,gain=0.,limit=.25):
        if not all(math.isfinite(x) for x in (tau_s,gain,limit)) or tau_s<0 or gain<0 or limit<=0:
            raise ValueError('Invalid ADC recovery parameters')
        self.tau=tau_s;self.gain=gain;self.limit=limit
        self.time=0.;self.residual=0j;self.overloads=0
    def sample(self,value,time):
        if not math.isfinite(time) or time<self.time or not all(math.isfinite(x) for x in (value.real,value.imag)):
            raise ValueError('Invalid recovery input/time')
        decay=math.exp(-(time-self.time)/self.tau) if self.tau else 0.
        self.residual*=decay;self.time=time
        excess=complex(*(x-max(-1.,min(1.,x)) for x in (value.real,value.imag)))
        self.overloads+=int(excess!=0)
        result=value+self.residual
        if self.tau:
            next_state=self.residual+self.gain*excess
            self.residual=complex(*(max(-self.limit,min(self.limit,x)) for x in (next_state.real,next_state.imag)))
        return result
