"""Causal one-zero/one-pole receiver equalization feeding both crossing and data detectors."""
import json,math
from chip_model import P
from live_wired_lifecycle import LiveReceiver,ForwardedReceiver
from wired_idle_lifecycle import IdleWireChip
from sustained_lifecycle import run

class EqualizedReceiver(LiveReceiver):
    def __init__(self,*args,boost=0.,channel_ratio=1.,**kwargs):
        super().__init__(*args,**kwargs)
        if boost not in (0.,.5,1.,2.) or not math.isfinite(channel_ratio) or channel_ratio<=0:
            raise ValueError('Invalid equalizer/channel setting')
        self.boost=boost;self.pole*=channel_ratio;self.eq_pole=self.pole/4;self.slow=0.
    def inherit_analog(self,previous):
        if not isinstance(previous,EqualizedReceiver):raise ValueError('Equalizer state mapping requires compatible topology')
        super().inherit_analog(previous)
        self.slow=previous.slow;self.eq_pole=previous.eq_pole
    def evolve(self,time):
        dt=time-self.time;a=self.pole;b=self.eq_pole;x=self.state;h=self.held
        da=math.exp(-a*dt);db=math.exp(-b*dt)
        self.slow=h+(self.slow-h)*db+(x-h)*b*(da-db)/(b-a)
        super().evolve(time)
    def decision_value(self):return (1+self.boost)*self.state-self.boost*self.slow
    def crossing_delays(self,duration):
        if self.boost==0:return super().crossing_delays(duration)
        a=self.pole;b=self.eq_pole;h=self.held;d=self.state-h
        A=(1+self.boost)*d-self.boost*d*b/(b-a)
        B=-self.boost*(self.slow-h-d*b/(b-a))
        def value(t):return h+A*math.exp(-a*t)+B*math.exp(-b*t)
        points=[0.,duration]
        if A*a and -B*b/(A*a)>0:
            extremum=math.log(-B*b/(A*a))/(b-a)
            if 0<extremum<duration:points.insert(1,extremum)
        roots=[]
        for left,right in zip(points,points[1:]):
            if value(left)*value(right)>=0:continue
            lo,hi=left,right
            for _ in range(48):
                mid=(lo+hi)/2
                if value(lo)*value(mid)<=0:hi=mid
                else:lo=mid
            root=(lo+hi)/2
            if 0<root<duration:roots.append(root)
        return roots

class EqualizerControls:
    def __init__(self,rx_boost=0.,rx_channel_ratio=1.,**kwargs):
        if rx_boost not in (0.,.5,1.,2.) or not math.isfinite(rx_channel_ratio) or rx_channel_ratio<=0:
            raise ValueError('Invalid equalizer configuration')
        super().__init__(**kwargs);self.rx_boost=rx_boost;self.rx_channel_ratio=rx_channel_ratio
    def configure_wire_rx(self,boost):
        if self.session.armed:raise ValueError('RX equalizer configuration requires disarmed state')
        if boost not in (0.,.5,1.,2.):raise ValueError('Unsupported RX boost')
        self.rx_boost=boost
        if self.live_rx is not None:
            self.live_rx.boost=boost
            if not self.live_rx.done:self.live_rx.schedule_crossings(min(self.live_rx.start+self.live_rx.launch_index*self.live_rx.ui,self.live_rx.stop))
    def make_receiver(self,words,rate,start,phase,ppm):
        if getattr(self,'wire_interface',{}).get('clock_source')=='forwarded_word':
            return ForwardedReceiver(words,rate,start,phase,ppm)
        return EqualizedReceiver(words,rate,start,phase,ppm,boost=self.rx_boost,channel_ratio=self.rx_channel_ratio)

class EqualizedChip(EqualizerControls,IdleWireChip):
    pass


def controls():
    words=[(i*37+19)%1024 for i in range(100)];rows=[]
    for ratio in (.03,.1,.15,.35,1.):
        for boost in (0.,.5,1.,2.):
            c=EqualizedReceiver(words,1.25e9,0,boost=boost,channel_ratio=ratio);got=[]
            while not c.done:
                w=c.step()
                if w is not None:got.append(w)
            rows.append(dict(channel_ratio=ratio,boost=boost,exact_words=got==words,recovered_words=len(got)))
    a=EqualizedReceiver([],1e9,0,boost=1);b=EqualizedReceiver([],1e9,0,boost=1)
    a.held=b.held=1.;t=73e-9;a.evolve(t)
    for i in range(1,101):b.evolve(t*i/100)
    assert abs(a.slow-b.slow)<1e-13 and abs(a.decision_value()-b.decision_value())<1e-13
    c=EqualizedReceiver([],1e9,0,boost=2);c.held=1.;t=.37e-9;n=20000;dt=t/n
    integral=sum(c.eq_pole*math.exp(-c.eq_pole*(t-(i+.5)*dt))*(1-math.exp(-c.pole*(i+.5)*dt))*dt for i in range(n))
    c.evolve(t);assert abs(c.slow-integral)<1e-9
    assert abs(c.decision_value()-(3*(1-math.exp(-c.pole*t))-2*integral))<2e-9
    assert all(not r['exact_words'] for r in rows if r['channel_ratio']==.03)
    assert any(r['exact_words'] for r in rows if r['boost']>0)
    return rows


def main():
    checks=controls();rows=[]
    for mode in (0,1):
        for boost in (0.,1.):
            factory=lambda **kw:EqualizedChip(rx_boost=boost,**kw)
            row=run(mode,100,chip_factory=factory,matched_reference=True,host_ppm=-100)
            row['rx_boost']=boost;rows.append(row)
    report=dict(status='passed',channel_screen=checks,cases=rows,complete_architecture=False,physical_qualification=False,
        limitations=['Ideal CTLE envelope with high-frequency gain1+boost and DC gain1; no internal noise or overload.',
        'Equalized zero crossings are found from exact two-exponential segments; data decisions use the same output.',
        'No automatic adaptation or hardware trim mapping; channel loss sweep reports failures without claiming universal recovery.',
        'Compatible receiver replacement retains channel/equalizer states and absolute poles; topology changes remain unsupported.'])
    (P/'evidence/connected-wired-equalizer.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed20 channel/equalizer screens, quadrature/subdivision controls and four sustained equalized cases')

if __name__=='__main__':main()
