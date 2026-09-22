"""Sampled RF envelope and word-clocked host return in the persistent controller."""
from collections import deque
from sample_clock import SampleClock
from adc_recovery import ADCRecovery
import json,math
from chip_model import P,encode,Receiver,encode_iq
from burst_codec import BurstEncoder,BurstDecoder
from timed_lifecycle import TimedChip
from rf_cascade_state import RfCascadeState, controls as cascade_controls

class ReturnChip(TimedChip):
    def __init__(self,adc_latency_s=0.,adc_pipeline_capacity=4,adc_recovery_tau_s=0.,adc_recovery_gain=0.,**kwargs):
        if not math.isfinite(adc_latency_s) or adc_latency_s<0 or not isinstance(adc_pipeline_capacity,int) or adc_pipeline_capacity<1:
            raise ValueError('Invalid ADC pipeline contract')
        self.adc_recovery=ADCRecovery(adc_recovery_tau_s,adc_recovery_gain)
        super().__init__(**kwargs)
        self.adc_latency=adc_latency_s;self.adc_pipeline_capacity=adc_pipeline_capacity
        self.adc_pending=deque();self.adc_sampled=0;self.adc_completed=0;self.adc_cancelled=0
        self.tx=RfCascadeState(self.session)
        self.next_adc=self.next_return=math.inf
        self.adc_left=0;self.return_queue=deque();self.return_frame=deque()
        self.return_capacity=128;self.return_sequence=0
        self.adc_words=[];self.host_samples=[];self.return_ticks=0
        self.return_discarded=0
        self.host_abort_epoch=None
        self.adc_diagnostics=dict(conversions=0,clipped_samples=0,i_low=0,i_high=0,q_low=0,q_high=0)

    def capture(self,count,start,ppm=0,host_ppm=0,gain=.5,jitter_s=0):
        if self.state!='active' or self.adc_left or self.adc_pending or self.return_queue or self.return_frame or start<=self.time:
            raise ValueError('Capture requires idle active stream and future start')
        self.adc_encoder=BurstEncoder(2*self.bits,count)
        self.host_decoder=BurstDecoder(2*self.bits,count)
        self.host_receiver=Receiver(self.session.mode)
        self.return_sequence=0
        self.adc_left=count;self.next_adc=start if count else math.inf
        self.adc_period=1/((40e6 if self.session.mode==0 else 20e6)*(1+ppm*1e-6))
        self.adc_clock=SampleClock(start,self.adc_period,jitter_s)
        self.return_period=1/((250e6 if self.session.mode==0 else 312.5e6)*(1+host_ppm*1e-6))
        self.next_return=self.time+self.return_period;self.gain=gain
        if not count:self.adc_encoder.finish()

    def quiesce(self,time,reason):
        super().quiesce(time,reason)
        self.adc_cancelled+=len(self.adc_pending);self.adc_pending.clear()
        self.next_adc=self.next_return=math.inf;self.adc_left=0
        self.return_discarded+=len(self.return_queue)+len(self.return_frame)
        self.return_queue.clear();self.return_frame.clear()
        self.host_abort_epoch=None
        # Retain host decoder state until explicit management acknowledgement.

    def acknowledge_host_abort(self,epoch,time):
        self.advance(time)
        if self.state!='draining' or epoch!=self.epoch:
            raise ValueError('Host abort requires matching stopped epoch')
        if hasattr(self,'host_receiver'):self.host_receiver.reset()
        self.host_decoder=None
        self.host_abort_epoch=epoch

    def acknowledge_drain(self,epoch,time):
        if self.host_abort_epoch!=epoch:
            raise ValueError('Host must discard partial return frame before drain acknowledgement')
        super().acknowledge_drain(epoch,time)

    def queue_adc_words(self,words,time):
        if len(self.return_queue)+len(words)>self.return_capacity:
            self.quiesce(time,'ADC return overflow');return False
        self.return_queue.extend(words);return True

    def emitted_return_word(self,word,time):
        pass

    def receiver_value(self):
        return self.gain*self.tx.received

    def clear_adc_diagnostics(self):
        if self.session.armed:raise ValueError('ADC diagnostics clear requires disarmed state')
        for key in self.adc_diagnostics:self.adc_diagnostics[key]=0

    def quantize_adc(self,value):
        if not math.isfinite(value.real) or not math.isfinite(value.imag):
            raise ValueError('Nonfinite ADC input')
        scale=1 << (self.bits-1);mask=(1 << self.bits)-1;codes=[];clipped=False
        for axis,x in (('i',value.real),('q',value.imag)):
            raw=-scale-1 if x < -2 else scale if x>=1 else round(x*scale)
            low=raw < -scale;high=raw > scale-1
            self.adc_diagnostics[axis+'_low']+=int(low);self.adc_diagnostics[axis+'_high']+=int(high)
            clipped=clipped or low or high
            codes.append(max(-scale,min(scale-1,raw)) & mask)
        self.adc_diagnostics['conversions']+=1;self.adc_diagnostics['clipped_samples']+=int(clipped)
        return codes[0] | (codes[1] << self.bits)

    def convert_adc(self,value):
        return self.quantize_adc(self.adc_recovery.sample(value,self.tx.time))

    def adc_became_valid(self,word,time):
        pass

    def complete_adc(self,time):
        while self.adc_pending and self.adc_pending[0][0]<=time:
            deadline,epoch,word,last=self.adc_pending.popleft()
            if epoch!=self.epoch:raise AssertionError('Stale ADC conversion survived epoch barrier')
            self.adc_completed+=1;self.adc_words.append(word)
            self.adc_became_valid(word,deadline)
            words=self.adc_encoder.push(word)
            if last:words+=self.adc_encoder.finish()
            if not self.queue_adc_words(words,deadline):return False
        return True

    def adc_accounting(self):
        assert self.adc_sampled==self.adc_completed+self.adc_cancelled+len(self.adc_pending)
        return dict(sampled=self.adc_sampled,completed=self.adc_completed,cancelled=self.adc_cancelled,
                    pending=len(self.adc_pending),latency_s=self.adc_latency,capacity=self.adc_pipeline_capacity)

    def encode_return_frame(self,words,sequence):
        return encode(self.session.mode,[],words,sequence)

    def accept_host_event(self,event):
        if event and event[0]=='iq':self.host_samples.extend(self.host_decoder.feed(event[1]))

    def advance(self,time):
        def next_event():return min(self.next_adc,self.next_return,self.adc_pending[0][0] if self.adc_pending else math.inf)
        while next_event()<=time:
            deadline=next_event()
            super().advance(deadline)
            if self.state!='active':break
            if not self.complete_adc(deadline):break
            if self.next_adc==deadline:
                if len(self.adc_pending)>=self.adc_pipeline_capacity:
                    self.quiesce(deadline,'ADC pipeline overflow');break
                sample=self.convert_adc(self.receiver_value())
                self.adc_left-=1;self.adc_sampled+=1
                self.adc_pending.append((deadline+self.adc_latency,self.epoch,sample,not self.adc_left))
                self.next_adc=self.adc_clock.step() if self.adc_left else math.inf
                if not self.complete_adc(deadline):break
            if self.next_return==deadline:
                if not self.return_frame:
                    quota=25 if self.session.mode==0 else 7
                    words=[self.return_queue.popleft() for _ in range(min(quota,len(self.return_queue)))]
                    self.return_frame.extend(self.encode_return_frame(words,self.return_sequence))
                    self.return_sequence=(self.return_sequence+1)%64
                emitted=self.return_frame.popleft()
                self.emitted_return_word(emitted,deadline)
                event=self.host_receiver.feed(emitted)
                self.accept_host_event(event)
                self.return_ticks+=1;self.next_return=deadline+self.return_period
        super().advance(time)


