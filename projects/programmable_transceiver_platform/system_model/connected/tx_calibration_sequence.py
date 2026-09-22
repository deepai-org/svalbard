"""Timed TX probe/ADC sequence with explicit ownership and atomic commit.

The parent supplies quiet/epoch checks, physical advancement, and probe writes.
This controller never enables the external RF output or starts user traffic.
"""
import math
from tx_iq_calibration import fit

class TxCalibrationSequence:
    def __init__(self,detector,write_probe,commit,release,relative_gain=False):
        self.relative_gain=relative_gain
        self.detector=detector;self.write_probe=write_probe;self.commit=commit;self.release=release
        self.state='idle';self.next_event=None;self.time=0.;self.generation=0
        self.candidate=None;self.valid=False
    @property
    def busy(self):return self.state in ('settle','convert','ready')
    def start(self,time,*,epoch,quiet,probes,dwell=2e-6):
        if self.busy or not quiet or self.detector.pending is not None:raise ValueError('Exclusive quiet detector ownership required')
        if not math.isfinite(time) or time<self.time or not math.isfinite(dwell) or dwell<=0 or len(probes)<6:
            raise ValueError('Invalid sequence')
        self.time=time;self.epoch=epoch;self.generation+=1;self.valid=False;self.candidate=None
        self.probes=list(probes);self.dwell=dwell;self.index=0;self.powers=[];self.state='settle'
        self.write_probe(time,self.probes[0]);self.next_event=time+dwell
        return self.generation
    def cancel(self,time,reason):
        if not math.isfinite(time) or time<self.time:raise ValueError('Invalid cancellation time')
        self.detector.abort();self.release(time);self.time=time;self.generation+=1
        self.next_event=None;self.state='cancelled';self.valid=False;self.candidate=None;self.reason=reason
    def service(self,time,*,epoch,quiet):
        if not math.isfinite(time) or time<self.time:raise ValueError('Nonmonotonic service')
        if self.state=='done' and epoch!=self.epoch:
            self.cancel(time,'committed calibration epoch expired');return
        if self.busy and (epoch!=self.epoch or not quiet):
            self.cancel(time,'epoch or ownership changed');return
        self.time=time
        if self.next_event is None or time<self.next_event:return
        if time!=self.next_event or self.detector.time!=time:
            raise ValueError('Parent must advance analog state at the exact event')
        if self.state=='settle':
            self.detector.request();self.state='convert';self.next_event=time+self.detector.latency
        elif self.state=='convert':
            sample=self.detector.read()
            if sample['overflow']:
                self.cancel(time,'detector saturated');return
            self.powers.append(sample['power']);self.index+=1
            if self.index<len(self.probes):
                self.write_probe(time,self.probes[self.index]);self.state='settle';self.next_event=time+self.dwell
            else:
                try:self.candidate=fit(self.probes,self.powers,relative_gain=self.relative_gain,
                    signed_observations=getattr(self.detector,'signed_observations',False))
                except ValueError:
                    self.cancel(time,'unobservable or out-of-range fit');return
                self.release(time);self.state='ready';self.next_event=None
    def accept(self,time,*,epoch,generation,quiet):
        if self.state!='ready' or generation!=self.generation or epoch!=self.epoch or not quiet or time<self.time or not math.isfinite(time):
            raise ValueError('Commit requires current completed calibration and quiet ownership')
        self.commit(self.candidate);self.time=time;self.state='done';self.valid=True
