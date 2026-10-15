"""Shared sample packing and prescribed FIFO timing helpers.

This module retains numerical/codec utilities for scoped experiments. It no
longer constructs or simulates a chip; use architecture_fast.behavioral and the
selected electrical composition for current integration.
"""
from collections import deque
from fractions import Fraction
from pathlib import Path
import sys
import numpy as np

P = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(P/'verification'))
from stream_codec import encode, Receiver, slots
from loopback_return import return_samples

class Packer:
    """LSB-first continuous bit stream, with no per-sample padding."""
    def __init__(self):
        self.value = self.count = 0
    def push(self, value, width, output_width):
        assert 0 <= value < 1 << width
        self.value |= int(value) << self.count
        self.count += width
        words = []
        while self.count >= output_width:
            words.append(self.value & ((1 << output_width)-1))
            self.value >>= output_width
            self.count -= output_width
        return words


def encode_iq(z,bits):
    scale=1 << (bits-1);mask=(1 << bits)-1
    i=int(np.clip(np.rint(z.real*scale),-scale,scale-1))
    q=int(np.clip(np.rint(z.imag*scale),-scale,scale-1))
    return (i & mask) | ((q & mask) << bits)


def decode_iq(word,bits):
    scale=1 << (bits-1);mask=(1 << bits)-1
    def signed(value):return value-(1 << bits) if value & scale else value
    return complex(signed(word & mask)/scale,signed((word >> bits)&mask)/scale)


def paced_sink(values, arrivals, period, duration, start_delay, capacity_samples=None):
    """Merge actual arrivals and independently scheduled consumption deadlines.

    An arrival exactly at a deadline is available. Missing data records an
    underflow; no sample is synthesized and no consumption clock is stalled.
    """
    events=[(Fraction(t),0,value) for t,value in zip(arrivals,values)]
    index=0
    while index*period < duration:
        events.append((start_delay+index*period,1,index))
        index+=1
    assert capacity_samples is None or capacity_samples>0
    fifo=deque();peak=0;underflows=[];overflows=[];output=[]
    for when,kind,value in sorted(events):
        if kind==0:
            if capacity_samples is not None and len(fifo)>=capacity_samples:
                overflows.append((when,value))
            else:
                fifo.append(value);peak=max(peak,len(fifo))
        elif fifo:
            output.append((value,when,fifo.popleft()))
        else:
            underflows.append(value)
    assert len(values)==len(output)+len(fifo)+len(overflows)
    return dict(output=output,underflows=underflows,overflows=overflows,peak_samples=peak,
                remaining_samples=len(fifo))
