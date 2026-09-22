"""Loaded passive filter with compliant pump and separate VCO control node."""
import math
import numpy as np
from scipy.integrate import solve_ivp

class ThreeCapFilter:
    def __init__(self,r,cf,cs,r3,c3,limit=1.,headroom=.1):
        if not all(math.isfinite(v) and v>0 for v in (r,cf,cs,r3,c3,limit,headroom)) or headroom>limit:
            raise ValueError('Invalid filter parameters')
        self.r,self.cf,self.cs,self.r3,self.c3=r,cf,cs,r3,c3
        self.limit,self.headroom=limit,headroom
        # pump v, slow w, VCO u, integrated u, pump charge, source work, R loss
        self.state=np.zeros(7);self.time=0.
    def __copy__(self):
        obj=object.__new__(type(self));obj.__dict__=self.__dict__.copy();obj.state=self.state.copy();return obj
    @property
    def energy(self):
        v,w,u=self.state[:3];return .5*(self.cf*v*v+self.cs*w*w+self.c3*u*u)
    def rhs(self,t,y,command):
        v,w,u=y[:3]
        current=command*min(1.,max(0.,(self.limit-math.copysign(1.,command)*v)/self.headroom)) if command else 0.
        a=(v-w)/self.r;b=(v-u)/self.r3
        return [(current-a-b)/self.cf,a/self.cs,b/self.c3,u,current,current*v,(v-w)*a+(v-u)*b]
    def advance(self,time,command,max_step=1e-9):
        if not all(math.isfinite(v) for v in (time,command,max_step)) or time<self.time or max_step<=0:
            raise ValueError('Invalid interval')
        if not np.all(np.isfinite(self.state)) or np.max(abs(self.state[:3]))>=self.limit:
            raise ValueError('Initial state outside compliance domain')
        if time==self.time:return
        def boundary(t,y):return self.limit-np.max(abs(y[:3]))
        boundary.terminal=True;boundary.direction=-1
        sol=solve_ivp(lambda t,y:self.rhs(t,y,command),(self.time,time),self.state,
            method='Radau',rtol=1e-9,atol=[1e-12]*3+[1e-20,1e-24,1e-24,1e-24],
            max_step=max_step,events=boundary)
        if not sol.success or sol.t[-1]!=time:raise ValueError('Filter compliance boundary or solve failure')
        self.state=sol.y[:,-1];self.time=time
