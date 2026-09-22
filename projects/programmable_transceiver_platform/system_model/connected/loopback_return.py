"""Causal D2H replay of feed-forward RF loopback plus simultaneous wired RX."""
from collections import deque
import math
from stream_codec import encode,Receiver,slots
from burst_codec import BurstEncoder,BurstDecoder


def return_samples(mode,adc_words,adc_ticks,sample_bits,wire_words,wire_ticks,capture=None,capture_ticks=None,burst_count=None):
    assert len(adc_words)==len(adc_ticks) and len(wire_words)==len(wire_ticks)
    burst=burst_count is not None
    if burst:
        encoder=BurstEncoder(sample_bits,burst_count)
        decoder=BurstDecoder(sample_bits,burst_count)
        if burst_count==0:encoder.finish()
    arrivals=sorted([(float(t),'iq',int(v)) for t,v in zip(adc_ticks,adc_words)]+
                    [(float(t),'wire',int(v)) for t,v in zip(wire_ticks,wire_words)],
                    key=lambda item:item[0])  # Stable ties preserve source order, not payload magnitude.
    plan=slots(mode);rx=Receiver(mode);queues={k:deque() for k in ('wire','iq')}
    prepared={k:[] for k in queues};received={k:[] for k in queues}
    peak={k:0 for k in queues};index=0;pack_value=pack_count=0
    unpack_value=unpack_count=0;latencies=[]
    # After the final arrival, each ingress may hold its full bit capacity.
    # Include a partially transmitted frame, the prepared snapshot and a final
    # frame boundary. This is a service-derived upper bound, not a magic timeout.
    ingress_capacity=1024
    drain_frames=max(math.ceil(math.ceil(ingress_capacity/10)/plan.count(k))
                     for k in queues)+3
    horizon=math.ceil(arrivals[-1][0] if arrivals else 0)+64*drain_frames
    for tick in range(horizon):
        while index<len(arrivals) and arrivals[index][0]<=tick:
            _,name,value=arrivals[index];index+=1
            if name=='wire':queues[name].append(value)
            elif burst:
                queues['iq'].extend(encoder.push(value))
                if encoder.accepted==encoder.count:
                    queues['iq'].extend(encoder.finish())
            else:
                pack_value|=value<<pack_count;pack_count+=sample_bits
                while pack_count>=10:
                    queues['iq'].append(pack_value & 1023)
                    pack_value>>=10;pack_count-=10
            occupied=len(queues[name])*10+((encoder.pending if burst else pack_count) if name=='iq' else 0)
            peak[name]=max(peak[name],occupied)
            assert occupied<=ingress_capacity, 'Provisional D2H ingress capacity exceeded'
        if tick%64==0:
            frame=encode(mode,prepared['wire'],prepared['iq'],(tick//64)%64)
            prepared={k:[queues[k].popleft() for _ in range(min(len(queues[k]),plan.count(k)))] for k in queues}
        event=rx.feed(frame[tick%64])
        if event and event[0] in queues:
            name,value=event
            if name=='wire':received[name].append(value)
            else:
                samples=[]
                if burst:
                    samples=decoder.feed(value)
                else:
                    unpack_value|=value<<unpack_count;unpack_count+=10
                    while unpack_count>=sample_bits:
                        samples.append(unpack_value & ((1<<sample_bits)-1))
                        unpack_value>>=sample_bits;unpack_count-=sample_bits
                for sample in samples:
                    received[name].append(sample)
                    delay=tick-float(adc_ticks[len(received[name])-1])
                    assert delay>=0
                    latencies.append(delay)
                    if capture_ticks is not None:capture_ticks.append(tick)
    if burst:
        assert encoder.closed, 'Declared burst count exceeds supplied samples'
        decoder.finish()
    assert received['iq']==list(adc_words) and received['wire']==list(wire_words)
    assert pack_count==unpack_count==0 and index==len(arrivals)
    assert all(not q for q in queues.values()) and all(not q for q in prepared.values())
    if capture is not None:capture.extend(received['iq'])
    return dict(adc_samples_returned=len(received['iq']),wired_words_returned=len(received['wire']),
                payload_errors=0,peak_ingress_bits=peak,
                burst_sample_count=burst_count,drain_bound_frames=drain_frames,
                maximum_adc_to_host_delay_ticks=max(latencies) if latencies else None,
                minimum_adc_to_host_delay_ticks=min(latencies) if latencies else None,
                execution='Feed-forward replay at absolute event times; no RF/host feedback coupling.')
