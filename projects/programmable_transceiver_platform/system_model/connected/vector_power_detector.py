"""Vectorized version of the existing exact exponential detector convolution.

No pole pruning, timestep relaxation or new detector approximation. Kept separate
until numerical equivalence and lifecycle tests justify composition changes.
"""
import math
import numpy as np
from tx_power_detector import PowerDetector

class VectorPowerDetector(PowerDetector):
    def advance(self,time,terms):
        if not math.isfinite(time) or time<self.time:raise ValueError('Nonmonotonic time')
        if not terms:raise ValueError('Invalid exponential terms')
        data=np.asarray(terms,dtype=complex)
        if data.ndim!=2 or data.shape[1]!=2 or not np.all(np.isfinite(data)):
            raise ValueError('Invalid exponential terms')
        dt=time-self.time;decay=math.exp(-self.pole*dt)
        amplitudes=data[:,0];rates=data[:,1]
        rate=rates[:,None]+rates.conjugate()[None,:];den=rate+self.pole
        small=abs(den*dt)<1e-10
        integral=np.empty_like(rate);integral[small]=dt*decay
        integral[~small]=(np.exp(rate[~small]*dt)-decay)/den[~small]
        result=self.value*decay+self.pole*np.sum(amplitudes[:,None]*amplitudes.conjugate()[None,:]*integral)
        if not np.isfinite(result) or abs(result.imag)>1e-9 or result.real < -1e-10:
            raise ValueError('Invalid detector power')
        self.value=max(0.,float(result.real));self.time=time
