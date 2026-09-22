"""Bounded two-input gm/C tile; held inputs, leaky integration and hysteresis.

Abstract local tile, not a universal crossbar. Rails, gm and leakage are assumed.
Configuration preserves capacitor state. Discharge is an explicit analog action.
"""
import math

class AnalogTile:
    def __init__(self,capacitance=1e-12,gm=1e-6,leakage=1e-7,limit=.8,hysteresis=.01):
        values=(capacitance,gm,leakage,limit,hysteresis)
        if not all(math.isfinite(v) for v in values) or capacitance<=0 or gm<0 or leakage<0 or limit<=0 or not 0<=hysteresis<limit:
            raise ValueError('Invalid tile parameters')
        self.c=capacitance;self.gm=gm;self.leakage=leakage
        self.limit=limit;self.hysteresis=hysteresis
        self.time=0.;self.voltage=0.;self.inputs=(0.,0.);self.weights=(1.,0.)
        self.comparator=False;self.enabled=True
    def advance(self,time):
        if not math.isfinite(time) or time<self.time:raise ValueError('Nonmonotonic tile time')
        dt=time-self.time
        current=self.gm*sum(w*x for w,x in zip(self.weights,self.inputs)) if self.enabled else 0.
        if self.leakage:
            decay=math.exp(-self.leakage*dt/self.c)
            v=self.voltage*decay+current/self.leakage*(-math.expm1(-self.leakage*dt/self.c))
        else:v=self.voltage+current*dt/self.c
        self.voltage=max(-self.limit,min(self.limit,v));self.time=time
        if self.voltage>=self.hysteresis:self.comparator=True
        elif self.voltage<=-self.hysteresis:self.comparator=False
        return self.voltage
    def drive(self,time,first,second):
        if not all(math.isfinite(x) for x in (first,second)):raise ValueError('Nonfinite tile input')
        self.advance(time);self.inputs=(first,second)
    def configure(self,time,weights,enabled=True):
        weights=tuple(weights)
        if len(weights)!=2 or any(w not in (-1.,-.5,0.,.5,1.) for w in weights) or not isinstance(enabled,bool):
            raise ValueError('Unsupported local tile setting')
        self.advance(time);self.weights=weights;self.enabled=enabled
    def discharge(self,time):
        self.advance(time);self.voltage=0.;self.comparator=False
