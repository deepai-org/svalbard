"""Hypothetical signal-dependent ADC reference span; not a SAR fit."""
import numpy as np


def apply(values,fs,strength,tau=50e-9):
    assert fs>0 and tau>0 and abs(strength)<1
    decay=np.exp(-1/(fs*tau));state=0.;previous=0j
    output=[];spans=[]
    for value in values:
        # Use only earlier activity in this sample's effective reference span.
        span=1+strength*state
        spans.append(span);output.append(value/span)
        activity=min(abs(value-previous),1.)
        state=decay*state+(1-decay)*activity
        previous=value
    return np.asarray(output),np.asarray(spans)


def controls():
    z=np.array([1,1,1,0,1j],complex);fs=20e6;tau=50e-9
    out,span=apply(z,fs,0,tau)
    assert np.array_equal(out,z) and np.array_equal(span,np.ones(len(z)))
    for sign in (-1,1):
        out,span=apply(z,fs,sign*.1,tau)
        d=np.exp(-1/(fs*tau))
        assert span[0]==1
        assert abs(span[1]-(1+sign*.1*(1-d)))<1e-14
        assert abs(span[2]-(1+sign*.1*d*(1-d)))<1e-14
        changed=z.copy();changed[-1]=100
        _,other=apply(changed,fs,sign*.1,tau)
        assert np.array_equal(span,other)
        assert np.all((span>=.9)&(span<=1.1))
