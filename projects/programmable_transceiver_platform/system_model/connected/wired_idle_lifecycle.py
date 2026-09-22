"""Received-energy electrical-idle indication, distinct from transition density."""
import json,math
from chip_model import P
from live_wired_lifecycle import LiveReceiver,LiveWireChip
from sustained_lifecycle import run

class EnergyDetector:
    def __init__(self):self.idle=None;self.low=self.high=0
    def observe(self,rms):
        if not math.isfinite(rms) or rms<0:raise ValueError('Invalid detector input')
        self.low=self.low+1 if rms<.15 else 0
        self.high=self.high+1 if rms>.25 else 0
        if self.low>=2:self.idle=True
        if self.high>=2:self.idle=False
        return self.idle

class IdleWireChip(LiveWireChip):
    def __init__(self,idle_policy='rx_only',**kwargs):
        if idle_policy not in ('rx_only','session'):raise ValueError('Invalid idle policy')
        super().__init__(**kwargs);
        self.idle_policy=idle_policy;self.rx_idle_latched=False;self.rx_idle_ack=False;self.rx_generation=0
        self.rx_idle_events=[];self.next_detect=math.inf;self.detector=EnergyDetector()
        self.last_energy=0.;self.detect_history=[]
    def incoming_wire(self,*args,**kwargs):
        if self.rx_idle_latched and not self.rx_idle_ack:raise ValueError('Host must acknowledge wired RX idle before retraining')
        super().incoming_wire(*args,**kwargs)
        self.detect_period=8*self.live_rx.ui;self.next_detect=self.live_rx.start+self.detect_period
        self.detector=EnergyDetector();self.last_energy=0.
        self.rx_idle_latched=False;self.rx_idle_ack=False;self.rx_generation+=1
    def acknowledge_wire_idle(self,time):
        self.advance(time)
        if not self.rx_idle_latched or self.detector.idle is not False:
            raise ValueError('Acknowledgement requires latched idle and restored signal')
        self.rx_idle_ack=True

    def receive_idle(self,time):
        if self.idle_policy=='session':
            self.quiesce(time,'wired electrical idle');return
        if self.rx_idle_latched:return
        self.rx_idle_events.append(dict(time=time,generation=self.rx_generation,
            partial_bits=self.live_rx.framer.count,completed_words=self.rx_accepted))
        self.live_rx.reset_tracking(time,False)
        self.rx_idle_latched=True;self.rx_idle_ack=False
        # Completed words stay in order; only incomplete reception is discarded.
        # RF, wire TX and the shared host frame scheduler continue.

    def set_wire_swing(self,time,swing):
        if not math.isfinite(swing) or not 0<=swing<=2:raise ValueError('Invalid swing')
        self.advance(time)
        if self.live_rx is None:raise ValueError('No wired source')
        self.live_rx.set_swing(time,swing)
    def advance(self,time):
        while self.next_detect<=time:
            when=self.next_detect;super().advance(when)
            energy=self.live_rx.energy
            rms=math.sqrt(max(0.,energy-self.last_energy)/self.detect_period)
            old=self.detector.idle;idle=self.detector.observe(rms)
            self.last_energy=energy;self.next_detect=when+self.detect_period
            if idle!=old:self.detect_history.append(dict(time=when,idle=idle,rms=rms))
            if idle and self.state=='active':self.receive_idle(when)
        super().advance(time)


def controls():
    d=EnergyDetector()
    assert d.observe(0) is None and d.observe(0) is True
    for _ in range(10):assert d.observe(.2) is True
    assert d.observe(1) is True and d.observe(1) is False
    for _ in range(10):assert d.observe(.2) is False
    r=LiveReceiver([],1.25e9,0);r.held=1;r.evolve(3e-9)
    p=r.pole;t=3e-9
    expected=t-2*(1-math.exp(-p*t))/p+(1-math.exp(-2*p*t))/(2*p)
    assert abs(r.energy-expected)<1e-23


def local(mode,quiet):
    c=IdleWireChip(idle_policy='session');c.configure(mode,0)
    while c.state!='active':c.advance(c.next_reference)
    c.incoming_wire([1023]*64,c.time)
    rx=c.live_rx
    while rx.framer.state!='PAYLOAD' or rx.framer.count!=3:c.advance(rx.next_time())
    assert c.detector.idle is False
    if quiet:
        cut=c.time;c.set_wire_swing(cut,0);retained=rx.state
        assert retained!=0  # Driving idle does not erase channel charge.
        c.advance(cut+24*rx.ui)
        assert c.detector.idle is True and c.state=='draining'
        count=c.rx_accepted;c.advance(c.time+32*rx.ui);assert c.rx_accepted==count
        c.set_wire_swing(c.time,1);c.advance(c.time+24*rx.ui)
        assert c.detector.idle is False and c.state=='draining'  # Signal return is not rearm.
    else:
        c.advance(rx.stop+24*rx.ui)
        assert c.detector.idle is False and c.state=='active' and c.rx_accepted==64
    return dict(mode=mode,quiet=quiet,state=c.state,detector_history=c.detect_history)


def main():
    controls();rows=[local(m,q) for m in (0,1) for q in (False,True)]
    sustained=[run(m,100,chip_factory=IdleWireChip,matched_reference=True,host_ppm=-100) for m in (0,1)]
    report=dict(status='passed',cases=rows,sustained_cases=sustained,complete_architecture=False,physical_qualification=False,
        contract=dict(window_ui=8,consecutive_windows=2,idle_rms_threshold=.15,present_rms_threshold=.25,
            thresholds_units='normalized differential amplitude',idle_response='default RX-only stop with explicit host acknowledgement; legacy full-session policy also tested'),
        limitations=['Windowed RMS/hysteresis is an abstract detector, not a transistor energy detector or protocol electrical-idle limit.',
        'Legacy full-session tests select that policy explicitly; RX-only continuation is tested in independent-wired-idle evidence.',
        'No receiver-detect impedance test, common-mode model or qualified idle exit/link training.',
        'Source amplitude control is an external stimulus, not a programmable on-chip transmitter swing implementation.'])
    (P/'evidence/connected-wired-idle-lifecycle.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed four idle/constant-signal cases, detector/energy controls and two sustained live four-path cases')

if __name__=='__main__':main()
