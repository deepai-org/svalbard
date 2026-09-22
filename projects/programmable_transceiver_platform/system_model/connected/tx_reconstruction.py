"""Normalized continuous-time TX reconstruction; exact held-input propagation."""
import math
import numpy as np
from scipy import signal

class Reconstruction:
    def __init__(self,kind='elliptic',pass_hz=8e6,stop_hz=12e6,ripple_db=.9,rejection_db=30.,buffer_hz=80e6):
        if not 0<pass_hz<stop_hz or not 0<ripple_db<rejection_db or buffer_hz<=stop_hz:
            raise ValueError('Invalid reconstruction specification')
        self.scale=2*math.pi*pass_hz;ratio=stop_hz/pass_hz
        if kind=='elliptic':
            n,wn=signal.ellipord(1,ratio,ripple_db,rejection_db,analog=True)
            z,p,k=signal.ellip(n,ripple_db,rejection_db,wn,analog=True,output='zpk')
        elif kind=='butterworth':
            n,wn=signal.buttord(1,ratio,ripple_db,rejection_db,analog=True)
            z,p,k=signal.butter(n,wn,analog=True,output='zpk')
        elif kind=='chebyshev':
            n,wn=signal.cheb1ord(1,ratio,ripple_db,rejection_db,analog=True)
            z,p,k=signal.cheby1(n,ripple_db,wn,analog=True,output='zpk')
        else:raise ValueError('Unknown reconstruction family')
        self.kind=kind;self.order=int(n);self.pass_hz=pass_hz
        self.zero=z;self.core_poles=p;self.buffer_ratio=buffer_hz/pass_hz
        self.poles=np.append(p,-self.buffer_ratio);self.gain=k*self.buffer_ratio
        self.b,self.a=signal.zpk2tf(z,self.poles,self.gain)
        self.residues,self.modal_poles,direct=signal.residue(self.b,self.a)
        if len(direct) or min(abs(np.diff(np.sort_complex(self.modal_poles))))<1e-10:
            raise ValueError('Strictly proper distinct-pole reconstruction required')
        if not np.all(self.modal_poles.real<0):raise ValueError('Unstable reconstruction')
        self.states=np.zeros(len(self.modal_poles),complex);self.time=0.
    def projected(self,time,held):
        if not math.isfinite(time) or time<self.time:raise ValueError('Nonmonotonic reconstruction time')
        u=complex(held)
        if not math.isfinite(u.real) or not math.isfinite(u.imag):raise ValueError('Nonfinite held input')
        x=self.modal_poles*(self.scale*(time-self.time))
        return self.states*np.exp(x)+u*np.expm1(x)/self.modal_poles
    def value(self,time,held):return complex(np.sum(self.residues*self.projected(time,held)))
    def advance(self,time,held):
        self.states=self.projected(time,held);self.time=time
        return complex(np.sum(self.residues*self.states))
    def terms(self,held):
        equilibrium=-complex(held)/self.modal_poles
        return [(complex(np.sum(self.residues*equilibrium)),0j)]+[
            (complex(r*(x-eq)),complex(p*self.scale)) for r,x,eq,p in zip(self.residues,self.states,equilibrium,self.modal_poles)]
    def response(self,frequencies_hz):
        return signal.freqs_zpk(self.zero,self.poles,self.gain,worN=2*math.pi*np.asarray(frequencies_hz)/self.scale)[1]
    def metrics(self):
        return dict(kind=self.kind,core_order=self.order,total_order=len(self.poles),pass_hz=self.pass_hz,
            core_poles_hz=[[float(z.real*self.pass_hz),float(z.imag*self.pass_hz)] for z in self.core_poles],
            pole_pair_q=[float(abs(z)/(-2*z.real)) for z in self.core_poles if z.imag>0],
            buffer_pole_hz=self.buffer_ratio*self.pass_hz,
            normalized_numerator=self.b.tolist(),normalized_denominator=self.a.tolist())
