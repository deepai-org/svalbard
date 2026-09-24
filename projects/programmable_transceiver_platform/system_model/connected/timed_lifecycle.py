"""Independent DAC deadlines in the persistent framed lifecycle controller."""
from collections import deque
from sample_clock import SampleClock
from wired_serializer import Serializer
import json
import math
from chip_model import P, encode, encode_iq
from burst_codec import BurstEncoder
from whole_chip_lifecycle import WholeChip, expect_rejection

class TimedChip(WholeChip):
    def __init__(self,dac_latency_s=0.,dac_pipeline_capacity=4, **kwargs):
        if not math.isfinite(dac_latency_s) or dac_latency_s<0 or not isinstance(dac_pipeline_capacity,int) or dac_pipeline_capacity<1:
            raise ValueError('Invalid DAC pipeline contract')
        super().__init__(**kwargs)
        self.dac_latency=dac_latency_s;self.dac_pipeline_capacity=dac_pipeline_capacity
        self.dac_pending=deque();self.dac_pipeline_updates=0;self.dac_cancelled=0
        self.serializer=None
        self.next_sample=math.inf
        self.remaining=0
        self.played=[]
        self.wire_queue=deque()
        self.wire_capacity=128
        self.next_wire=math.inf
        self.wire_remaining=0
        self.wire_accepted=self.wire_consumed=self.wire_discarded=0
        self.wire_partial_discarded=0
        self.wire_underflows=0
        self.wire_times=[]

    def configure(self,mode,time):
        previous=self.serializer
        super().configure(mode,time)
        if previous is not None:
            # The external channel is not erased or widened by local mode reset.
            # super().configure advanced the old serializer to this time first.
            self.channel.state=previous.channel.state
            if hasattr(self.channel,'current_state'):
                self.channel.current_state=getattr(previous.channel,'current_state',previous.drive)
                for name in ('tail_state','common_drop_state'):
                    if hasattr(previous.channel,name):setattr(self.channel,name,getattr(previous.channel,name))
            self.channel.decay=math.exp(-previous.pole/self.channel.rate)
        self.serializer=self.make_serializer(time)
        if previous is not None:self.serializer.pole=previous.pole
        contract=json.loads((P/'spec/contract.json').read_text())
        budget=contract['transport']['scheduling']['egress_bits_per_source']
        self.wire_capacity=budget//10
        self.tx.capacity=budget//(2*self.bits)

    def make_serializer(self,time):
        return Serializer(self.channel,time)

    def next_wire_deadline(self,deadline):
        return deadline+self.wire_period

    def schedule(self, count, start, ppm=0, jitter_s=0):
        if self.state!='active' or self.remaining or self.dac_pending or start<=self.time or count<0:
            raise ValueError('Playback requires active idle engine and future start')
        self.period=1/((40e6 if self.session.mode==0 else 20e6)*(1+ppm*1e-6))
        self.sample_clock=SampleClock(start,self.period,jitter_s)
        self.remaining=count
        self.next_sample=self.sample_clock.edge() if count else math.inf

    def accept_wire(self,value):
        if len(self.wire_queue)>=self.wire_capacity:
            raise OverflowError('Wired TX queue full')
        self.wire_queue.append(value);self.wire_accepted+=1

    def schedule_wire(self,count,start,ppm=0):
        if self.state!='active' or self.wire_remaining or (self.serializer is not None and self.serializer.active) or start<=self.time or count<0:
            raise ValueError('Wired playback requires active idle engine and future start')
        self.wire_period=10/(self.channel.rate*(1+ppm*1e-6))
        self.wire_remaining=count
        self.next_wire=start if count else math.inf

    def wire_accounting(self):
        assert self.wire_accepted==self.wire_consumed+self.wire_discarded+len(self.wire_queue)
        pending=int(self.serializer is not None and self.serializer.active)
        assert self.wire_consumed==len(self.wired_output)+self.wire_partial_discarded+pending
        return dict(completed_words=len(self.wired_output),partial_words_discarded=self.wire_partial_discarded,serializing=pending,accepted=self.wire_accepted,consumed=self.wire_consumed,
                    discarded=self.wire_discarded,pending=len(self.wire_queue),underflows=self.wire_underflows)

    def quiesce(self,time,reason):
        if self.serializer is not None:
            self.wire_partial_discarded+=int(self.serializer.active);self.serializer.abort(time)
        super().quiesce(time,reason)
        self.dac_cancelled+=len(self.dac_pending);self.dac_pending.clear()
        self.remaining=0
        self.next_sample=math.inf
        clock=getattr(self,'sample_clock',None)
        if hasattr(clock,'stop'):clock.stop()
        self.wire_discarded+=len(self.wire_queue);self.wire_queue.clear()
        self.wire_remaining=0;self.next_wire=math.inf

    def complete_dac(self,time):
        while self.dac_pending and self.dac_pending[0][0]<=time:
            deadline,epoch,value=self.dac_pending[0]
            if epoch!=self.epoch:raise AssertionError('Stale DAC update survived epoch barrier')
            self.tx.apply_sample(value,deadline);self.dac_pending.popleft();self.dac_pipeline_updates+=1
            self.played.append((deadline,self.tx.held))

    def dac_accounting(self):
        assert self.tx.consumed==self.dac_pipeline_updates+self.dac_cancelled+len(self.dac_pending)
        return dict(consumed=self.tx.consumed,updated=self.dac_pipeline_updates,cancelled=self.dac_cancelled,
                    pending=len(self.dac_pending),latency_s=self.dac_latency,capacity=self.dac_pipeline_capacity)

    @staticmethod
    def converter_consumed(clock,time,remaining):
        # Forecast-driven clocks commit even their final edge. Historical
        # prescribed clocks retain their existing eager stepping behavior.
        consume=getattr(clock,'consumed',None)
        return consume(time,remaining) if consume is not None else (clock.step() if remaining else math.inf)

    def provide_dac_sample(self):
        pass

    def advance(self,time):
        # DAC edge precedes a simultaneous incoming word. This conservative
        # ordering is deliberate; it never borrows a just-arriving payload.
        while min(self.next_sample,self.next_wire,self.dac_pending[0][0] if self.dac_pending else math.inf,self.serializer.deadline if self.serializer is not None else math.inf)<=time:
            deadline=min(self.next_sample,self.next_wire,self.dac_pending[0][0] if self.dac_pending else math.inf,self.serializer.deadline if self.serializer is not None else math.inf)
            super().advance(deadline)
            if self.state!='active':break
            self.complete_dac(deadline)
            if self.next_wire==deadline:
                if not self.wire_queue:
                    self.wire_underflows+=1
                    self.quiesce(deadline,'wired underflow');break
                self.serializer.start(self.wire_queue.popleft(),deadline,self.wire_period/10)
                self.wire_times.append(deadline);self.wire_consumed+=1
                self.wire_remaining-=1
                self.next_wire=self.next_wire_deadline(deadline) if self.wire_remaining else math.inf
            if self.serializer is not None and self.serializer.deadline==deadline:
                word=self.serializer.step()
                if word is not None:self.wired_output.append(word)
            if self.next_sample==deadline:
                if len(self.dac_pending)>=self.dac_pipeline_capacity:
                    self.quiesce(deadline,'DAC pipeline overflow');break
                self.provide_dac_sample()
                if not self.tx.queue:
                    self.tx.clock(deadline)
                    self.quiesce(deadline,'DAC underflow');break
                value=self.tx.queue.popleft();self.tx.consumed+=1
                self.dac_pending.append((deadline+self.dac_latency,self.epoch,value))
                self.complete_dac(deadline)
                self.remaining-=1
                self.next_sample=self.converter_consumed(self.sample_clock,deadline,self.remaining)
        super().advance(time)
        if self.serializer is not None:self.serializer.advance(time)


