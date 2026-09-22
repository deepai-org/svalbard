"""Finite buffered detector-to-ADC readout settling, exact exponential forcing.

Detector pole a feeds isolated readout pole b. Buffer reverse loading and ADC
sampling kickback are not included. State persists across conversion/abort.
"""
import math
import numpy as np
from vector_power_detector import VectorPowerDetector

class SettlingDetector(VectorPowerDetector):
    def __init__(self,readout_tau_s=20e-9,**kwargs):
        super().__init__(**kwargs)
        if not math.isfinite(readout_tau_s) or readout_tau_s<=0:raise ValueError('Invalid readout time constant')
        self.readout_pole=1/readout_tau_s
        if abs(self.readout_pole-self.pole)<1e-6*max(self.pole,self.readout_pole):
            raise ValueError('Coincident cascade poles require a separate limit representation')
        self.readout_value=0.
    def advance(self,time,terms):
        if not math.isfinite(time) or time<self.time:raise ValueError('Invalid time')
        dt=time-self.time;a=self.pole;b=self.readout_pole
        data=np.asarray(terms,dtype=complex)
        if data.ndim!=2 or data.shape[1]!=2 or not len(data) or not np.all(np.isfinite(data)):
            raise ValueError('Invalid exponential terms')
        rates=data[:,1,None]+data[:,1].conjugate()[None,:]
        coeff=data[:,0,None]*data[:,0].conjugate()[None,:]
        def integral(pole):
            den=rates+pole;small=abs(den*dt)<1e-8
            result=np.empty_like(den);result[small]=dt*np.exp(-pole*dt)
            # Match original detector integral; near-resonance limit explicit.
            result[~small]=(np.exp(rates[~small]*dt)-np.exp(-pole*dt))/den[~small]
            return result
        readout=(self.readout_value*np.exp(-b*dt)+self.value*b*(np.exp(-a*dt)-np.exp(-b*dt))/(b-a)
                 +a*b/(b-a)*np.sum(coeff*(integral(a)-integral(b))))
        if not np.isfinite(readout) or abs(readout.imag)>1e-9 or readout.real< -1e-10:
            raise ValueError('Invalid readout state')
        super().advance(time,terms)
        self.readout_value=max(0.,float(readout.real))


# Shared ADC protocol helpers live beside detector state, not chip compositions.
from chip_model import decode_iq

def read_shared_detector(self):
    if self.pending is None or self.time<self.pending[0]:raise ValueError('ADC result not ready')
    _,epoch,power,invalid=self.pending;self.pending=None
    if epoch!=self.epoch:raise ValueError('Stale ADC result')
    return dict(epoch=epoch,power=power,overflow=invalid)

def sample_shared_detector(self,power,time):
    if time!=self.time or time!=self.tx.time:raise ValueError('ADC sample time mismatch')
    if not self.tx_cal.busy or not self.quiet() or self.adc_pending or self.maintenance_pending is not None:
        raise ValueError('Shared ADC not exclusively available')
    # Declared analog scaling: detector fullscale -> +0.8 normalized ADC input.
    scale=.8/self.tx_detector.fullscale
    had=hasattr(self,'bits');previous=getattr(self,'bits',None)
    clipped=self.adc_diagnostics['clipped_samples'];self.bits=12
    try:word=self.convert_adc(complex(power*scale,0.))
    finally:
        if had:self.bits=previous
        else:del self.bits
    value=decode_iq(word,12).real/scale
    self.tx_adc_samples+=1
    invalid=(power<0 or power>self.tx_detector.fullscale or
             self.adc_diagnostics['clipped_samples']>clipped)
    return value,invalid

class BufferedSharedDetector(SettlingDetector):
    signed_observations=True
    read=read_shared_detector
    def __init__(self,sample,**kwargs):
        super().__init__(**kwargs);self.sample=sample
    def request(self):
        if self.pending is not None:raise ValueError('ADC busy')
        power,invalid=self.sample(self.readout_value,self.time)
        self.pending=(self.time+self.latency,self.epoch,power,invalid)

