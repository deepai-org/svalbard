"""Event-driven reversible trim search with externally enforced quiet ownership."""
import math
from calibration_verification import assess

class TimedCalibration:
    def __init__(self,write,compare):
        self.write=write;self.compare=compare;self.state='idle';self.next_event=None
        self.time=0.;self.generation=0;self.valid=False;self.result=None
    @property
    def busy(self):return self.state in ('search','settle','observe')
    def start(self,time,*,epoch,quiet,code,spacing,tolerance):
        if self.busy:raise ValueError('Calibration already owns target')
        if not quiet:raise ValueError('Quiet ownership required')
        if not all(math.isfinite(x) for x in (time,spacing,tolerance)) or time<self.time or spacing<=0 or tolerance<=0:
            raise ValueError('Invalid calibration timing or tolerance')
        if type(code) is not int or not 0<=code<=4095:raise ValueError('Invalid saved trim')
        self.time=time;self.epoch=epoch;self.saved_code=code;self.spacing=spacing;self.tolerance=tolerance
        self.generation+=1;self.valid=False;self.result=None;self.state='search'
        self.polarity=1;self.accepted=0;self.bit=11;self.codes=[];self.history=[]
        self._trial(time)
        return self.generation
    def _trial(self,time):
        self.trial=self.accepted|(1<<self.bit)
        self.write(time,self.trial);self.next_event=time+self.spacing
    def cancel(self,time,reason='cancelled'):
        if not math.isfinite(time) or time<self.time:raise ValueError('Nonmonotonic cancellation')
        if self.busy:self.write(time,self.saved_code)
        self.time=time;self.generation+=1;self.next_event=None;self.valid=False
        self.state='cancelled';self.result=dict(done=False,valid=False,accuracy='unverified',reason=reason)
    def advance(self,time,*,epoch,quiet):
        if not math.isfinite(time) or time<self.time:raise ValueError('Nonmonotonic calibration')
        if self.state=='done' and epoch!=self.epoch:
            self.cancel(time,'completed calibration invalidated by epoch change');return
        if self.busy and (epoch!=self.epoch or not quiet):
            self.cancel(time,'epoch changed or quiet ownership lost');return
        while self.next_event is not None and self.next_event<=time:
            at=self.next_event;self.time=at
            if self.state=='settle':
                self.state='observe';self.next_event=None;break
            high=self.compare(at,self.polarity)
            if self.polarity==-1:high=not high
            self.history.append((at,self.trial,self.polarity,high))
            if not high:self.accepted=self.trial
            self.bit-=1
            if self.bit>=0:self._trial(at);continue
            self.codes.append(self.accepted)
            if self.polarity==1:
                self.polarity=-1;self.accepted=0;self.bit=11;self._trial(at);continue
            limited=any(c in (0,4095) for c in self.codes)
            self.code=self.saved_code if limited else (sum(self.codes)+1)//2
            self.write(at,self.code);self.range_limited=limited
            self.state='settle';self.next_event=at+self.spacing
        self.time=time
    def observe(self,time,*,generation,epoch,quiet,value,error_bound):
        if generation!=self.generation or epoch!=self.epoch:raise ValueError('Stale observation')
        if not math.isfinite(time) or self.state!='observe' or time<self.time:raise ValueError('Observation not ready')
        if not quiet:self.cancel(time,'quiet ownership lost');return
        self.result=assess(done=True,range_limited=self.range_limited,observation_v=value,
             error_bound_v=error_bound,tolerance_v=self.tolerance,quiet=True,epoch=epoch,observation_epoch=epoch)
        self.time=time;self.state='done';self.valid=self.result['valid']
