"""Nonblocking startup bank search with integer counter observations only."""
import math
from coarse_counter import CoarseCounter

class CoarseAcquisition:
    def __init__(self,clock,guard_s=2e-6,window_s=2e-6,tau_bound_s=200e-9,span_bound_hz=375e6,noise_bound_hz=0.,fine_margin_hz=150e6,counter_ages=(0,0),snapshot_latency_s=50e-9):
        vals=(guard_s,window_s,tau_bound_s,span_bound_hz,noise_bound_hz,fine_margin_hz)
        if not all(math.isfinite(x) for x in vals) or min(window_s,tau_bound_s,span_bound_hz,fine_margin_hz)<=0 or min(guard_s,noise_bound_hz)<0:raise ValueError('Invalid coarse acquisition contract')
        self.counter=CoarseCounter(window_s,ages=counter_ages,latency_s=snapshot_latency_s)
        self.clock=clock;self.guard=guard_s;self.window=window_s;self.prescale=16
        self.residue=span_bound_hz*math.exp(-guard_s/tau_bound_s)
        self.bound=self.counter.error_hz+self.residue*tau_bound_s/window_s*(-math.expm1(-window_s/tau_bound_s))+noise_bound_hz
        self.margin=fine_margin_hz;self.state='idle';self.next_event=None;self.qualified=False;self.history=[];self.generation=0
    @property
    def busy(self):return self.state in ('settle','start_wait','measure','end_wait','commit')
    def start(self,time,target,epoch):
        if self.busy or self.clock.present or not self.clock.coarse_initial_ready:raise ValueError('Coarse startup requires unused held fine loop')
        if type(target) is not int or target%1000000 or not 2300000000<=target<=2500000000:raise ValueError('Coarse carrier outside accepted grid')
        self.clock.advance(time)
        self.target=target;self.epoch=epoch;self.saved=self.clock.bank_code;self.generation+=1
        self.low=0;self.high=15;self.history=[];self.qualified=False;self.snapshot_pending=None
        self._trial(time)
    def _trial(self,time):
        self.code=(self.low+self.high)//2
        self.clock.write_bank(time,self.code,self.guard)
        self.state='settle';self.next_event=time+self.guard
    def cancel(self,time):
        if self.busy:
            self.clock.set_reference(False,time)
            self.clock.write_bank(time,self.saved,self.guard)
            self.state='cancelled';self.qualified=False;self.generation+=1;self.next_event=None;self.snapshot_pending=None
    def step(self,time,epoch,reference):
        if not self.busy:return
        if epoch!=self.epoch or not reference:self.cancel(time);return
        if time!=self.next_event:raise ValueError('Coarse event must be serviced at its deadline')
        if self.state=='settle':
            self.measurement_start=time
            value=self.counter.snapshot(self.clock.counter(time,self.prescale),0)
            self.snapshot_pending=(self.generation,value)
            self.state='start_wait';self.next_event=time+self.counter.latency
        elif self.state=='start_wait':
            generation,self.begin_count=self.snapshot_pending
            if generation!=self.generation:raise ValueError('Stale start snapshot')
            self.snapshot_pending=None
            self.state='measure';self.next_event=self.measurement_start+self.window
        elif self.state=='measure':
            value=self.counter.snapshot(self.clock.counter(time,self.prescale),1)
            self.snapshot_pending=(self.generation,value)
            self.state='end_wait';self.next_event=time+self.counter.latency
        elif self.state=='end_wait':
            generation,end_count=self.snapshot_pending
            if generation!=self.generation:raise ValueError('Stale end snapshot')
            self.snapshot_pending=None
            try:count=self.counter.delta(self.begin_count,end_count)
            except ValueError as error:
                self.cancel(time);self.state='failed';self.failure_reason=str(error)
                return
            estimate=count*self.prescale/self.window
            self.history.append(dict(code=self.code,count=count,frequency_hz=estimate,error_bound_hz=self.bound,
                                     start_snapshot=self.begin_count,end_snapshot=end_count,counter_bits=self.counter.bits,
                                     modular_wrap=end_count<self.begin_count,snapshot_ages=self.counter.ages))
            if estimate<self.target:self.low=self.code+1
            else:self.high=self.code-1
            if self.low<=self.high:self._trial(time)
            else:
                chosen=min(self.history,key=lambda r:abs(r['frequency_hz']-self.target))
                self.will_qualify=abs(chosen['frequency_hz']-self.target)+self.bound+self.residue<=self.margin
                self.clock.write_bank(time,chosen['code'] if self.will_qualify else self.saved,self.guard)
                self.state='commit';self.next_event=time+self.guard
        else:
            self.qualified=self.will_qualify;self.state='done' if self.qualified else 'failed';self.next_event=None
            if self.qualified:
                self.clock.retarget(time,self.target)
                self.clock.set_reference(True,time)


def advance_coarse(chip,time,advance_parent):
    if not math.isfinite(time) or time<chip.time:raise ValueError('Invalid coarse chip time')
    while chip.time<time:
        event=chip.coarse.next_event if chip.coarse is not None and chip.coarse.next_event is not None else math.inf
        command=chip.command_events[0][0] if chip.command_events else math.inf
        end=min(time,event,command)
        advance_parent(end)
        if chip.coarse is not None and chip.coarse.busy and chip.coarse.next_event==chip.time:
            chip.coarse.step(chip.time,chip.epoch,chip.reference)
            if chip.coarse.qualified:chip.rf_target_hz=chip.coarse.target
            chip.install_segment(chip.rf_pll.frequency_hz-chip.rf_carrier,check=False)
    advance_parent(time)
