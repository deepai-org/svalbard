"""Exact programmable two-pole TX/RX envelope cascade between DAC transitions."""
import math,cmath
from rf_tx_state import RfTxState

def convolution(rate, pole, dt):
    """Integral pole*exp(-pole*(dt-s))*exp(rate*s) ds, including resonance."""
    z=(pole+rate)*dt
    if abs(z)<1e-4:
        ratio=1+z/2+z*z/6+z**3/24+z**4/120
        return pole*dt*(cmath.exp(-pole*dt) if isinstance(pole,complex) else math.exp(-pole*dt))*ratio
    return pole*(cmath.exp(rate*dt)-(cmath.exp(-pole*dt) if isinstance(pole,complex) else math.exp(-pole*dt)))/(pole+rate)

class RfCascadeState(RfTxState):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.received=0j;self.rx_pole=self.pole;self.rx_bank=None
        self.rf_cubic=0.;self.rf_blockers=();self.rf_envelope_limit=1.
        self.tx_lo_hz=0.;self.rx_lo_hz=0.;self.tx_lo_phase=0.;self.rx_lo_phase=0.
        self.rx_route='loopback';self.external_amplitude=0j;self.external_frequency=0.
    def set_butterworth(self,order,cutoff_hz):
        if self.time!=0 or self.received!=0 or self.session.armed:
            raise ValueError('Filter topology selection requires initial unenergized state')
        if not isinstance(order,int) or not 1<=order<=7 or not math.isfinite(cutoff_hz) or cutoff_hz<=0:
            raise ValueError('Invalid Butterworth configuration')
        poles=[-2*math.pi*cutoff_hz*cmath.exp(1j*math.pi*(2*k+order+1)/(2*order)) for k in range(order)]
        product=math.prod(poles)
        weights=[product/(p*math.prod(q-p for j,q in enumerate(poles) if j!=i)) for i,p in enumerate(poles)]
        self.rx_bank=dict(poles=poles,weights=weights,states=[0j]*order,cutoff_hz=cutoff_hz)

    def set_bandwidths(self,tx_hz,rx_hz,time):
        if self.rx_bank is not None or self.reconstruction is not None:raise ValueError('Single-pole tuning unavailable for selected multipole topology')
        if not all(math.isfinite(v) and v>0 for v in (tx_hz,rx_hz)):
            raise ValueError('Invalid filter bandwidth')
        self.advance(time)
        self.pole=2*math.pi*tx_hz;self.rx_pole=2*math.pi*rx_hz

    def receive_terms(self):
        # RF envelope terms before ideal downconversion: C*exp(rate*s).
        terms=[]
        if self.rx_route=='loopback':
            rotation=cmath.exp(1j*(2*math.pi*self.tx_lo_hz*self.time+self.tx_lo_phase))
            terms=[(a*rotation,r+2j*math.pi*self.tx_lo_hz) for a,r in self.transmit_terms()]
            bound=(sum(abs(a) for a,r in terms) if self.reconstruction is not None else max(abs(self.held),abs(self.filtered)))
        elif self.rx_route=='external_tone':
            terms=[(self.external_amplitude*cmath.exp(2j*math.pi*self.external_frequency*self.time),
                    2j*math.pi*self.external_frequency)]
            bound=abs(self.external_amplitude)
        else:
            return []
        bound+=sum(abs(amplitude) for amplitude,frequency in self.rf_blockers)
        if (self.rf_cubic or self.rf_blockers) and bound>self.rf_envelope_limit:raise ValueError('RF envelope outside declared cubic-model range')
        terms.extend((amplitude*cmath.exp(2j*math.pi*frequency*self.time),2j*math.pi*frequency)
                     for amplitude,frequency in self.rf_blockers)
        products=list(terms)
        if self.rf_cubic:
            products.extend((self.rf_cubic*x*y*z.conjugate(),rx+ry+rz.conjugate())
                            for x,rx in terms for y,ry in terms for z,rz in terms)
        rotation=cmath.exp(-1j*(2*math.pi*self.rx_lo_hz*self.time+self.rx_lo_phase))
        return [(rotation*amplitude,rate-2j*math.pi*self.rx_lo_hz) for amplitude,rate in products]

    def nonlinear_receive(self,elapsed):
        return self.received*math.exp(-self.rx_pole*elapsed)+sum(
            amplitude*convolution(rate,self.rx_pole,elapsed) for amplitude,rate in self.receive_terms())

    def advance(self,time):
        assert time>=self.time
        if time==self.time:return
        elapsed=time-self.time
        if self.rx_bank is not None:
            terms=self.receive_terms();bank=self.rx_bank
            states=[old*cmath.exp(-pole*elapsed)+sum(amplitude*convolution(rate,pole,elapsed)
                    for amplitude,rate in terms) for old,pole in zip(bank['states'],bank['poles'])]
            bank['states']=states
            self.received=sum(w*x for w,x in zip(bank['weights'],states))
            super().advance(time)
            return
        if self.reconstruction is not None:
            self.received=self.nonlinear_receive(elapsed)
            super().advance(time)
            return
        a=self.pole;b=self.rx_pole
        da=math.exp(-a*elapsed);db=math.exp(-b*elapsed);difference=b-a
        if difference==0:transfer=b*elapsed*da
        elif abs(difference*elapsed)<1e-4:
            transfer=b*da*(-math.expm1(-difference*elapsed))/difference
        else:transfer=b*(da-db)/difference
        # Exact RX response to continuously evolving TX, including near-equal poles.
        if self.rf_cubic or self.rf_blockers:
            self.received=self.nonlinear_receive(elapsed)
        elif self.rx_route=='loopback':
            omega=2*math.pi*(self.tx_lo_hz-self.rx_lo_hz)
            phase=self.tx_lo_phase-self.rx_lo_phase
            if omega==0 and phase==0:
                self.received=self.held+(self.received-self.held)*db+(self.filtered-self.held)*transfer
            else:
                rotation=cmath.exp(1j*(omega*self.time+phase))
                self.received=self.received*db+rotation*(
                    self.held*convolution(1j*omega,b,elapsed)+
                    (self.filtered-self.held)*convolution(-a+1j*omega,b,elapsed))
        else:
            amplitude=self.external_amplitude if self.rx_route=='external_tone' else 0j
            omega=2*math.pi*(self.external_frequency-self.rx_lo_hz)
            amplitude*=cmath.exp(-1j*self.rx_lo_phase)
            self.received=self.received*db+amplitude*b/(b+1j*omega)*(cmath.exp(1j*omega*time)-db*cmath.exp(1j*omega*self.time))
        super().advance(time)


def controls():
    from session import Session
    s=Session();s.configure(0);s.host_ready=True;s.ready.update(rf=True,wire=True);s.arm()
    a=RfCascadeState(s);b=RfCascadeState(s)
    a.accept(1);b.accept(1);a.clock(0);b.clock(0)
    a.advance(30e-9)
    for i in range(1,101):b.advance(i*30e-9/100)
    expected=1-(1+a.pole*30e-9)*math.exp(-a.pole*30e-9)
    assert abs(a.received-expected)<1e-14 and abs(a.received-b.received)<1e-14
    x,y=a.filtered,a.received
    a.reset(30e-9)
    assert a.received==y and a.filtered==x
    a.advance(50e-9)
    expected=(y+x*a.pole*20e-9)*math.exp(-a.pole*20e-9)
    assert abs(a.received-expected)<1e-14
    return dict(subdivision_error=abs(b.received-y),reset_tail_error=abs(a.received-expected))
