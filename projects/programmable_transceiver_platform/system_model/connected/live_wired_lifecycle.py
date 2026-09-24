"""Event-driven wired channel, transition tracker and word framing in the chip model."""
import math,json
import numpy as np
from chip_model import P
from framing import Framer,MARKER
from recovered_clock import framed_words
from rf_phase_lifecycle import PhaseChip
from sustained_lifecycle import run

class LiveReceiver:
    def __init__(self,words,rate,start,phase=.3,ppm=100):
        training=np.random.default_rng(650).integers(0,2,1024).tolist()
        self.bits=training+list(MARKER)+[(int(w)>>k)&1 for w in words for k in range(10)]
        self.ui=1/rate;self.start=start;self.stop=start+len(self.bits)*self.ui
        self.time=start;self.state=0.;self.held=0.;self.swing=1.;self.energy=0.;self.pole=2*math.pi*rate
        self.launch_index=0;self.cross=math.inf;self.crossings=[];self.period=self.ui*(1+ppm*1e-6)
        self.anchor=start+phase*self.ui;self.cycle=0;self.index=0;self.forced_sample=None
        self.framer=Framer();self.enabled=True;self.done=False;self.omitted=0;self.samples=0;self.transitions=0
    def inherit_analog(self,previous):
        self.state=previous.state;self.held=previous.held;self.pole=previous.pole

    def sample_time(self):
        if self.forced_sample is not None:return self.forced_sample
        return self.anchor+(self.index-self.cycle+.5)*self.period
    def next_time(self):
        if self.done:return math.inf
        launch=self.start+self.launch_index*self.ui if self.launch_index<len(self.bits) else math.inf
        return min(launch,self.cross,self.sample_time() if self.enabled else math.inf,self.stop)
    def reset_tracking(self,time,enabled=False,phase=.3,ppm=100):
        if not all(math.isfinite(v) for v in (time,phase,ppm)) or time>self.next_time():
            raise ValueError('Reset must not skip pending channel events')
        if time>=self.time:self.evolve(time)
        elif time>=self.start:raise ValueError('Nonmonotonic receiver reset')
        self.enabled=enabled;self.framer.reset()
        self.period=self.ui*(1+ppm*1e-6);self.anchor=max(time,self.start)+phase*self.ui
        self.cycle=0;self.index=0;self.forced_sample=None;self.retime()

    def retime(self):
        while self.sample_time()<self.time:
            self.index+=1;self.omitted+=1
    def disturb(self,time,phase_ui=0.,period_ppm=0.):
        if not all(math.isfinite(v) for v in (time,phase_ui,period_ppm)) or time<self.time:
            raise ValueError('Invalid wired disturbance')
        self.evolve(time)
        self.anchor+=phase_ui*self.ui
        self.period=min(self.ui*1.005,max(self.ui*.995,self.period+period_ppm*1e-6*self.ui))
        # An external phase jump crossing the pending oscillator threshold emits
        # now; it must not erase that sample by relabeling it as a past event.
        if self.sample_time()<time:self.forced_sample=time
    def set_swing(self,time,swing):
        if not math.isfinite(swing) or not 0<=swing<=2 or time<self.time or time>self.next_time():
            raise ValueError('Invalid source amplitude event')
        self.evolve(time);self.swing=swing
        self.held=(2*self.bits[self.launch_index-1]-1)*swing if self.launch_index else 0.
        self.schedule_crossings(min(self.start+self.launch_index*self.ui,self.stop))

    def decision_value(self):return self.state
    def crossing_delays(self,duration):
        if self.state*self.held<0:
            dt=math.log((self.held-self.state)/self.held)/self.pole
            if 0<dt<duration:return [dt]
        return []
    def schedule_crossings(self,end):
        self.crossings=[self.time+dt for dt in self.crossing_delays(end-self.time)]
        self.cross=self.crossings.pop(0) if self.crossings else math.inf
    def consume_crossing(self):
        self.cross=self.crossings.pop(0) if self.crossings else math.inf

    def evolve(self,time):
        assert time>=self.time
        dt=time-self.time;delta=self.state-self.held;p=self.pole
        integral=self.held**2*dt+2*self.held*delta*(-math.expm1(-p*dt))/p+delta**2*(-math.expm1(-2*p*dt))/(2*p)
        self.energy+=max(0.,integral)
        self.state=self.held+delta*math.exp(-p*dt);self.time=time
    def step(self):
        t=self.next_time();self.evolve(t)
        if t==self.stop:self.done=True;return None
        launch=self.start+self.launch_index*self.ui if self.launch_index<len(self.bits) else math.inf
        if t==launch:
            self.held=(2*self.bits[self.launch_index]-1)*self.swing;self.launch_index+=1
            self.schedule_crossings(min(self.start+self.launch_index*self.ui,self.stop))
        if t==self.cross and not self.enabled:
            self.consume_crossing();self.transitions+=1
        if t==self.cross:
            cycles=max(1,round((t-self.anchor)/self.period));self.cycle+=cycles
            predicted=self.anchor+cycles*self.period;error=t-predicted
            self.period=min(self.ui*1.005,max(self.ui*.995,self.period+.001*error/cycles))
            self.anchor=predicted+.1*error;self.consume_crossing();self.transitions+=1;self.retime()
        if self.enabled and t==self.sample_time():
            self.samples+=1;self.index+=1;self.forced_sample=None;self.retime()
            return self.framer.feed(int(self.decision_value()>0))
        return None

