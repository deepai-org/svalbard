"""Carrier amplitude on complete measured clock cycles; no phase-noise inference."""
import numpy as np

def cycle_amplitude(time, signal, rising_edges):
    """Project output onto one sinusoidal cycle between successive reference edges.

    Strict input ordering; interpolate exact cycle endpoints. Remove each cycle's
    time-weighted DC before projection. Per-cycle phase is linear in time: this
    estimates carrier magnitude, not oscillator phase noise or harmonic distortion.
    """
    t=np.asarray(time);y=np.asarray(signal);edges=np.asarray(rising_edges)
    assert t.ndim==y.ndim==edges.ndim==1 and len(t)==len(y)
    assert np.isfinite(t).all() and np.isfinite(y).all() and np.isfinite(edges).all()
    assert np.all(np.diff(t)>0) and np.all(np.diff(edges)>0)
    values=[]
    for start,stop in zip(edges[:-1],edges[1:]):
        assert t[0]<=start<stop<=t[-1]
        tc=np.r_[start,t[(t>start)&(t<stop)],stop]
        yc=np.interp(tc,t,y);duration=stop-start
        yc=yc-np.trapezoid(yc,tc)/duration
        phase=2*np.pi*(tc-start)/duration
        real=2*np.trapezoid(yc*np.cos(phase),tc)/duration
        imag=2*np.trapezoid(yc*np.sin(phase),tc)/duration
        values.append(float(np.hypot(real,imag)))
    return values

if __name__=='__main__':
    # Known amplitude, DC offset and phase on a nonuniform sample grid.
    u=np.linspace(0,1,20001);t=3*u**1.1
    y=1.7+0.12*np.cos(2*np.pi*t+0.73)
    result=cycle_amplitude(t,y,np.arange(4.))
    assert len(result)==3 and max(abs(x-0.12) for x in result)<1e-7
    assert max(cycle_amplitude(t,np.full_like(t,2.3),np.arange(4.)))<1e-12
    print('Known sinusoid and DC projection checks passed')
