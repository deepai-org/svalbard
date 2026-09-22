"""Local comparison-system bound for fixed-region thermal filter trajectories.

For deviation d=x-x0, d'=A*d+f0+n. A is Metzler in each pump region,
so |d(t)| <= integral(exp(A*u),u=0..t)*(|f0|+noise_bound).
This componentwise bound grows monotonically and covers the whole interval.
Acceptance requires that its box avoids all voltage and pump-region boundaries.
Floating-point evaluation uses a cushion; this is not formal interval arithmetic.
"""
import numpy as np
from thermal_filter_guard_screen import safe_region as global_guard


def safe_region(model,stop,command):
    if global_guard(model,stop,command):return True
    dt=stop-model.time
    x=model.state[:3];m=model
    factor=(m.limit-np.sign(command)*x[0])/m.headroom if command else 1.
    slope=-abs(command)/m.headroom if 0<factor<1 else 0.
    offset=command*m.limit/m.headroom if 0<factor<1 else command*np.clip(factor,0,1)
    c=np.array([m.cf,m.cs,m.c3]);root=np.sqrt(c)
    g=np.array([[slope-1/m.r-1/m.r3,1/m.r,1/m.r3],
                [1/m.r,-1/m.r,0],[1/m.r3,0,-1/m.r3]])
    a=g/c[:,None]
    if m.center_enabled:a-=np.eye(3)/m.center_tau
    lam,v=np.linalg.eigh(root[:,None]*a/root[None,:])
    j1,j3=np.sum(m.noise_amplitude,axis=1)
    forcing=abs(a@x+np.array([offset/m.cf,0,0]))+np.array([(j1+j3)/m.cf,j1/m.cs,j3/m.c3])
    z=lam*dt;small=abs(z)<1e-4;safe=np.where(small,1.,z)
    phi=dt*np.where(small,1+z/2+z*z/6+z**3/24+z**4/120,np.expm1(z)/safe)
    radius=(v@(phi*(v.T@(root*forcing))))/root
    # Nonnegative comparison solution; negative values beyond rounding reject.
    if not np.all(np.isfinite(radius)) or min(radius)<-1e-12:return False
    radius=np.maximum(radius,0)+1e-10*max(1.,m.limit)
    if np.any(abs(x)+radius>=m.limit):return False
    if command and abs(np.sign(command)*x[0]-(m.limit-m.headroom))<=radius[0]:return False
    return True
