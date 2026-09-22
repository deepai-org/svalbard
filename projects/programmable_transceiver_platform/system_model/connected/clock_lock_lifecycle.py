"""Linear near-lock clock dynamics and sampled lock qualification in DuplexChip."""
import json,math
from chip_model import P
from wired_return_lifecycle import DuplexChip

class LinearClock:
    def __init__(self,phase=.25,frequency_hz=40000,bandwidth_hz=1e6):
        self.phase=phase;self.frequency=frequency_hz;self.omega=2*math.pi*bandwidth_hz
        self.good=0;self.locked=False
    def advance(self,dt):
        if dt<0:raise ValueError('Negative clock interval')
        a=self.frequency+self.omega*self.phase;decay=math.exp(-self.omega*dt)
        self.phase=(self.phase+a*dt)*decay
        self.frequency=(self.frequency-self.omega*a*dt)*decay
    def observe(self):
        valid=abs(self.phase)<=.01 and abs(self.frequency)<=4000
        self.good=self.good+1 if valid else 0
        self.locked=self.good>=8
        return self.locked

class LockedChip(DuplexChip):
    def __init__(self,phase=.25,frequency_hz=40000,**kwargs):
        super().__init__(**kwargs)
        self.initial_phase=phase;self.initial_frequency=frequency_hz
        self.next_reference=math.inf;self.reference_period=25e-9
        self.lock_history=[]
    def configure(self,mode,time):
        super().configure(mode,time)
        self.clock=LinearClock(self.initial_phase,self.initial_frequency)
        self.clock_time=time;self.reference_index=1;self.reference_origin=time
        self.next_reference=time+self.reference_period
        self.lock_at=math.inf
    def set_reference(self,present,time):
        super().set_reference(present,time)
        if self.state=='acquiring':self.lock_at=math.inf

    def advance(self,time):
        while self.next_reference<=time:
            tick=self.next_reference
            super().advance(tick)
            if self.reference and self.state in ('acquiring','active'):
                self.clock.advance(tick-self.clock_time)
                qualified=self.clock.observe()
                self.lock_history.append((tick,self.clock.phase,self.clock.frequency,qualified))
                if self.state=='acquiring' and qualified:
                    self.lock_at=tick;super().advance(tick)
                elif self.state=='active' and not qualified:
                    self.quiesce(tick,'clock lock loss')
            self.clock_time=tick
            self.reference_index+=1
            self.next_reference=self.reference_origin+self.reference_index*self.reference_period
        super().advance(time)


def controls():
    a=LinearClock();b=LinearClock()
    a.advance(1e-6)
    for _ in range(100):b.advance(1e-8)
    assert abs(a.phase-b.phase)<1e-14 and abs(a.frequency-b.frequency)<1e-7
    c=LinearClock(-.25,-40000);c.advance(1e-6)
    assert abs(a.phase+c.phase)<1e-14 and abs(a.frequency+c.frequency)<1e-7
    d=LinearClock(0,0)
    for _ in range(7):assert not d.observe()
    assert d.observe()
    d.phase=.02;assert not d.observe()


def run(mode,phase,frequency):
    c=LockedChip(phase=phase,frequency_hz=frequency,watchdog_s=20e-6)
    c.configure(mode,0)
    c.advance(200e-9);assert c.state=='acquiring'
    c.advance(3e-6);assert c.state=='active'
    acquired=next(t for t,p,f,locked in c.lock_history if locked)
    c.capture(3,c.time+10e-9);c.incoming_wire([17,801,3],c.time)
    c.advance(c.time+2e-6);c.host_decoder.finish()
    assert c.host_wire==[17,801,3] and c.host_samples==[0,0,0]
    # Disturb after advancing dynamics to the intervention instant.
    c.clock.advance(c.time-c.clock_time);c.clock_time=c.time
    c.clock.phase+=.2
    c.advance(c.next_reference)
    assert c.state=='draining' and c.events[-1][1]=='clock lock loss'
    assert not c.session.enabled('rf') and not c.session.enabled('wire')
    return dict(mode=mode,initial_phase_cycles=phase,initial_frequency_hz=frequency,
                acquired_s=acquired,loss_detected_s=c.time)


def main():
    controls();rows=[run(m,p,f) for m in (0,1) for p in (-.25,.25) for f in (-40000,40000)]
    report=dict(status='passed',cases=rows,complete_architecture=False,physical_qualification=False,
        assumptions=['Critically damped linear phase-error dynamics with1MHz natural frequency; near-lock approximation, not nonlinear PLL capture.',
        '40MHz ideal reference and eight consecutive samples within.01cycle/4kHz qualify lock.',
        'Phase/frequency state gates lifecycle but does not yet modulate payload clock edges.',
        'No phase wrapping, tuning saturation, divider quantization, reference noise or physical loop calibration.'])
    (P/'evidence/connected-clock-lock-lifecycle.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed eight dynamic lock/receive/loss cases and analytic clock controls')

if __name__=='__main__':main()
