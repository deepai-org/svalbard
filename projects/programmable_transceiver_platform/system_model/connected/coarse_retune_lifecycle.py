"""Quiet-window counted RF retuning with finite passive filter recentering."""
import math
from coarse_acquisition import CoarseAcquisition
from coarse_startup_lifecycle import CoarseStartupChip
from recenter_filter import RecenteringClock

class RetuningAcquisition(CoarseAcquisition):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        # Bound on both capacitor nodes after the timer, not an observed voltage.
        self.bound+=self.clock.gains.kvco*self.clock.filter.limit*math.exp(-12)
        self.center_history=[]
    @property
    def busy(self):return self.state=='centering' or super().busy
    def start(self,time,target,epoch):
        if self.busy:raise ValueError('Coarse sequencer busy')
        if type(target) is not int or target%1000000 or not 2300000000<=target<=2500000000:
            raise ValueError('Coarse carrier outside accepted grid')
        if self.clock.coarse_initial_ready:return super().start(time,target,epoch)
        self.target=target;self.epoch=epoch;self.saved=self.clock.bank_code
        self.generation+=1;self.qualified=False;self.snapshot_pending=None;self.history=[]
        self.next_event=self.clock.start_center(time)
        self.state='centering'
        self.center_history.append(dict(start_s=time,deadline_s=self.next_event,epoch=epoch))
    def step(self,time,epoch,reference):
        if self.state!='centering':return super().step(time,epoch,reference)
        if epoch!=self.epoch or not reference:self.cancel(time);return
        if time!=self.next_event:raise ValueError('Centering event missed deadline')
        self.clock.finish_center(time)
        self.state='idle';self.next_event=None
        super().start(time,self.target,epoch)
    def cancel(self,time):
        if self.state=='centering':self.clock.cancel_center(time)
        return super().cancel(time)

class HeldRetuningClock(RecenteringClock):
    def __init__(self,**kwargs):
        super().__init__(**kwargs);self.set_reference(False,0.)

class CoarseRetuningChip(CoarseStartupChip):
    RF_CLOCK_CLASS=HeldRetuningClock
    COARSE_CLASS=RetuningAcquisition
    def execute_management(self,operation,payload,time):
        if operation=='rf_coarse_status' and self.coarse.state=='centering':
            if payload:raise ValueError('Reserved coarse status payload')
            return dict(value=9|256|(self.rf_pll.bank_code<<16))
        return super().execute_management(operation,payload,time)
