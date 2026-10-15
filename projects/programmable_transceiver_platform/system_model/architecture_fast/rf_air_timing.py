"""Generic sample-domain launch service. No RF waveform or protocol parser.

Counter timestamps refer to converter edges, not antenna time. FPGA calibration
translates antenna deadlines into sample indices. A late command never launches
late; retuning invalidates the epoch and all pending work.
"""
import math
MODULUS=1<<48
HALF=MODULUS//2


def antenna_target(*, antenna_time_s, sample_origin_s, sample_hz, tx_delay_s):
    if not all(math.isfinite(v) for v in (antenna_time_s,sample_origin_s,sample_hz,tx_delay_s)) or sample_hz<=0 or tx_delay_s<0:
        raise ValueError('Timing calibration')
    raw=(antenna_time_s-sample_origin_s-tx_delay_s)*sample_hz
    if raw<0:raise ValueError('Before sample epoch')
    index=math.floor(raw+.5)
    actual=sample_origin_s+index/sample_hz+tx_delay_s
    return dict(sample_index=index%MODULUS,antenna_time_s=actual,error_s=actual-antenna_time_s)


class SampleLaunch:
    def __init__(self,epoch=0,counter=0,prefill_pairs=16):
        if type(epoch) is not int or not 0<=epoch<65536 or type(counter) is not int or not 0<=counter<MODULUS:
            raise ValueError('Epoch/counter')
        if type(prefill_pairs) is not int or not 1<=prefill_pairs<=42:
            raise ValueError('Prefill exceeds1024bit ingress allocation')
        self.epoch=epoch;self.counter=counter;self.prefill_pairs=prefill_pairs
        self.target=None;self.output=False;self.status='idle'

    def arm(self,epoch,target):
        if type(target) is not int or not 0<=target<MODULUS or epoch!=self.epoch or self.target is not None or self.output or self.status in ('fault','underflow'):
            raise ValueError('Stale, malformed or overlapping launch')
        distance=(target-self.counter)%MODULUS
        if not 0<distance<HALF:raise ValueError('Late or ambiguous launch')
        self.target=target;self.status='armed'

    def edge(self,*,queued_pairs,source_ready=True,board_ready=True,calibration_valid=True):
        if type(queued_pairs) is not int or not 0<=queued_pairs<=42:raise ValueError('Finite ingress')
        self.counter=(self.counter+1)%MODULUS
        if not all((source_ready,board_ready,calibration_valid)):
            self.output=False;self.target=None;self.status='fault';return False
        if self.target==self.counter:
            self.target=None
            if queued_pairs<self.prefill_pairs:
                self.output=False;self.status='underflow';return False
            self.output=True;self.status='launched';return True
        if self.output and queued_pairs==0:
            self.output=False;self.status='underflow'
        return False

    def stop(self):
        self.output=False;self.target=None;self.status='idle'

    def retune(self,epoch):
        if type(epoch) is not int or not 0<=epoch<65536 or epoch==self.epoch:
            raise ValueError('New epoch required')
        self.stop();self.epoch=epoch;self.counter=0
