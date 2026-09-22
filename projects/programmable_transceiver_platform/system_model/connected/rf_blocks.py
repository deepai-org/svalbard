"""Uncalibrated RF-envelope blocks; continuous-time one-pole responses."""
import numpy as np


def tone_response(t, amplitude, frequency_hz, bandwidth_hz, gain=1):
    """Zero-state response to amplitude*exp(j*w*t), applied at t=0."""
    pole=2*np.pi*bandwidth_hz
    omega=2*np.pi*frequency_hz
    return gain*amplitude*pole/(pole+1j*omega)*(np.exp(1j*omega*t)-np.exp(-pole*t))


def held_response(values, times, bandwidth_hz):
    """DAC updates at times[i]; return output just before each next update.

    Last sample is held for the preceding update interval. Initial state is zero.
    """
    assert len(values)==len(times) and len(times)>1
    dt=np.diff(times)
    assert np.all(dt>0)
    durations=np.r_[dt,dt[-1]]
    state=0j;out=[]
    for value,duration in zip(values,durations):
        state=value+(state-value)*np.exp(-2*np.pi*bandwidth_hz*duration)
        out.append(state)
    return np.asarray(out)


def controls():
    bw=2e6;t=np.arange(10)*1e-8
    dc=tone_response(t, .4, 0, bw)
    assert np.allclose(dc,.4*(1-np.exp(-2*np.pi*bw*t)),rtol=1e-13,atol=1e-14)
    held=held_response(np.full(10,.4),t,bw)
    assert np.allclose(held,.4*(1-np.exp(-2*np.pi*bw*(t+1e-8))),rtol=1e-13,atol=1e-14)
    # Splitting a hold into two intervals must preserve its endpoint.
    coarse=held_response([1j,1j],[0,2e-8],bw)
    fine=held_response([1j]*4,np.arange(4)*1e-8,bw)
    assert np.allclose(coarse,fine[1::2],rtol=1e-13,atol=1e-14)


def cascade_held_response(values,times,bandwidth_hz,attenuation=1):
    """Two equal-pole filters separated by external attenuation, sampled at hold ends.

    Integrates the continuous first-stage trajectory; does not replace it with
    a held endpoint feeding stage two. Both initial states are zero.
    """
    assert len(values)==len(times) and len(times)>1 and attenuation>=0
    dt=np.diff(times);assert np.all(dt>0)
    state1=state2=0j;out=[];pole=2*np.pi*bandwidth_hz
    for value,duration in zip(values,np.r_[dt,dt[-1]]):
        decay=np.exp(-pole*duration)
        state2=value+(state2-value)*decay+(state1-value)*pole*duration*decay
        state1=value+(state1-value)*decay
        out.append(attenuation*state2)
    return np.asarray(out)


def cascade_controls():
    t=np.arange(20)*1e-8;pole=2*np.pi*2e6
    actual=cascade_held_response(np.ones(20),t,2e6,.25)
    elapsed=t+1e-8
    expected=.25*(1-(1+pole*elapsed)*np.exp(-pole*elapsed))
    assert np.allclose(actual,expected,rtol=1e-12,atol=1e-14)
    assert np.array_equal(cascade_held_response(np.ones(20),t,2e6,0),np.zeros(20))
    coarse=cascade_held_response([1j]*2,[0,2e-8],2e6)
    fine=cascade_held_response([1j]*4,np.arange(4)*1e-8,2e6)
    assert np.allclose(coarse,fine[1::2],rtol=1e-13,atol=1e-14)


def mixed_cascade(values,times,bandwidth_hz,attenuation=1,lo_offset_hz=0):
    """Continuous LO rotation between TX and RX filters; positive offset raises IF."""
    if lo_offset_hz==0:
        return cascade_held_response(values,times,bandwidth_hz,attenuation)
    dt=np.diff(times);assert len(dt)>0 and np.all(dt>0)
    pole=2*np.pi*bandwidth_hz;omega=2*np.pi*lo_offset_hz
    first=second=0j;out=[]
    for value,start,duration in zip(values,times,np.r_[dt,dt[-1]]):
        decay=np.exp(-pole*duration);rotation=np.exp(1j*omega*duration)
        forced=value*(rotation-decay)/(pole+1j*omega)
        transient=(first-value)*decay*np.expm1(1j*omega*duration)/(1j*omega)
        second=second*decay+attenuation*pole*np.exp(1j*omega*start)*(forced+transient)
        first=value+(first-value)*decay
        out.append(second)
    return np.asarray(out)


def mixer_controls():
    t=np.arange(20)*1e-8;values=np.ones(20)
    positive=mixed_cascade(values,t,2e6,.25,1e6)
    negative=mixed_cascade(values,t,2e6,.25,-1e6)
    assert np.allclose(positive,np.conj(negative),rtol=1e-13,atol=1e-14)
    # Independent quadrature of the continuous first-stage DC-step response.
    duration=1e-8;grid=np.linspace(0,duration,10001);pole=2*np.pi*2e6
    integrand=.25*pole*(1-np.exp(-pole*grid))*np.exp(1j*2*np.pi*1e6*grid)*np.exp(-pole*(duration-grid))
    reference=np.sum((integrand[1:]+integrand[:-1])*np.diff(grid)/2)
    assert abs(positive[0]-reference)<1e-10
    coarse=mixed_cascade([1j]*2,[0,2e-8],2e6,1,1e6)
    fine=mixed_cascade([1j]*4,np.arange(4)*1e-8,2e6,1,1e6)
    assert np.allclose(coarse,fine[1::2],rtol=1e-12,atol=1e-14)


def iq_error(values,gain_error,phase_error_deg):
    """Constant receiver I/Q mismatch; hypothetical equal-bandwidth branches."""
    phase=np.deg2rad(phase_error_deg)
    matrix=np.array([[1+gain_error,0],[np.sin(phase),(1-gain_error)*np.cos(phase)]])
    values=np.asarray(values)
    output=matrix @ np.vstack((values.real,values.imag))
    return output[0]+1j*output[1],float(np.linalg.norm(matrix,2))


def iq_controls():
    z=np.array([1+0j,1j,-1-1j])
    out,norm=iq_error(z,0,0)
    assert np.array_equal(out,z) and norm==1
    out,_=iq_error(z,.1,0)
    assert np.allclose(out,[1.1,.9j,-1.1-.9j])
    out,_=iq_error(z,0,90)
    assert abs(out[0]-(1+1j))<1e-14 and abs(out[1])<1e-14
