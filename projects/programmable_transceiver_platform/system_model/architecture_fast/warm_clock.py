"""Finite exponential fine-control centering before counter-based bank search."""
import math
from coarse_clock import CoarseSampledClock
from coarse_acquisition import CoarseAcquisition

class WarmClock(CoarseSampledClock):
    def __init__(self,center_tau_s=200e-9,**kwargs):
        if not math.isfinite(center_tau_s) or center_tau_s<=0:raise ValueError('Invalid center time constant')
        self.centering=False;self.center_tau=center_tau_s
        super().__init__(**kwargs)
    def centered_voltage(self,time):
        return self.center_initial*math.exp(-(time-self.center_epoch)/self.center_tau)
    def control(self,error=None,integral=None):
        if self.centering:return self.centered_voltage(self.time)
        return super().control(error,integral)
    def derivative(self,error,integral,time=None):
        if not self.centering:return super().derivative(error,integral,time)
        if time is None:time=self.time
        frequency=self.free_hz+self.kvco*self.centered_voltage(time)+self.supply_shift_hz+self.rail_frequency(time)+self.frequency_noise.frequency(time)
        return self.reference_hz-frequency/self.divider,-integral/self.center_tau
    def start_center(self,time):
        if self.centering:raise ValueError('Centering already active')
        self.advance(time);self.set_reference(False,time)
        self.center_initial=self.hold_voltage;self.center_epoch=time
        self.centering=True;self.coarse_initial_ready=False
        self.good=0;self.locked=False
        return time+12*self.center_tau
    def finish_center(self,time):
        if not self.centering or time<self.center_epoch+12*self.center_tau:
            raise ValueError('Center interval incomplete')
        self.advance(time);self.hold_voltage=self.centered_voltage(time)
        self.centering=False;self.coarse_initial_ready=True
    def cancel_center(self,time):
        if self.centering:
            self.advance(time);self.hold_voltage=self.centered_voltage(time)
            self.centering=False;self.coarse_initial_ready=False

class WarmAcquisition(CoarseAcquisition):
    def __init__(self,clock,**kwargs):
        super().__init__(clock,**kwargs)
        self.bound+=clock.kvco*clock.rail*math.exp(-12)
    @property
    def busy(self):return self.state=='centering' or super().busy
    def start(self,time,target,epoch):
        if self.busy:raise ValueError('Coarse sequencer busy')
        if type(target) is not int or target%1000000 or not 2300000000<=target<=2500000000:
            raise ValueError('Carrier outside candidate grid')
        self.target=target;self.epoch=epoch;self.qualified=False;self.generation+=1
        self.snapshot_pending=None;self.history=[]
        self.next_event=self.clock.start_center(time);self.state='centering'
    def step(self,time,epoch,reference):
        if self.state!='centering':return super().step(time,epoch,reference)
        if epoch!=self.epoch or not reference:self.cancel(time);return
        if time!=self.next_event:raise ValueError('Center event missed')
        self.clock.finish_center(time)
        self.state='idle';self.next_event=None
        super().start(time,self.target,epoch)
    def cancel(self,time):
        if self.state=='centering':
            self.clock.cancel_center(time);self.state='cancelled';self.qualified=False
            self.generation+=1;self.next_event=None;self.snapshot_pending=None;return
        return super().cancel(time)
