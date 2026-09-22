"""Payload edges from the same undisturbed linear trajectory used for lock."""
import json,math
from sample_clock import SampleClock
from clock_lock_lifecycle import LockedChip,LinearClock
from chip_model import P,encode,encode_iq
from burst_codec import BurstEncoder

class LoopEdges(SampleClock):
    def __init__(self,start,period,state,state_time,jitter_s=0):
        super().__init__(start,period,jitter_s)
        self.phase=state.phase;self.frequency=state.frequency;self.omega=state.omega
        self.state_time=state_time
    def phase_at(self,t):
        dt=t-self.state_time
        if dt<0:raise ValueError('Edge predates loop state')
        return (self.phase+(self.frequency+self.omega*self.phase)*dt)*math.exp(-self.omega*dt)
    def edge(self):
        nominal=super().edge()
        lo,hi=max(self.state_time,nominal-self.period/4),nominal+self.period/4
        def residual(t):return t+self.phase_at(t)/40e6-nominal
        if lo>=hi or residual(lo)>0 or residual(hi)<0:
            raise ValueError('Phase trajectory outside local edge bracket')
        for _ in range(55):
            mid=(lo+hi)/2
            if residual(mid)>0:hi=mid
            else:lo=mid
        return (lo+hi)/2

class PhasedChip(LockedChip):
    def disturb_clock(self,time,phase_cycles=0,frequency_hz=0):
        if not all(math.isfinite(v) for v in (time,phase_cycles,frequency_hz)):
            raise ValueError('Nonfinite clock disturbance')
        self.advance(time)
        if self.state!='active':raise ValueError('Clock disturbance requires active state')
        self.clock.advance(time-self.clock_time);self.clock_time=time
        self.clock.phase+=phase_cycles;self.clock.frequency+=frequency_hz
        updated=[]
        for attr,next_attr,pending in [('sample_clock','next_sample',self.remaining),
                                       ('adc_clock','next_adc',self.adc_left)]:
            if not pending:continue
            old=getattr(self,attr)
            new=LoopEdges(old.start,old.period,self.clock,time,old.jitter)
            new.index=old.index
            try:
                deadline=new.edge()
                if deadline<=time:raise ValueError('Edge would replay at or before intervention')
            except ValueError:
                self.quiesce(time,'clock edge discontinuity')
                return False
            updated.append((attr,next_attr,new,deadline))
        # Commit both clocks together only if both pending edges remain causal.
        for attr,next_attr,new,deadline in updated:
            setattr(self,attr,new);setattr(self,next_attr,deadline)
        return True

    def schedule(self,count,start,ppm=0,jitter_s=0):
        super().schedule(count,start,ppm,jitter_s)
        self.sample_clock=LoopEdges(start,self.period,self.clock,self.clock_time,jitter_s)
        if count:self.next_sample=self.sample_clock.edge()
    def capture(self,count,start,ppm=0,host_ppm=0,gain=.5,jitter_s=0):
        super().capture(count,start,ppm,host_ppm,gain,jitter_s)
        self.adc_clock=LoopEdges(start,self.adc_period,self.clock,self.clock_time,jitter_s)
        if count:self.next_adc=self.adc_clock.edge()


def controls():
    zero=LoopEdges(1e-6,25e-9,LinearClock(0,0),0)
    assert abs(zero.edge()-1e-6)<1e-20
    for sign in (-1,1):
        s=LinearClock(sign*.01,0)
        a=LoopEdges(100e-9,25e-9,s,0)
        first=a.edge();assert (first-100e-9)*sign<0
        assert abs(first+a.phase_at(first)/40e6-100e-9)<1e-20
        s.advance(10e-9);b=LoopEdges(100e-9,25e-9,s,10e-9)
        assert abs(a.edge()-b.edge())<1e-20
        edges=[a.edge()]+[a.step() for _ in range(100)]
        assert all(y>x for x,y in zip(edges,edges[1:]))


def run(mode,sign):
    c=PhasedChip(phase=sign*.25,frequency_hz=sign*40000,watchdog_s=20e-6)
    c.configure(mode,0)
    while c.state!='active':c.advance(c.next_reference)
    begin=c.time;rate=250e6 if mode==0 else 312.5e6;start=begin+192/rate
    c.descriptor(3);e=BurstEncoder(2*c.bits,3);words=[]
    for v in (.5,-.25,.125):words+=e.push(encode_iq(v,c.bits))
    words+=e.finish()
    c.schedule(3,start);first=c.next_sample
    c.capture(3,start+10e-9);c.schedule_wire(2,start)
    c.incoming_wire([3,511,97],begin)
    for i,w in enumerate(encode(mode,[17,801],words,0)):c.feed(w,c.epoch,begin+(i+1)/rate)
    c.finish_burst();c.advance(begin+3e-6);c.host_decoder.finish()
    assert c.host_wire==[3,511,97] and c.wired_output==[17,801]
    assert c.host_samples==c.adc_words and len(c.host_samples)==3
    assert c.played[0][0]==first and (first-start)*sign<0
    return dict(mode=mode,error_sign=sign,first_dac_edge_error_s=first-start,rf_samples=3,wired_words=3)


def main():
    controls();rows=[run(m,s) for m in (0,1) for s in (-1,1)]
    report=dict(status='passed',cases=rows,complete_architecture=False,physical_qualification=False,
        limitations=['Undisturbed linear near-lock trajectory is snapshotted when scheduling; later disturbances require invalidating pending deadlines.',
        'Phase expressed in40MHz reference cycles maps to shared absolute time error for ADC/DAC; divider and separate PLL effects absent.',
        'Wired serializer and host edge clocks remain independent ideal clocks.',
        'Local quarter-period root bracket does not establish nonlinear acquisition or cycle-slip behavior.'])
    (P/'evidence/connected-loop-driven-edges.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(rows,indent=2))

if __name__=='__main__':main()
