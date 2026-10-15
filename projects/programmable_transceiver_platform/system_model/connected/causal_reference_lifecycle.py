"""Standalone reference recharge/charge controls; explicit aggregate event assumptions."""
import math

class Reference:
    def __init__(self,resistance=1000,capacitance=100e-12,load_capacitance=1e-12):
        if not all(math.isfinite(v) for v in (resistance,capacitance,load_capacitance)) or resistance<=0 or capacitance<=0 or not 0<=load_capacitance<capacitance:
            raise ValueError('Invalid reference parameters')
        self.r=resistance;self.c=capacitance;self.load=load_capacitance
        self.voltage=1.;self.time=0.;self.minimum=1.;self.charge=0.;self.samples=0;self.dac_updates=0;self.dac_charge=0.;self.last_dac=0j
    def advance(self,time):
        if time<self.time:raise ValueError('Nonmonotonic reference time')
        self.voltage=1+(self.voltage-1)*math.exp(-(time-self.time)/(self.r*self.c))
        self.time=time
    def dac_update(self,time,value,load):
        if not math.isfinite(load) or not 0<=load<self.c:raise ValueError('Invalid DAC reference load')
        self.advance(time);span=self.voltage
        if span<=.1:raise ValueError('Reference outside modeled operating range')
        activity=min(1.,(abs(value.real-self.last_dac.real)+abs(value.imag-self.last_dac.imag))/4)
        q=load*span*(.25+.75*activity)
        self.voltage-=q/self.c;self.charge+=q;self.dac_charge+=q;self.dac_updates+=1
        self.minimum=min(self.minimum,self.voltage);self.last_dac=value
        return value*span

    def sample(self,time,value):
        if not math.isfinite(value.real) or not math.isfinite(value.imag):raise ValueError('Nonfinite reference input')
        self.advance(time)
        span=self.voltage
        if span<=.1:raise ValueError('Reference outside modeled operating range')
        normalized=value/span
        # One aggregate conversion impulse after sampling. Not SAR bit timing.
        activity=min(1.,abs(value.real)+abs(value.imag))
        q=self.load*span*(.25+.75*activity)
        self.voltage-=q/self.c;self.charge+=q;self.samples+=1
        self.minimum=min(self.minimum,self.voltage)
        return normalized

class CurrentLimitedReference(Reference):
    """Exact fixed-target RC recharge with the existing bidirectional limiter law.

    Tracks source charge, not complete rail power; target/bias rail coupling and
    transistor buffer dynamics remain separate physical integration work.
    """
    def __init__(self,*,source_limit_a=150e-6,sink_limit_a=150e-6,**kwargs):
        if not all(math.isfinite(v) and v>0 for v in (source_limit_a,sink_limit_a)):
            raise ValueError('Positive finite reference current limits required')
        super().__init__(**kwargs)
        self.source_current_limit=source_limit_a;self.sink_current_limit=sink_limit_a
        self.recharge_c=0.;self.absorbed_c=0.;self.limited_s=0.;self.peak_current_a=0.
    def advance(self,time):
        if not math.isfinite(time) or time<self.time:raise ValueError('Invalid reference time')
        dt=time-self.time;before=self.voltage;gap=1.-before
        if dt and gap:
            direction=1. if gap>0 else -1.
            limit=self.source_current_limit if gap>0 else self.sink_current_limit
            self.peak_current_a=max(self.peak_current_a,min(abs(gap)/self.r,limit))
            clipped=min(dt,max(0.,(abs(gap)-limit*self.r)*self.c/limit))
            self.voltage+=direction*limit*clipped/self.c
            self.voltage=1.+(self.voltage-1.)*math.exp(-(dt-clipped)/(self.r*self.c))
            self.limited_s+=clipped
            charge=self.c*(self.voltage-before)
            self.recharge_c+=max(0.,charge);self.absorbed_c+=max(0.,-charge)
        self.time=time;self.minimum=min(self.minimum,self.voltage)


def controls():
    r=Reference();z=.4+.2j
    assert r.sample(0,z)==z
    q=1e-12*(.25+.75*.6)
    assert abs(r.voltage-(1-q/100e-12))<1e-15
    expected=1-q/100e-12*math.exp(-25e-9/(1000*100e-12))
    assert abs(r.sample(25e-9,z)-z/expected)<1e-14
    a=Reference();b=Reference();a.sample(0,z);b.sample(0,z)
    a.advance(100e-9)
    for i in range(1,101):b.advance(i*1e-9)
    assert abs(a.voltage-b.voltage)<1e-14
    # Zero loading remains exactly ideal, irrespective of sample history.
    c=Reference(load_capacitance=0)
    assert all(c.sample(i*25e-9,z)==z for i in range(100))


if __name__=="__main__":
    controls()
    print("Standalone numerical controls passed; no chip lifecycle exercised.")