def run(mode,ppm,phase):
    c=TimedChip();c.configure(mode,0);c.advance(c.acquisition_s)
    rate=250e6 if mode==0 else 312.5e6
    def send(values,seq,start):
        c.descriptor(len(values));enc=BurstEncoder(2*c.bits,len(values));words=[]
        for value in values:words.extend(enc.push(encode_iq(value,c.bits)))
        words.extend(enc.finish())
        c.schedule(len(values),start,ppm)
        c.inflight+=1
        begin=c.time
        for i,word in enumerate(encode(c.session.mode,[17,801],words,seq)):
            c.feed(word,c.epoch,begin+(i+1)/rate)
        c.inflight-=1;c.finish_burst()
    # Entire small burst prefills through real frames; edges use an independent
    # oscillator period, never payload arrival or queue occupancy.
    start=c.time+(192+phase)/rate
    send([.5,.25,-.25],0,start)
    c.advance(start+c.period*.5)
    assert c.tx.consumed==1 and len(c.tx.queue)==2
    retained=c.tx.filtered
    assert abs(retained)>0
    c.set_reference(False,c.time)
    assert c.tx.accounting()['discarded']==2 and c.remaining==0
    c.advance(c.time+100e-9)
    assert abs(c.tx.filtered-retained*math.exp(-c.tx.pole*100e-9))<1e-12
    c.acknowledge_drain(c.epoch,c.time)
    c.set_reference(True,c.time);c.configure(1-mode,c.time)
    c.advance(c.time+c.acquisition_s)
    rate=250e6 if c.session.mode==0 else 312.5e6
    start=c.time+(192+phase)/rate
    send([-.5,-.25],0,start)
    c.advance(start+2*c.period)
    assert [v for _,v in c.played[-2:]]==[-.5,-.25]
    assert abs((c.played[-1][0]-c.played[-2][0])-c.period)<1e-18
    # No payload is synthesized when a scheduled sample cannot be delivered.
    c.schedule(1,c.time+c.period,ppm);c.advance(c.next_sample)
    assert c.state=='draining' and c.tx.underflows==1 and c.tx.held==0
    return dict(mode=mode,ppm=ppm,host_phase_words=phase,
                samples_played=len(c.played),accounting=c.tx.accounting(),events=c.events)


