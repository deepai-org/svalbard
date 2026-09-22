"""Bounded deterministic phase modulation; explicit assumption, not PLL noise."""
import math

class SampleClock:
    def __init__(self,start,period,jitter_s=0):
        if not all(math.isfinite(x) for x in (start,period,jitter_s)) or period<=0 or abs(jitter_s)>=period/4:
            raise ValueError('Finite clock and jitter below quarter period required')
        self.start=start;self.period=period;self.jitter=jitter_s;self.index=0
    def edge(self):
        # Four-edge modulation, exact integer phases; no accumulated edge error.
        return self.start+self.index*self.period+self.jitter*(0,1,0,-1)[self.index%4]
    def step(self):
        self.index+=1
        return self.edge()


def controls():
    c=SampleClock(1e-6,25e-9,1e-9)
    times=[c.edge()]+[c.step() for _ in range(1000)]
    assert all(b>a for a,b in zip(times,times[1:]))
    assert max(abs(t-(1e-6+i*25e-9)) for i,t in enumerate(times))<=1.000001e-9
    assert times[1000]==1e-6+1000*25e-9
    try:SampleClock(0,1, .25)
    except ValueError:pass
    else:raise AssertionError('Unsafe jitter accepted')