def run(mode,ppm,interrupt=False):
    c=ReturnChip(watchdog_s=20e-6);c.configure(mode,0);c.advance(c.acquisition_s)
    c.descriptor(3);e=BurstEncoder(2*c.bits,3);words=[]
    for value in (.5,-.25,.125):words+=e.push(encode_iq(value,c.bits))
    words+=e.finish();rate=250e6 if mode==0 else 312.5e6
    begin=c.time;start=begin+192/rate
    c.schedule(3,start,-ppm);c.schedule_wire(2,start,ppm)
    c.capture(3,start+10e-9,ppm,host_ppm=-ppm)
    for i,word in enumerate(encode(mode,[17,801],words,0)):
        c.feed(word,c.epoch,begin+(i+1)/rate)
    c.finish_burst()
    if interrupt:
        c.advance(start+10e-9)
        assert len(c.adc_words)==1 and c.return_queue
        c.set_reference(False,c.time)
        assert not c.return_queue and not c.return_frame and math.isinf(c.next_adc)
        before=list(c.host_samples);c.advance(c.time+1e-6)
        assert c.host_samples==before
    else:
        c.advance(start+1e-6)
        c.host_decoder.finish()
        assert len(c.host_samples)==3 and c.host_samples==c.adc_words
        assert c.wired_output==[17,801] and c.tx.consumed==3
        expected=encode_iq(.25*(1-(1+c.tx.pole*10e-9)*math.exp(-c.tx.pole*10e-9)),c.bits)
        assert c.adc_words[0]==expected
    return dict(mode=mode,ppm=ppm,interrupted=interrupt,captured=len(c.adc_words),
                returned=len(c.host_samples),return_word_ticks=c.return_ticks,
                discarded_transport_words=c.return_discarded)


def main():
    cascade_controls()
    rows=[run(mode,ppm,interrupt) for mode in (0,1) for ppm in (-100,100) for interrupt in (False,True)]
    report=dict(status='passed',cases=rows,complete_architecture=False,physical_qualification=False,
        limitations=['RF uses equal10MHz one-pole TX/RX filters with ideal coherent gain and quantization; mixer impairments and noise remain open.',
        'Return uses real frames at independent word deadlines, with coherent host abort on reference loss assumed.',
        'Small bursts only; continuous throughput, wired RX and management/CDC timing remain open.',
        'An ADC edge coincident with host service is available to that frame; TX edges precede ADC sampling.'])
    (P/'evidence/connected-rf-return-lifecycle.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed eight sampled RF round-trip and interrupted-return scenarios')

if __name__=='__main__':main()