class ForwardedReceiver(LiveReceiver):
    """Opaque ten-bit words at an externally established word boundary.

    No training sequence, marker, transition-tracking CDR or protocol decoder.
    Reference phase/rate are prescribed inputs; acquisition remains external.
    """
    def __init__(self,words,rate,start,phase=0.,ppm=0):
        from wired_blocks import CurrentSwitchChannel
        from types import SimpleNamespace
        if not words or any(type(w) is not int or not 0<=w<1024 for w in words):
            raise ValueError('Nonempty opaque ten-bit payload required')
        super().__init__(words,rate,start,phase,ppm)
        self.bits=[(w>>k)&1 for w in words for k in range(10)]
        self.stop=start+len(self.bits)*self.ui
        self.pad=CurrentSwitchChannel(rate)
        self.framer=SimpleNamespace(state='PAYLOAD',count=0,value=0)
        self.framer.reset=lambda:self.reset_word()
        self.minimum_margin=math.inf
    def reset_word(self):
        self.framer.state='PAYLOAD';self.framer.count=0;self.framer.value=0
    def inherit_analog(self,previous):
        import copy
        if not isinstance(previous,ForwardedReceiver):
            raise ValueError('Forwarded receiver requires compatible retained pad state')
        self.pad=copy.copy(previous.pad);self.pad.rate=1/self.ui
        self.state=self.pad.state;self.held=previous.held
    def schedule_crossings(self,end):
        self.cross=math.inf;self.crossings=[]
    def evolve(self,time):
        if time<self.time:raise ValueError('Nonmonotonic forwarded receiver')
        dt=time-self.time
        # Exact integral of the squared equal-pole response for idle detection.
        # The default equal-pole response is D+(A+B*t)*exp(-t/tau).
        from scipy.special import gammainc
        tau=self.pad.load_tau_s
        if self.pad.switch_tau_s!=tau:raise ValueError('Energy observer requires equal poles')
        a=self.pad.state-self.held;b=(self.pad.current_state-self.held)/tau
        def integral(n,k):return math.factorial(n)*gammainc(n+1,k*dt)/k**(n+1)
        self.energy+=max(0.,self.held**2*dt+2*self.held*(a*integral(0,1/tau)+b*integral(1,1/tau))+
            a*a*integral(0,2/tau)+2*a*b*integral(1,2/tau)+b*b*integral(2,2/tau))
        self.pad.advance_state(self.held,dt);self.state=self.pad.state;self.time=time
    def step(self):
        time=self.next_time();self.evolve(time)
        if time==self.stop:self.done=True;return None
        launch=self.start+self.launch_index*self.ui if self.launch_index<len(self.bits) else math.inf
        if time==launch:
            self.held=(2*self.bits[self.launch_index]-1)*self.swing;self.launch_index+=1
        if self.enabled and time==self.sample_time():
            self.samples+=1;self.index+=1;self.forced_sample=None;self.retime()
            self.minimum_margin=min(self.minimum_margin,abs(self.state)*self.pad.volts_per_unit)
            self.framer.value|=int(self.state>0)<<self.framer.count;self.framer.count+=1
            if self.framer.count==10:
                word=self.framer.value;self.reset_word();return word
        return None


