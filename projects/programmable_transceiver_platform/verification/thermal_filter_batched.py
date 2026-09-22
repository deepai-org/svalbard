"""Independent batched fixed-region thermal filter prototype; not live chip code."""
import copy
import numpy as np
from thermal_filter_guard_screen import safe_region
QUADRATURE={n:np.polynomial.legendre.leggauss(n) for n in (8,16)}


class Trajectory:
    def __init__(self,m,command):
        self.m=m
        c=np.array([m.cf,m.cs,m.c3]);root=np.sqrt(c)
        factor=(m.limit-np.sign(command)*m.state[0])/m.headroom if command else 1.
        slope=-abs(command)/m.headroom if 0<factor<1 else 0.
        offset=command*m.limit/m.headroom if 0<factor<1 else command*np.clip(factor,0,1)
        g=np.array([[slope-1/m.r-1/m.r3,1/m.r,1/m.r3],
                    [1/m.r,-1/m.r,0],[1/m.r3,0,-1/m.r3]])
        symmetric=g/root[:,None]/root[None,:]
        if m.center_enabled:symmetric-=np.eye(3)/m.center_tau
        eigenvectors=None
        self.lam,v=np.linalg.eigh(symmetric)
        self.forward=v/root[:,None];self.inverse=v.T*root[None,:]
        b=np.array([offset/m.cf,0.,0.])
        self.b=self.inverse@b
        forcing=np.array([[1/m.cf,1/m.cf],[-1/m.cs,0],[0,-1/m.c3]])
        omega=2j*np.pi*m.noise_frequency
        amplitude=m.noise_amplitude.T*np.exp(1j*m.noise_phase.T)
        modal_forcing=(self.inverse@forcing)@amplitude.T
        self.q=modal_forcing/(omega[None,:]-self.lam[:,None])
        self.q*=np.exp(omega*m.time)[None,:]
        self.h=self.inverse@m.state[:3]-np.real(self.q.sum(axis=1))
        self.omega=omega;self.slope=slope;self.offset=offset

    def states(self,delta):
        delta=np.asarray(delta)
        z=delta[:,None]*self.lam[None,:]
        # Entire functions avoid cancellation at the conserved-charge eigenvalue.
        small=abs(z)<1e-4
        safe=np.where(small,1.,z)
        f1=np.where(small,1+z/2+z*z/6+z**3/24+z**4/120,np.expm1(z)/safe)
        f2=np.where(small,.5+z/6+z*z/24+z**3/120+z**4/720,(np.expm1(z)-z)/safe**2)
        p1=delta[:,None]*f1;p2=delta[:,None]**2*f2
        tones=np.exp(delta[:,None]*self.omega[None,:])
        modal=np.exp(z)*self.h+p1*self.b+np.real(tones@self.q.T)
        integrated=p1*self.h+p2*self.b+np.real((np.expm1(delta[:,None]*self.omega)/self.omega)@self.q.T)
        voltages=modal@self.forward.T;integrals=integrated@self.forward.T
        return voltages,integrals


def batched_step(m,stop,command):
    if not safe_region(m,stop,command):
        out=copy.copy(m);out.advance(stop,command)
        return out,'radau_boundary_fallback'
    dt=stop-m.time
    trajectory=Trajectory(m,command)
    increments=[]
    for n in (8,16):
        nodes,weights=QUADRATURE[n];delta=dt*(nodes+1)/2
        voltage,_=trajectory.states(delta)
        v,w,u=voltage.T
        # Same absolute-time forcing as the reference solver.
        currents=np.array([m.thermal_currents(m.time+d) for d in delta])
        current=command*np.clip((m.limit-np.sign(command)*v)/m.headroom,0,1)
        work=current*v+currents[:,0]*(v-w)+currents[:,1]*(v-u)
        loss=(v-w)**2/m.r+(v-u)**2/m.r3
        if m.center_enabled:loss+=(m.cf*v*v+m.cs*w*w+m.c3*u*u)/m.center_tau
        increments.append(dt/2*np.array([weights@work,weights@loss]))
    if max(abs(increments[0]-increments[1]))>1e-24:
        out=copy.copy(m);out.advance(stop,command)
        return out,'radau_quadrature_fallback'
    out=copy.copy(m)
    voltage,integral=trajectory.states([dt])
    out.state[:3]=voltage[0]
    out.state[3]+=integral[0,2]
    out.state[4]+=trajectory.offset*dt+trajectory.slope*integral[0,0]
    out.state[5:7]+=increments[1];out.time=stop
    return out,'analytic'
