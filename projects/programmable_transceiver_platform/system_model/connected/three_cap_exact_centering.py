"""Exact linear passive-centering propagation; active pump retains Radau."""
import math
import numpy as np
from scipy.linalg import expm
from three_cap_centering import ThreeCapCenteringFilter

class ExactCenteringFilter(ThreeCapCenteringFilter):
    def advance(self,time,command,max_step=1e-9):
        if not self.center_enabled:return super().advance(time,command,max_step)
        if command or not all(math.isfinite(v) for v in (time,command,max_step)) or time<self.time or max_step<=0:
            raise ValueError('Centering requires held pump and valid interval')
        if not np.all(np.isfinite(self.state)) or max(abs(self.state[:3]))>=self.limit:
            raise ValueError('Initial state outside compliance domain')
        dt=time-self.time
        if not dt:return
        caps=np.array([self.cf,self.cs,self.c3]);a=1/self.r;b=1/self.r3
        conductance=np.array([[a+b,-a,-b],[-a,a,0],[-b,0,b]])+np.diag(caps/self.center_tau)
        matrix=np.zeros((4,4));matrix[:3,:3]=-conductance/caps[:,None];matrix[3,2]=1
        result=expm(matrix*dt)@np.r_[self.state[:3],0.]
        # Passive RC diffusion plus positive shunts obeys a maximum principle:
        # no interior node magnitude exceeds the initial maximum.
        old_energy=self.energy
        self.state[:3]=result[:3];self.state[3]+=result[3]
        self.state[6]+=old_energy-self.energy
        self.time=time
