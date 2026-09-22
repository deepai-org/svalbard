"""Continuous TX via actual framed host words, shared clocks and DAC pipeline."""
from collections import deque
import json,math
from chip_model import P,encode,encode_iq,decode_iq
from programmable_chip import ProgrammableChip
from continuous_iq_codec import StreamEncoder
from pacing import RationalPacer

def run(mode,stop,duplex=False,chip_factory=ProgrammableChip,preparation_s=8e-6):
    c=chip_factory(watchdog_s=100e-6,dac_latency_s=20e-9)
    c.configure(mode,c.time);c.advance(c.time+preparation_s)
    token,apply,reply=c.submit('stream_start' if duplex else 'tx_stream_start',c.time,c.epoch,c.rx_generation,(32<<2)|3 if duplex else 32)
    c.advance(apply-1e-12);assert c.remaining==0 and c.decoder is None
    c.advance(apply);assert math.isinf(c.remaining)
    if duplex:
        assert math.isinf(c.adc_left)
        assert abs(c.next_adc-c.next_sample-c.local_rx_offset_s)<1e-15
    encoder=StreamEncoder(2*c.bits);pacer=RationalPacer(4,25) if mode==0 else RationalPacer(8,125)
    rate=250e6 if mode==0 else 312.5e6
    words=deque();source=[];stop_token=None;peak=0
    for frame in range(64):
        if frame==16 and stop:
            stop_token,_,stop_reply=c.submit('stop',c.time,c.epoch,c.rx_generation)
        for edge in range(64):
            if pacer.tick():
                i=len(source);sample=encode_iq(complex((i%7-3)/16,(i%5-2)/16),c.bits)
                source.append(decode_iq(sample,c.bits));words.extend(encoder.push(sample))
        payload=[words.popleft() for _ in range(min(len(words),25 if mode==0 else 7))]
        for i,word in enumerate(encode(mode,[],payload,frame%64)):
            c.feed(word,c.epoch,apply+(frame*64+i+1)/rate)
            peak=max(peak,len(c.tx.queue))
        if c.state!='active':break
    if stop:
        assert c.state=='draining' and c.read_reply(stop_token,max(c.time,stop_reply))['accepted']
    else:
        assert c.state=='active' and math.isinf(c.remaining)
        c.advance(c.time+5e-6)
        assert c.state=='draining' and c.tx.underflows==1
    assert c.read_reply(token,max(c.time,reply))['accepted']
    assert c.dac_pipeline_updates>128 and [z for _,z in c.played]==source[:len(c.played)]
    assert peak<=c.tx.capacity and not c.dac_pending and c.remaining==0
    if duplex:
        assert len(c.host_samples)>128
        assert c.host_samples==c.adc_words[:len(c.host_samples)]
        c.adc_accounting()
    accounting=c.dac_accounting();c.tx.accounting()
    epoch=c.epoch;c.acknowledge_host_abort(epoch,c.time);c.acknowledge_drain(epoch,c.time)
    assert c.decoder is None and c.state=='reset'
    return dict(mode=mode,management_stop=stop,duplex=duplex,rx_samples=len(c.host_samples),updates=c.dac_pipeline_updates,queue_peak=peak,accounting=accounting)

def main():
    rows=[run(m,s) for m in (0,1) for s in (False,True)]+[run(m,True,True) for m in (0,1)]
    (P/'evidence/connected-continuous-transmit.json').write_text(json.dumps(dict(status='passed',cases=rows,
        complete_architecture=False,physical_qualification=False,
        limitations=['Finite matched-rate observation, not a proof for arbitrary host service or ppm mismatch.',
        'Stop aborts pending samples; no lossless stop protocol.',
        'Duplex cases use direct RX start alongside timed TX; atomic dual-start and triggers remain open.']),indent=2)+'\n')
    print('Passed continuous framed TX, exact DAC sequence, timed stop and underrun')
if __name__=='__main__':main()
