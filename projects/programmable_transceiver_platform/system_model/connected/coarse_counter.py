"""Finite coherent counter snapshots with explicit freshness and delivery bounds.

A held snapshot arrives after a fixed modeled CDC latency. It may contain the
current prescaled count or its predecessor. This is an assumed handshake/CDC
contract, not a metastability or implementation qualification.
"""
import math

class CoarseCounter:
    def __init__(self,window_s,prescale=16,bits=12,latency_s=50e-9,frequency_ceiling_hz=3e9,ages=(0,0)):
        if type(bits) is not int or not 2<=bits<=32 or type(prescale) is not int or prescale<1:
            raise ValueError('Invalid finite counter dimensions')
        if not all(math.isfinite(x) for x in (window_s,latency_s,frequency_ceiling_hz)) or not 0<latency_s<window_s or frequency_ceiling_hz<=0:
            raise ValueError('Invalid counter observation timing')
        if len(ages)!=2 or any(type(a) is not int or a not in (0,1) for a in ages):
            raise ValueError('Counter snapshots allow current or previous count only')
        self.modulus=1<<bits;self.bits=bits;self.prescale=prescale;self.latency=latency_s;self.ages=tuple(ages)
        # At most one modular wrap; two ambiguous endpoint counts reserved.
        if window_s*frequency_ceiling_hz/prescale+2>=self.modulus:
            raise ValueError('Measurement window can alias finite counter wraps')
        self.error_hz=2*prescale/window_s
        self.frequency_ceiling_hz=frequency_ceiling_hz
        self.maximum_delta=math.ceil(window_s*frequency_ceiling_hz/prescale)+2
    def snapshot(self,absolute_count,endpoint):
        return (absolute_count-self.ages[endpoint])%self.modulus
    def delta(self,start,end):
        if any(type(x) is not int or not 0<=x<self.modulus for x in (start,end)):
            raise ValueError('Malformed coherent counter snapshot')
        value=(end-start)%self.modulus
        if value>self.maximum_delta:raise ValueError('Counter interval exceeds declared envelope')
        return value
