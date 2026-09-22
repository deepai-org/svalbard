"""Finite-band resistor Norton forcing; seeded and independent of solver calls.

One-sided 4kT/R PSD is represented by logarithmic midpoint tones. This is a
finite spectral approximation, not white noise or transistor noise closure.
State[5] accumulates pump PLUS thermal-source work for energy accounting.
"""
import math
import numpy as np
from three_cap_centering import ThreeCapCenteringFilter

K_B = 1.380649e-23

class ResistorNoiseFilter(ThreeCapCenteringFilter):
    def __init__(self, *, temperature_k=300., noise_low_hz=100.,
                 noise_high_hz=10e6, noise_bins=64, noise_seed=1249, **kwargs):
        super().__init__(**kwargs)
        if not (math.isfinite(temperature_k) and temperature_k >= 0 and
                0 < noise_low_hz < noise_high_hz and math.isfinite(noise_high_hz)
                and isinstance(noise_bins,int) and noise_bins > 0):
            raise ValueError('Invalid thermal noise spectrum')
        edges=np.geomspace(noise_low_hz,noise_high_hz,noise_bins+1)
        self.noise_frequency=np.sqrt(edges[:-1]*edges[1:])
        widths=np.diff(edges)
        rng=np.random.default_rng(noise_seed)
        self.noise_phase=rng.uniform(0,2*np.pi,(2,noise_bins))
        self.noise_amplitude=np.sqrt(2*4*K_B*temperature_k*widths[None,:]/np.array([self.r,self.r3])[:,None])
        for array in (self.noise_frequency,self.noise_phase,self.noise_amplitude):
            array.flags.writeable=False
    def thermal_currents(self,time):
        return np.sum(self.noise_amplitude*np.cos(2*np.pi*self.noise_frequency*time+self.noise_phase),axis=1)
    def rhs(self,t,y,command):
        result=super().rhs(t,y,command)
        j1,j3=self.thermal_currents(t)
        result[0]+=(j1+j3)/self.cf
        result[1]-=j1/self.cs
        result[2]-=j3/self.c3
        result[5]+=j1*(y[0]-y[1])+j3*(y[0]-y[2])
        return result
