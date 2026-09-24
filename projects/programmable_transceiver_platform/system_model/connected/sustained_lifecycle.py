"""Source-paced finite sustained traffic through the persistent four-path model."""
from collections import deque
from fractions import Fraction
import json,math,hashlib
from chip_model import P,encode,encode_iq
from burst_codec import BurstEncoder
from wired_return_lifecycle import DuplexChip
from pacing import RationalPacer


class TrafficFault(AssertionError):
    def __init__(self,event):
        self.event=event
        super().__init__(event)


def run(mode,ppm,frames=128,chip_factory=DuplexChip,disturbance_sign=0,matched_reference=False,host_ppm=0,visibility_edges=0,source_phase_edges=0,service_pauses=None,waveform=None,*,_startup=None):
    if visibility_edges<0 or not math.isfinite(visibility_edges) or not math.isfinite(source_phase_edges):
        raise ValueError('Invalid visibility/phase')
    lag=Fraction(str(visibility_edges))+Fraction(str(source_phase_edges))
    if lag<0:raise ValueError('Negative source visibility lag')
    if lag and not matched_reference:raise ValueError('Visibility test requires matched rates')
    service_pauses=dict(service_pauses or {})
    if service_pauses and not matched_reference:raise ValueError('Pause tests require matched rates')
    if any(not isinstance(k,int) or k<1 or not isinstance(v,int) or v<0 for k,v in service_pauses.items()):
        raise ValueError('Pauses require positive frame index and nonnegative integer word periods')
    paused_edges=0;pause_observations=[]
    c=chip_factory(watchdog_s=20e-6)
    if _startup is None:
        c.configure(mode,0)
        if hasattr(c,'next_reference'):
            while c.state=='acquiring' and c.time<10e-6:c.advance(c.next_reference)
        else:c.advance(c.acquisition_s)
        assert c.state=='active'
    else:
        _startup(c,mode)
    interventions=[]
    host_rate=250e6 if mode==0 else 312.5e6
    fs=40e6 if mode==0 else 20e6;wr=125e6 if mode==0 else 250e6
    nominal_host_rate=host_rate
    production_frames=frames
    if matched_reference:
        if not isinstance(ppm,int) or not isinstance(host_ppm,int):raise ValueError('Integer ppm required for exact pacing ratios')
        host_rate*=1+host_ppm*1e-6
        duration=frames*64/(nominal_host_rate*(1+ppm*1e-6))
        production_frames=(frames*(1000000+host_ppm)+(1000000+ppm)-1)//(1000000+ppm)
        wn,wd,qn,qd=(1,2,4,25) if mode==0 else (4,5,8,125)
        wp=RationalPacer(wn,wd);qp=RationalPacer(qn,qd)
        generated_edges=produced_wire=produced_iq=0
        ns=(qd-qn+frames*64*qn)//qd;nw=(wd-wn+frames*64*wn)//wd
    else:
        duration=frames*64/host_rate
        ns=int(duration*fs);nw=int(duration*wr)
    values=[complex(.4*math.cos(i*.13),.3*math.sin(i*.17)) for i in range(ns)] if waveform is None else list(waveform(ns,fs))
    if len(values)!=ns or not all(math.isfinite(z.real) and math.isfinite(z.imag) and
                                  -1<=z.real<1 and -1<=z.imag<1 for z in values):
        raise ValueError('Source waveform must fit sample count and signed converter range')
    samples=[encode_iq(z,c.bits) for z in values]
    wire=[(i*37+19)%1024 for i in range(nw)]
    c.descriptor(ns);encoder=BurstEncoder(2*c.bits,ns)
    begin=c.time;start=begin+192/host_rate
    c.schedule(ns,start,ppm);c.schedule_wire(nw,start,ppm)
    c.capture(ns,start+10e-9,ppm,host_ppm=ppm if matched_reference else -ppm)
    c.incoming_wire(wire,begin,.3,-ppm)
    iq=deque();wq=deque();si=wi=0;frame=0;finished=False
    peaks=dict(rf_tx=0,wire_tx=0,rf_return=0,wire_return=0,source_iq=0,source_wire=0)
    while frame<=production_frames or si<ns or wi<nw or iq or wq:
        # External source samples generated during the preceding frame become
        # available for this frame. Fixed playback prefill covers that latency.
        if frame in service_pauses:
            delay=service_pauses[frame];paused_edges+=delay
            before=(c.tx.consumed,c.wire_consumed,len(c.adc_words))
            c.advance(begin+(frame*64+paused_edges)/host_rate)
            if c.state!='active':raise TrafficFault(c.events[-1])
            pause_observations.append(dict(frame=frame,word_periods=delay,
                dac_consumed=c.tx.consumed-before[0],wired_consumed=c.wire_consumed-before[1],
                adc_captured=len(c.adc_words)-before[2]))
        if disturbance_sign and frame in (40,80):
            old=c.next_sample;old_adc=c.next_adc
            sign=disturbance_sign*(1 if frame==40 else -1)
            assert c.disturb_clock(c.time,phase_cycles=sign*.001,frequency_hz=sign*500)
            assert (c.next_sample-old)*sign<0 and (c.next_adc-old_adc)*sign<0
            interventions.append(dict(frame=frame,dac_shift_s=c.next_sample-old,adc_shift_s=c.next_adc-old_adc))
        if matched_reference:
            available=max(0,min(frames*64,int((Fraction(frame*64+paused_edges)-lag)*(1000000+ppm)//(1000000+host_ppm))))
            while generated_edges<available:
                produced_wire+=wp.tick();produced_iq+=qp.tick();generated_edges+=1
            sn=produced_iq;wn=produced_wire
        else:
            upto=min(frame,frames)*64/host_rate
            sn=min(ns,int(upto*fs+1e-9));wn=min(nw,int(upto*wr+1e-9))
        while si<sn:iq.extend(encoder.push(samples[si]));si+=1
        while wi<wn:wq.append(wire[wi]);wi+=1
        if si==ns and not finished:iq.extend(encoder.finish());finished=True
        peaks['source_iq']=max(peaks['source_iq'],len(iq));peaks['source_wire']=max(peaks['source_wire'],len(wq))
        qwords=[iq.popleft() for _ in range(min(len(iq),25 if mode==0 else 7))]
        wwords=[wq.popleft() for _ in range(min(len(wq),33 if mode==0 else 52))]
        for i,word in enumerate(encode(mode,wwords,qwords,frame%64)):
            c.feed(word,c.epoch,begin+(frame*64+paused_edges+i+1)/host_rate)
            for key,value in [('rf_tx',len(c.tx.queue)),('wire_tx',len(c.wire_queue)),('rf_return',len(c.return_queue)),('wire_return',len(c.wired_return))]:
                peaks[key]=max(peaks[key],value)
            if c.state!='active':raise TrafficFault(c.events[-1])
        frame+=1
    c.finish_burst();c.advance(max(c.time,start+duration)+3e-6)
    c.host_decoder.finish()
    assert c.state=='active' and c.tx.consumed==ns and c.wire_consumed==nw
    assert c.wired_output==wire and c.host_wire==wire
    assert c.host_samples==c.adc_words and len(c.adc_words)==ns
    assert not c.tx.queue and not c.wire_queue and not c.wired_return and not c.return_queue
    assert c.tx.underflows==0 and c.wire_underflows==0
    return dict(service_pauses=pause_observations,visibility_edges=visibility_edges,source_phase_edges=source_phase_edges,matched_reference=matched_reference,host_service_ppm=host_ppm,adc_sha256=hashlib.sha256(json.dumps(c.adc_words,separators=(',',':')).encode()).hexdigest(),adc_checksum=sum((i+1)*w for i,w in enumerate(c.adc_words)),reference_metrics=c.reference_metrics() if hasattr(c,'reference_metrics') else None,controller=type(c).__name__,interventions=interventions,mode=mode,ppm=ppm,duration_s=duration,source_frames=frames,transmitted_frames=frame,
        rf_samples_each_direction=ns,wired_words_each_direction=nw,observed_queue_peaks=peaks,
        rf_accounting=c.tx.accounting(),wire_accounting=c.wire_accounting())


def main():
    rows=[run(mode,ppm) for mode in (0,1) for ppm in (-100,100)]
    report=dict(status='passed',cases=rows,complete_architecture=False,physical_qualification=False,
        limitations=['Finite128-frame runs are not infinite-duration drift or FIFO bounds.',
        'External traffic is generated frame-wise with a three-frame playback prefill; producer phase sweep remains open.',
        'Queue peaks are observed after host events, not a proof of peak occupancy between events.',
        'Ideal coherent RF gain, deterministic clocks, batch wired recovery and abstract management remain.'])
    (P/'evidence/connected-sustained-lifecycle.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(rows,indent=2))

if __name__=='__main__':main()
