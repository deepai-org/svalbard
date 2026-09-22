"""Calibration using a settling actuator and comparator-only feedback."""
import math

class OffsetTrimPlant:
    def __init__(self,offset_v,tau_s=20e-9,span_v=.5,comparator_offset_v=0.):
        if not all(math.isfinite(x) for x in (offset_v,tau_s,span_v,comparator_offset_v)) or tau_s<=0 or span_v<=0:
            raise ValueError('Invalid trim plant')
        self.offset=offset_v;self.tau=tau_s;self.span=span_v;self.comparator_offset=comparator_offset_v
        self.code=2048;self.time=0.;self.correction=self.demand(self.code)
    def demand(self,code):return self.span*(code/4095-.5)
    def advance(self,time):
        if not math.isfinite(time) or time<self.time:raise ValueError('Nonmonotonic trim time')
        target=self.demand(self.code)
        self.correction=target+(self.correction-target)*math.exp(-(time-self.time)/self.tau)
        self.time=time
    def write(self,time,code):
        if not isinstance(code,int) or not 0<=code<=4095:raise ValueError('Trim code range')
        self.advance(time);self.code=code
    def above(self,time,polarity=1):
        if polarity not in (-1,1):raise ValueError('Invalid comparator polarity')
        self.advance(time);return polarity*(self.offset+self.correction)+self.comparator_offset>0
    def apply(self,time,signal):
        self.advance(time);return signal+self.offset+self.correction

class Calibration:
    def __init__(self,write,above,period_s=25e-9):
        if not math.isfinite(period_s) or period_s<=0:raise ValueError('Invalid calibration clock')
        self.write=write;self.above=above;self.period=period_s
    def run(self,start):
        # Same twelve MSB-first trials and nine-clock comparison spacing as the
        # existing RTL helper (eight settle decrements, then compare).
        accepted=0;history=[];time=start
        for bit in range(11,-1,-1):
            trial=accepted|(1<<bit);self.write(time,trial)
            time+=9*self.period;high=self.above(time)
            history.append((time,trial,high))
            if not high:accepted=trial
        self.write(time,accepted)
        return dict(code=accepted,done_at=time,comparisons=history,range_limited=accepted in (0,4095))


def calibrate_reversed(plant,start):
    old_code=plant.code
    forward=Calibration(plant.write,lambda t:plant.above(t,1)).run(start)
    reverse=Calibration(plant.write,lambda t:not plant.above(t,-1)).run(forward['done_at'])
    limited=forward['range_limited'] or reverse['range_limited']
    code=old_code if limited else (forward['code']+reverse['code']+1)//2
    plant.write(reverse['done_at'],code)
    return dict(code=code,done_at=reverse['done_at'],range_limited=limited,
                forward=forward,reverse=reverse)
