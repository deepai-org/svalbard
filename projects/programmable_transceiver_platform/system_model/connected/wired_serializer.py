"""Bit launch/sample events with persistent channel state and partial-word abort."""
import math

class Serializer:
    def __init__(self,channel,time):
        self.channel=channel;self.time=time;self.drive=0.;self.deadline=math.inf
        self.active=False;self.started=self.completed=self.aborted=0
        self.pole=-math.log(channel.decay)*channel.rate
    def advance(self,time):
        assert time>=self.time
        self.channel.state=self.drive+(self.channel.state-self.drive)*math.exp(-self.pole*(time-self.time));self.time=time
    def start(self,word,time,ui):
        if self.active:raise ValueError('Serializer already has a partial word')
        self.advance(time);self.word=word;self.origin=time;self.ui=ui;self.bit=0;self.result=0
        self.stage='launch';self.deadline=time;self.active=True;self.started+=1
    def step(self):
        self.advance(self.deadline);c=self.channel
        if self.stage=='launch':
            self.symbol=1 if self.word&(1<<self.bit) else -1
            self.drive=c.swing*(self.symbol-c.postcursor*c.previous_symbol)/(1+c.postcursor)
            c.previous_symbol=self.symbol;c.peak_drive=max(c.peak_drive,abs(self.drive))
            self.stage='sample';self.deadline=self.origin+(self.bit+.5)*self.ui
        else:
            margin=c.state*self.symbol;c.minimum_margin=min(c.minimum_margin,margin)
            c.bits+=1;c.errors+=int(margin<=0);self.result|=int(c.state>0)<<self.bit
            self.bit+=1
            if self.bit==10:
                self.active=False;self.deadline=math.inf;self.completed+=1;return self.result
            self.stage='launch';self.deadline=self.origin+self.bit*self.ui
        return None
    def abort(self,time):
        self.advance(time)
        if self.active:self.aborted+=1
        self.active=False;self.deadline=math.inf;self.drive=0.;self.channel.previous_symbol=0.
    def accounting(self):
        assert self.started==self.completed+self.aborted+int(self.active)
        return dict(started=self.started,completed=self.completed,aborted=self.aborted,pending=int(self.active))