def simultaneous(mode,wire_ppm,rf_ppm):
    c=TimedChip();c.configure(mode,0);c.advance(c.acquisition_s)
    c.descriptor(3);enc=BurstEncoder(2*c.bits,3);iq=[]
    for v in (.5,.25,-.25):iq.extend(enc.push(encode_iq(v,c.bits)))
    iq.extend(enc.finish())
    rate=250e6 if mode==0 else 312.5e6
    begin=c.time;start=begin+192/rate
    c.schedule(3,start,rf_ppm);c.schedule_wire(4,start,wire_ppm)
    for i,w in enumerate(encode(mode,[17,801,3,999],iq,0)):
        c.feed(w,c.epoch,begin+(i+1)/rate)
    c.finish_burst()
    assert c.tx.consumed==0 and c.wire_consumed==0
    c.advance(start)
    assert c.tx.consumed==1 and c.wired_output==[] and c.serializer.active
    c.advance(start+1.5*c.wire_period)
    assert c.wired_output==[17] and c.tx.consumed==1 and c.serializer.active
    c.set_reference(False,c.time)
    assert c.wire_accounting()['discarded']==2 and c.tx.accounting()['discarded']==2
    assert c.serializer.accounting()==dict(started=2,completed=1,aborted=1,pending=0)
    c.acknowledge_drain(c.epoch,c.time);c.set_reference(True,c.time)
    c.configure(1-mode,c.time);c.advance(c.time+c.acquisition_s)
    rate=250e6 if c.session.mode==0 else 312.5e6
    begin=c.time;start=begin+192/rate
    c.schedule_wire(2,start,wire_ppm)
    for i,w in enumerate(encode(c.session.mode,[511,7],[],0)):
        c.feed(w,c.epoch,begin+(i+1)/rate)
    c.advance(start+2*c.wire_period)
    assert c.wired_output==[17,511,7]
    assert abs(c.wire_times[-1]-c.wire_times[-2]-c.wire_period)<1e-18
    c.schedule_wire(1,c.time+c.wire_period,wire_ppm);c.advance(c.next_wire)
    assert c.state=='draining' and c.wire_underflows==1
    return dict(mode=mode,wire_ppm=wire_ppm,rf_ppm=rf_ppm,
                wire=c.wire_accounting(),rf=c.tx.accounting())


def main():
    rows=[run(mode,ppm,phase) for mode in (0,1) for ppm in (-100,100) for phase in (0,.37)]
    concurrent=[simultaneous(mode,w,r) for mode in (0,1) for w in (-100,100) for r in (-100,100)]
    report=dict(status='passed',cases=rows,concurrent_cases=concurrent,complete_architecture=False,physical_qualification=False,
        limitations=['Small bursts with explicit prefill; full-throughput bidirectional pacing remains separate.',
        'Playback descriptors and drain acknowledgement are coherent management events, not SPI/CDC implementation.',
        'Constant frequency error only; acquisition and loss detection retain idealized assumptions.',
        'RF RX/return and continuous wired bit-clock state are not yet attached; wired events consume ten-bit words.'])
    (P/'evidence/connected-timed-lifecycle.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed eight DAC and eight simultaneous wired/DAC lifecycle scenarios')

if __name__=='__main__':main()
