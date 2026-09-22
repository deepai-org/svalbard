"""Continuous calibrated RF duplex through the shared-ADC composition."""
from collections import deque
import hashlib,json,math,time
from pathlib import Path
from shared_tx_traffic import scenario
from chip import TransceiverChip
from chip_model import encode,encode_iq,decode_iq
from continuous_iq_codec import StreamEncoder
from pacing import RationalPacer
from managed_resources import command

class PreparedChip(TransceiverChip):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        for target in (0,1):
            assert command(self,'cal_start',48|(target<<16))['accepted']
            self.advance(self.time+40e-6)
        start=command(self,'tx_cal_start');assert start['accepted']
        self.advance(self.time+25e-6)
        assert command(self,'tx_cal_commit',start['value'])['accepted']
        self.applied_inputs=[]
        original=self.tx.apply_sample
        def observed(value,time):
            original(value,time)
            self.applied_inputs.append(value)
        self.tx.apply_sample=observed

def run(mode,stop,duplex=False,chip_factory=PreparedChip,preparation_s=8e-6):
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
    assert c.dac_pipeline_updates>128 and c.applied_inputs==source[:len(c.applied_inputs)] and len(c.applied_inputs)==len(c.played)
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
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    p=scenario.architecture.P;start=time.monotonic()
    files=list(scenario.architecture.D.glob('*.py'))+list(Path(__file__).parent.glob('*.py'))+[p/'verification/stream_codec.py']
    hashes={str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    report=dict(status='running',source_sha256=hashes,cases=[],physical_qualification=False,
        limitations=['Finite matched-rate RF duplex; simultaneous continuous wired paths remain open.',
                     'Input sample order and transport checked, not continuous RF waveform quality.',
                     'Loopback does not include nonlinear TX output stage; independent TX quality tested separately.',
                     'Stop uses lossy abort, not graceful drain.'])
    output=p/'evidence/fast-continuous-duplex.json'
    def save():output.write_text(json.dumps(report,indent=2)+'\n')
    save()
    try:
        for mode in (0,1):
            for stop in (False,True):
                report['cases'].append(run(mode,stop,True));save()
                print(mode,stop,'passed',flush=True)
        assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
        report.update(status='passed',elapsed_s=time.monotonic()-start)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));raise
    finally:save()

if __name__=='__main__':main()
