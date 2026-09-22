"""Finite-bandwidth square-law detector driven by continuous envelope terms.

Inputs are (complex amplitude, complex exponential rate) at the current time.
Power convolution is exact for that representation. ADC captures detector state
at request time, then publishes after latency with an epoch tag. All physical
parameters remain assumptions; loading and RF harmonics are absent.
"""
import math,cmath

class PowerDetector:
    def __init__(self,tau=200e-9,bits=10,fullscale=.1,latency=100e-9):
        if not all(math.isfinite(x) and x>0 for x in (tau,fullscale,latency)) or bits not in (8,10,12):
            raise ValueError('Invalid detector parameters')
        self.pole=1/tau;self.bits=bits;self.fullscale=fullscale;self.latency=latency
        self.time=0.;self.value=0.;self.pending=None;self.epoch=0
    def advance(self,time,terms):
        if not math.isfinite(time) or time<self.time:raise ValueError('Nonmonotonic time')
        if not terms or any(not math.isfinite(v) for a,p in terms for v in (a.real,a.imag,p.real,p.imag)):
            raise ValueError('Invalid exponential terms')
        dt=time-self.time;decay=math.exp(-self.pole*dt);total=0j
        for a,p in terms:
            for b,q in terms:
                rate=p+q.conjugate();den=rate+self.pole
                integral=(dt*decay if abs(den*dt)<1e-10 else
                    (cmath.exp(rate*dt)-decay)/den)
                total+=a*b.conjugate()*self.pole*integral
        result=self.value*decay+total
        if abs(result.imag)>1e-9 or result.real < -1e-10:raise ValueError('Invalid detector power')
        self.value=max(0.,result.real);self.time=time
    def request(self):
        if self.pending is not None:raise ValueError('ADC busy')
        code=round(min(self.fullscale,self.value)/self.fullscale*((1<<self.bits)-1))
        self.pending=(self.time+self.latency,self.epoch,code,self.value>self.fullscale)
    def read(self):
        if self.pending is None or self.time<self.pending[0]:raise ValueError('ADC result not ready')
        _,epoch,code,overflow=self.pending;self.pending=None
        if epoch!=self.epoch:raise ValueError('Stale result')
        return dict(epoch=epoch,code=code,power=code*self.fullscale/((1<<self.bits)-1),overflow=overflow)
    def abort(self):
        self.epoch+=1;self.pending=None  # Detector capacitor retains its charge.

def modulator_terms(terms,gain_db=0.,phase_deg=0.,leak=0j):
    g=10**(gain_db/40);rot=cmath.exp(1j*math.radians(phase_deg))
    a=(g+rot/g)/2;b=(g-rot/g)/2
    return [(a*v,p) for v,p in terms]+[(b*v.conjugate(),p.conjugate()) for v,p in terms]+[(complex(leak),0j)]
