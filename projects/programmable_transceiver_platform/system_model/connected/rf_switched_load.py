"""Continuous complex-envelope RC isolation/dummy network.

C dv/dt + (G+j*omega*C)v = b for a fixed carrier, RMS voltage envelopes.
Four nodes: internal, pad, monitor, dummy resistor top. Fixed switch capacitors
retain charge across resistance changes. Device gate charge and nonlinearities
are absent; switch commands change resistance instantaneously, not voltage.
"""
import math
import numpy as np
from scipy.linalg import expm

class SwitchedLoad:
    def __init__(self,frequency_hz=2.412e9,feedthrough_f=1e-15,dummy_feedthrough_f=10e-15):
        if not math.isfinite(frequency_hz) or frequency_hz<=0:raise ValueError('Invalid carrier')
        if not all(math.isfinite(c) and c>=0 for c in (feedthrough_f,dummy_feedthrough_f)):raise ValueError('Invalid capacitance')
        self.omega=2*math.pi*frequency_hz
        self.C=np.diag([50e-15,100e-15,50e-15,20e-15])
        self.stamp(self.C,0,1,feedthrough_f)
        self.stamp(self.C,0,3,dummy_feedthrough_f)
        self.voltage=np.zeros(4,dtype=complex);self.time=0.
        self.configure(False,True)
    @staticmethod
    def stamp(matrix,i,j,value):
        matrix[i,i]+=value;matrix[j,j]+=value
        matrix[i,j]-=value;matrix[j,i]-=value
    def configure(self,output_on,dummy_on):
        self.output_on=bool(output_on);self.dummy_on=bool(dummy_on)
        self.G=np.diag([1/50,1/50,1/10000,1/50])
        self.stamp(self.G,0,1,1/(5 if output_on else 1e6))
        self.stamp(self.G,0,3,1/(5 if dummy_on else 1e6))
        self.stamp(self.G,0,2,1/1000)
        self.A=-np.linalg.solve(self.C,self.G)-1j*self.omega*np.eye(4)
    def reframe(self,frequency_hz,phase_delta_rad):
        """Change coordinates at current time: delta = new phase - old phase.

Caller must rotate source coefficients by the same exp(-j*delta) and shift
rates by -j*(new_omega-old_omega). This is not a physical oscillator retune.
Detector power and capacitor energy are invariant under the coordinate change.
"""
        if not math.isfinite(frequency_hz) or frequency_hz<=0 or not math.isfinite(phase_delta_rad):
            raise ValueError('Invalid carrier frame')
        rotation=np.exp(-1j*math.remainder(phase_delta_rad,2*math.pi))
        self.voltage*=rotation
        self.omega=2*math.pi*frequency_hz
        self.A=-np.linalg.solve(self.C,self.G)-1j*self.omega*np.eye(4)
        return rotation
    def steady(self,source):
        return np.linalg.solve(self.G+1j*self.omega*self.C,np.array([source/50,0,0,0]))
    def forecast(self,dt,source):
        if not math.isfinite(dt) or dt<0 or not np.isfinite(source):raise ValueError('Invalid interval/source')
        steady=self.steady(source)
        return steady+expm(self.A*dt)@(self.voltage-steady)
    def advance(self,time,source):
        self.voltage=self.forecast(time-self.time,source);self.time=time
        return self.voltage.copy()
    def energy(self,voltage=None):
        v=self.voltage if voltage is None else voltage
        return float(np.vdot(v,self.C@v).real/2)