class LiveWireChip(PhaseChip):
    def __init__(self,**kwargs):
        super().__init__(**kwargs);self.live_rx=None;self.live_history=[]
    def make_receiver(self,words,rate,start,phase,ppm):return LiveReceiver(words,rate,start,phase,ppm)
    def incoming_wire(self,words,start,phase=.3,ppm=100):
        if self.state!='active' or (self.live_rx is not None and not self.live_rx.done) or start<self.time:
            raise ValueError('Incoming link requires active idle receiver')
        previous=self.live_rx
        if previous is not None:previous.evolve(start)
        self.live_rx=self.make_receiver(words,self.channel.rate,start,phase,ppm)
        if previous is not None:
            self.live_rx.inherit_analog(previous)
        self.rx_metadata=(dict(clock='prescribed forwarded reference',framing='external ten-bit word boundary')
            if isinstance(self.live_rx,ForwardedReceiver) else
            dict(clock='causal transition tracker',framing='observed64-bit test marker'))
    def advance(self,time):
        while self.live_rx is not None and min(self.live_rx.next_time(),self.next_return)<=time:
            rx=self.live_rx;when=min(rx.next_time(),self.next_return);super().advance(when)
            # Return switching may retime the pending sample at this instant.
            word=rx.step() if rx.next_time()==when else None
            if rx.framer.state=='FAULT':
                self.quiesce(when,'wired framing acquisition fault');continue
            if word is not None:
                if len(self.wired_return)>=128:
                    self.quiesce(when,'wired RX return overflow');continue
                self.wired_return.append(word);self.rx_accepted+=1
        super().advance(time)
        if self.live_rx is not None and time>=self.live_rx.time:self.live_rx.evolve(time)
    def disturb_wire(self,time,phase_ui=0.,period_ppm=0.):
        if not all(math.isfinite(v) for v in (time,phase_ui,period_ppm)):raise ValueError('Nonfinite wired disturbance')
        self.advance(time)
        if self.live_rx is None or self.live_rx.done:raise ValueError('No running wired receiver')
        self.live_rx.disturb(time,phase_ui,period_ppm)
    def quiesce(self,time,reason):
        if self.live_rx is not None:
            self.live_history.append(dict(partial_bits=self.live_rx.framer.count,samples=self.live_rx.samples))
            self.live_rx.reset_tracking(time,False)
        super().quiesce(time,reason)


def controls():
    rows=[];words=[(i*37+19)%1024 for i in range(80)]
    for rate in (1.25e9,2.5e9):
        for phase in (-.3,.3):
            for ppm in (-100,100):
                rx=LiveReceiver(words,rate,0,phase,ppm);got=[]
                while not rx.done:
                    value=rx.step()
                    if value is not None:got.append(value)
                expected,_,_=framed_words(words,rate,phase,ppm)
                assert got==expected==words
                rows.append(dict(rate=rate,phase=phase,ppm=ppm,samples=rx.samples,transitions=rx.transitions))
    # Intervene after a prefix has already been decoded: the prefix cannot change.
    rx=LiveReceiver(words,1.25e9,0);got=[]
    while len(got)<20:
        value=rx.step()
        if value is not None:got.append(value)
    prefix=list(got);rx.disturb(rx.time,.03,50)
    while not rx.done:
        value=rx.step()
        if value is not None:got.append(value)
    assert got==words and got[:20]==prefix
    damaged=LiveReceiver(words,1.25e9,0);bad=[]
    while len(bad)<20:
        value=damaged.step()
        if value is not None:bad.append(value)
    damaged.disturb(damaged.time,1.1,0)
    while not damaged.done:
        value=damaged.step()
        if value is not None:bad.append(value)
    assert bad[:20]==words[:20] and bad!=words
    return rows


def reset_case(mode):
    c=LiveWireChip();c.configure(mode,0)
    while c.state!='active':c.advance(c.next_reference)
    c.incoming_wire([0x155,0x2aa],c.time)
    while c.live_rx.framer.state!='PAYLOAD' or c.live_rx.framer.count!=3:
        c.advance(c.live_rx.next_time())
    assert c.rx_accepted==0
    old=c.live_rx;c.set_reference(False,c.time)
    assert c.live_rx is old and not old.enabled and old.framer.count==0 and old.framer.state=='SEARCH'
    assert c.live_history[-1]['partial_bits']==3
    epoch=c.epoch;c.acknowledge_host_abort(epoch,c.time);c.acknowledge_drain(epoch,c.time)
    c.advance(c.time+1e-6)
    assert c.rx_accepted==0 and not c.wired_return and c.epoch==epoch+1
    return dict(mode=mode,discarded_partial_bits=3,stale_words=0)


def main():
    checks=controls();rows=[]
    for mode in (0,1):
        chips=[]
        def factory(**kwargs):
            c=LiveWireChip(**kwargs);chips.append(c);return c
        row=run(mode,100,chip_factory=factory,matched_reference=True,host_ppm=-100)
        rx=chips[0].live_rx;assert rx.done
        row['live_receiver']=dict(samples=rx.samples,transitions=rx.transitions,omitted=rx.omitted)
        rows.append(row)
    report=dict(status='passed',controls=checks,cases=rows,reset_cases=[reset_case(m) for m in (0,1)],complete_architecture=False,physical_qualification=False,
        limitations=['Ideal zero-crossing timestamps and near-nominal PI oscillator remain assumed; no electrical noise or calibrated jitter.',
        'External stimulus bits are scheduled launches only; feedback uses observed channel crossings and sampled analog sign.',
        'Test marker is not a protocol PCS or a lock detector; transition-free behavior and idle/detection remain open.',
        'Receiver reset preserves channel state and lets the external waveform continue; exhausted fixtures hold their final level until a new frame starts.',
        'Small intervention recovers;1.1UI step corrupts payload without a protocol-level error detector. Supply coupling and slip detection remain open.'])
    (P/'evidence/connected-live-wired-lifecycle.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed eight live/batch recovery controls, small/large interventions, partial-word reset and two sustained four-path cases')

if __name__=='__main__':main()
