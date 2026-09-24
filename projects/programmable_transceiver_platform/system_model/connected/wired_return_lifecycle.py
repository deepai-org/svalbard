"""Recovered wired words share timed return frames with sampled RF data."""
from collections import deque
import json
from chip_model import P,encode,encode_iq
from burst_codec import BurstEncoder
from recovered_clock import framed_words
from rf_return_lifecycle import ReturnChip

class DuplexChip(ReturnChip):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        self.rx_events=deque();self.wired_return=deque();self.host_wire=[]
        self.rx_accepted=self.rx_discarded=self.rx_staged=0

    def incoming_wire(self,words,start,phase=.3,ppm=100):
        if self.state!='active' or self.rx_events or start<self.time:
            raise ValueError('Incoming link requires active idle receiver')
        rate=self.channel.rate
        recovered,times,metadata=framed_words(words,rate,phase,ppm)
        origin=start+(metadata['training_bits']+metadata['marker_bits'])/rate
        self.rx_events.extend((origin+float(t),int(w)) for t,w in zip(times,recovered))
        self.rx_metadata=metadata

    def configure_record_return(self,enabled=True):
        if type(enabled) is not bool or self.state!='reset' or self.session.armed:
            raise ValueError('Stopped record-return control required')
        if not enabled:
            if hasattr(self,'record_source'):self.record_source.reset()
            self.record_return=False
            return
        if self.state!='reset' or self.session.armed or self.host_frame_words!=8 or self.active_engine!='wire' or not self.wired_rx_enabled:
            raise ValueError('Stopped short-frame wired configuration required')
        from bit_event_stream import BitEventStream
        self.record_return=True;self.record_source=BitEventStream(16);self.host_records=[]
        self.record_generation=self.resource_generation

    def require_record_configuration(self):
        if (not getattr(self,'record_return',False) or self.record_generation!=self.resource_generation
                or self.active_engine!='wire' or self.host_frame_words!=8 or not self.wired_rx_enabled):
            raise ValueError('Raw record configuration is absent or stale')

    def observe_record(self,kind,value,time):
        self.require_record_configuration()
        if self.state!='active' or time!=self.time:
            raise ValueError('Raw observation requires active aligned chip time')
        if kind not in ('bit','event'):raise ValueError('Raw observation kind')
        try:
            getattr(self.record_source,kind)(value,time)
        except ValueError:
            if self.record_source.fault:self.quiesce(time,'raw record overflow')
            raise

    def encode_return_frame(self,words,sequence):
        if getattr(self,'record_return',False):
            self.require_record_configuration()
            if words:raise ValueError('Raw record return has no IQ slots')
            from bit_event_codec import snapshot_records
            return snapshot_records(self.record_source,sequence)
        quota=self.host_quota('wire')
        wire=[self.wired_return.popleft() for _ in range(min(quota,len(self.wired_return)))]
        self.rx_staged+=len(wire)
        return self.encode_host_frame(wire,words,sequence)

    def accept_host_event(self,event):
        if getattr(self,'record_return',False) and event and event[0] in ('data','event'):
            self.host_records.append((self.time,event));return
        super().accept_host_event(event)
        if event and event[0]=='wire':self.host_wire.append(event[1])

    def quiesce(self,time,reason):
        super().quiesce(time,reason)
        if hasattr(self,'record_source'):self.record_source.reset()
        self.record_return=False
        self.rx_events.clear()
        self.rx_discarded+=len(self.wired_return);self.wired_return.clear()

    def advance(self,time):
        while self.rx_events and self.rx_events[0][0]<=time:
            when,word=self.rx_events.popleft()
            super().advance(when)
            if self.state!='active':break
            if len(self.wired_return)>=128:
                self.quiesce(when,'wired RX return overflow');break
            self.wired_return.append(word);self.rx_accepted+=1
        super().advance(time)
        assert self.rx_accepted==self.rx_staged+self.rx_discarded+len(self.wired_return)


def run(mode,phase,ppm,interrupt=False,jitter_s=0):
    c=DuplexChip(watchdog_s=20e-6);c.configure(mode,0);c.advance(c.acquisition_s)
    input_wire=[(i*37+19)%1024 for i in range(80)]
    c.incoming_wire(input_wire,c.time,phase,ppm)
    c.descriptor(3);enc=BurstEncoder(2*c.bits,3);words=[]
    for value in (.5,-.25,.125):words+=enc.push(encode_iq(value,c.bits))
    words+=enc.finish();rate=250e6 if mode==0 else 312.5e6
    begin=c.time;start=begin+192/rate
    c.schedule(3,start,-ppm,jitter_s=jitter_s);c.schedule_wire(2,start,ppm)
    c.capture(3,start+10e-9,ppm,host_ppm=-ppm,jitter_s=-jitter_s)
    for i,word in enumerate(encode(mode,[17,801],words,0)):
        c.feed(word,c.epoch,begin+(i+1)/rate)
    c.finish_burst()
    if interrupt:
        cut=c.rx_events[20][0]
        c.advance(cut)
        assert c.rx_accepted>=21
        c.set_reference(False,c.time)
        before=list(c.host_wire);c.advance(c.time+2e-6)
        assert c.host_wire==before and not c.rx_events and not c.wired_return
        assert c.host_wire==input_wire[:len(c.host_wire)]
    else:
        c.advance(begin+4e-6);c.host_decoder.finish()
        assert c.host_wire==input_wire
        assert c.host_samples==c.adc_words and len(c.adc_words)==3
        assert c.wired_output==[17,801] and c.tx.consumed==3
    return dict(mode=mode,phase_ui=phase,ppm=ppm,interrupted=interrupt,
        recovered=c.rx_accepted,host_wired=len(c.host_wire),host_rf=len(c.host_samples),
        recovery=c.rx_metadata,jitter_s=jitter_s,adc_words=c.adc_words)


def main():
    rows=[run(m,p,f,stop) for m in (0,1) for p in (-.3,.3) for f in (-100,100) for stop in (False,True)]
    report=dict(status='passed',cases=rows,complete_architecture=False,physical_qualification=False,
        limitations=['Recovery is computed from a fixed external waveform, then delivered at causal completion times; receiver feedback under shared supply disturbance is absent.',
        'Training and64-bit marker are test-link framing, not PCIe or Ethernet PCS.',
        'Coherent host abort remains assumed; partial emitted frames and subsequent retraining need explicit protocol handling.',
        'Small finite traffic; sustained rates, RF impairments and realistic PLL/control state remain open.'])
    (P/'evidence/connected-wired-return-lifecycle.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed16 four-path shared-controller and interrupted-receive cases')

if __name__=='__main__':main()
