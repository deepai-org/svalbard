"""Counted empty-frame activation for the experimental streaming host link."""
import math
from chip_model import Receiver

class HostActivation:
    def __init__(self):self.state='idle';self.reason=None;self.last=None;self.words=0
    def start(self,mode,time,epoch,sequence=0):
        if self.state=='training':raise ValueError('Host activation already busy')
        self.receiver=Receiver(mode);self.receiver.sequence=sequence
        self.epoch=epoch;self.period=1/(250e6 if mode==0 else 312.5e6)
        self.state='training';self.reason=None;self.last=None;self.start_time=time;self.words=0
        self.previous=0;self.frame_transitions=0;self.transitions=0
    @property
    def deadline(self):
        return (self.start_time+20e-6 if self.last is None else self.last+1.01*self.period) if self.state=='training' else math.inf
    def invalidate(self,reason):self.state='failed';self.reason=reason
    def feed(self,word,time,epoch):
        if self.state!='training':raise ValueError('Activation is not training')
        if epoch!=self.epoch:raise ValueError('Stale activation epoch')
        if self.last is None:
            if not self.start_time<=time<=self.deadline:raise ValueError('Training first edge timeout')
        elif not .99*self.period<=time-self.last<=1.01*self.period:raise ValueError('Training clock gap or wrong rate')
        event=self.receiver.feed(word)
        if event is not None and event!=('command',(0,0)):raise ValueError('Training must contain no payload or commands')
        if self.receiver.pos==5 and any(self.receiver.left.values()):raise ValueError('Training payload allocation forbidden')
        changes=(word^self.previous).bit_count()+1
        self.previous=word;self.transitions+=changes;self.frame_transitions+=changes
        self.last=time;self.words+=1
        if self.receiver.pos==0:
            if not 4*64<=self.frame_transitions<=8*64:raise ValueError('Training frame switching activity outside assumed band')
            self.frame_transitions=0
        if self.words==4096:self.state='ready'
    def ready(self,time,epoch):
        # Bound new stream starts after an idle link; this is not a phase oracle.
        return self.state=='ready' and epoch==self.epoch and 0<=time-self.last<=64*self.period
