"""Count-free RF/wired TX with simultaneous RF and wired receive traffic."""
from collections import deque
import hashlib,json,math,time
from pathlib import Path
from shared_tx_traffic import SharedOutputChip,scenario
from chip_model import encode,encode_iq,decode_iq
from continuous_iq_codec import StreamEncoder
from pacing import RationalPacer
from managed_resources import command

from continuous_duplex import PreparedChip, record_cases

def run(mode,stop,duplex=False,chip_factory=PreparedChip,preparation_s=8e-6,waveform=None):
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
    wire_pacer=RationalPacer(1,2) if mode==0 else RationalPacer(4,5)
    wire_words=deque();wire_source=[]
    incoming=[(i*43+17)%1024 for i in range(4096)]
    c.schedule_wire(math.inf,c.next_sample)
    c.incoming_wire(incoming,apply,.3,0)
    stimulus=None if waveform is None else list(waveform(1024,40e6 if mode==0 else 20e6))
    if stimulus is not None:
        assert len(stimulus)==1024 and all(math.isfinite(z.real) and math.isfinite(z.imag) and -1<=z.real<1 and -1<=z.imag<1 for z in stimulus)
    words=deque();source=[];stop_token=None;peak=0
    for frame in range(64):
        if frame==16 and stop:
            stop_token,_,stop_reply=c.submit('stop',c.time,c.epoch,c.rx_generation)
        for edge in range(64):
            if wire_pacer.tick():
                wire_value=(len(wire_source)*37+19)%1024
                wire_source.append(wire_value);wire_words.append(wire_value)
            if pacer.tick():
                i=len(source);sample=encode_iq(complex((i%7-3)/16,(i%5-2)/16) if stimulus is None else stimulus[i],c.bits)
                source.append(decode_iq(sample,c.bits));words.extend(encoder.push(sample))
        payload=[words.popleft() for _ in range(min(len(words),25 if mode==0 else 7))]
        wired_payload=[wire_words.popleft() for _ in range(min(len(wire_words),33 if mode==0 else 52))]
        for i,word in enumerate(encode(mode,wired_payload,payload,frame%64)):
            c.feed(word,c.epoch,apply+(frame*64+i+1)/rate)
            peak=max(peak,len(c.tx.queue))
        if c.state!='active':break
    if stop:
        assert c.state=='draining' and c.read_reply(stop_token,max(c.time,stop_reply))['accepted']
    else:
        assert c.state=='active' and math.isinf(c.remaining)
        c.advance(c.time+5e-6)
        assert c.state=='draining' and c.tx.underflows+c.wire_underflows==1
    assert c.read_reply(token,max(c.time,reply))['accepted']
    assert c.dac_pipeline_updates>128 and c.applied_inputs==source[:len(c.applied_inputs)] and len(c.applied_inputs)==len(c.played)
    assert peak<=c.tx.capacity and not c.dac_pending and c.remaining==0
    if duplex:
        assert len(c.host_samples)>128
        assert c.host_samples==c.adc_words[:len(c.host_samples)]
        c.adc_accounting()
    assert len(c.wired_output)>128 and c.wired_output==wire_source[:len(c.wired_output)]
    assert len(c.host_wire)>128 and c.host_wire==incoming[:len(c.host_wire)]
    wire_accounting=c.wire_accounting()
    accounting=c.dac_accounting();c.tx.accounting()
    epoch=c.epoch;c.acknowledge_host_abort(epoch,c.time);c.acknowledge_drain(epoch,c.time)
    assert c.decoder is None and c.state=='reset'
    return dict(mode=mode,management_stop=stop,duplex=duplex,rx_samples=len(c.host_samples),updates=c.dac_pipeline_updates,queue_peak=peak,accounting=accounting,wire_accounting=wire_accounting,wire_tx_words=len(c.wired_output),wire_rx_words=len(c.host_wire))

def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    p=scenario.architecture.P;start=time.monotonic()
    files=list(scenario.architecture.D.glob('*.py'))+list(Path(__file__).parent.glob('*.py'))+[p/'verification/stream_codec.py']
    hashes={str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    report=dict(status='running',source_sha256=hashes,cases=[],physical_qualification=False,
        limitations=['Finite observation: TX engines and RF RX are count-free; external wired source contains 4096 words.',
                     'Input sample order and transport checked, not continuous RF waveform quality.',
                     'Loopback does not include nonlinear TX output stage; independent TX quality tested separately.',
                     'Stop uses lossy abort, not graceful drain.'])
    output=p/'evidence/fast-continuous-four-path.json'
    def save():output.write_text(json.dumps(report,indent=2)+'\n')
    save()
    record_cases(run, report, save, p, hashes, start)

if __name__=='__main__':main()
