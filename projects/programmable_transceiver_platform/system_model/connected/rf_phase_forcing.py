"""Piecewise-linear oscillator phase forcing of exponential RF envelopes.

Phase callback supplies unwrapped radians relative to the network carrier.
It must describe an immutable/predictable interval; external clock/control
changes must split calls. Step convergence is required, not assumed exact.
"""
import math
import numpy as np

def advance_phase(load,end,source_terms,phase,max_step_s,breakpoints=()):
    start=load.network.time
    if not math.isfinite(end) or end<start or not math.isfinite(max_step_s) or max_step_s<=0:
        raise ValueError('Invalid phase forcing interval')
    if end==start:return dict(steps=0,max_midpoint_phase_error=0.)
    points=list(breakpoints)
    if any(not math.isfinite(t) for t in points) or points!=sorted(set(points)):
        raise ValueError('Breakpoints must be finite, sorted and unique')
    points=[t for t in points if start<t<end]
    if points:
        result=dict(steps=0,max_midpoint_phase_error=0.)
        for stop in points+[end]:
            offset=load.network.time-start
            local=[(a*np.exp(p*offset),p) for a,p in source_terms]
            part=advance_phase(load,stop,local,phase,max_step_s)
            result['steps']+=part['steps']
            result['max_midpoint_phase_error']=max(result['max_midpoint_phase_error'],part['max_midpoint_phase_error'])
        return result

    count=max(1,math.ceil((end-start)/max_step_s));error=0.
    p0=phase(start)
    for i in range(count):
        a=start+(end-start)*i/count;b=start+(end-start)*(i+1)/count
        p1=phase(b);pm=phase((a+b)/2)
        if not all(math.isfinite(v) for v in (p0,p1,pm)):raise ValueError('Invalid phase trajectory')
        slope=(p1-p0)/(b-a)
        error=max(error,abs(pm-(p0+p1)/2))
        terms=[(v*np.exp(rate*(a-start)+1j*math.remainder(p0,2*math.pi)),rate+1j*slope)
               for v,rate in source_terms]
        load.advance(b,terms);p0=p1
    return dict(steps=count,max_midpoint_phase_error=error)
