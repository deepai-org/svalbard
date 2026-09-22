"""Count-free RX transport, timed start/stop and bounded-buffer failure."""
import json,math
from chip_model import P
from programmable_chip import ProgrammableChip
from managed_resources import command
from continuous_iq_codec import StreamEncoder,StreamDecoder

def codec():
    for bits in (16,24):
        e=StreamEncoder(bits);d=StreamDecoder(bits);samples=[];observed=[]
        for i in range(1003):
            v=(i*7919+13)% (1<<bits);samples.append(v)
            for w in e.push(v):observed.extend(d.feed(w))
            assert e.pending<10 and d.pending<bits
        assert observed==samples[:len(observed)] and len(samples)-len(observed)<=1

def run(mode,overflow=False):
    c=ProgrammableChip(watchdog_s=100e-6,adc_latency_s=30e-9)
    c.configure_rx('external_tone',1,5e6,5e6,.2+.1j,250e3)
    c.configure(mode,0);c.advance(8e-6)
    token,apply,reply=c.submit('rx_stream_start',c.time,c.epoch,c.rx_generation,8)
    c.advance(apply-1e-12);assert c.adc_left==0
    assert c.read_reply(token,reply)['accepted'] and math.isinf(c.adc_left)
    if overflow:c.return_period=1e-6
    c.advance(c.time+10e-6)
    if overflow:
        assert c.state=='draining' and c.adc_left==0 and not c.adc_pending
    else:
        assert c.state=='active' and c.adc_sampled>128 and math.isinf(c.adc_left)
        assert c.host_samples==c.adc_words[:len(c.host_samples)] and len(c.host_samples)>128
        assert len(c.return_queue)<=c.return_capacity and len(c.adc_pending)<=c.adc_pipeline_capacity
        assert not command(c,'rx_stream_start',8)['accepted']
        assert command(c,'stop')['accepted'] and c.state=='draining'
    samples=len(c.host_samples);c.advance(c.time+1e-6)
    assert len(c.host_samples)==samples
    epoch=c.epoch;c.acknowledge_host_abort(epoch,c.time);c.acknowledge_drain(epoch,c.time)
    assert c.state=='reset' and c.host_decoder is None
    return dict(mode=mode,overflow=overflow,sampled=c.adc_sampled,delivered=samples,accounting=c.adc_accounting())

def main():
    codec();rows=[run(m,f) for m in (0,1) for f in (False,True)]
    (P/'evidence/connected-continuous-receiver.json').write_text(json.dumps(dict(status='passed',cases=rows,
        complete_architecture=False,physical_qualification=False,
        limitations=['Finite observation of an unbounded-duration receiver; not an indefinite stability proof.',
        'Stop uses epoch abort and discards partial transport data; graceful drain is not implemented.',
        'Continuous TX and independent host descriptor/control implementation remain open.']),indent=2)+'\n')
    print('Passed continuous RX, bounded codec state, timed stop and overflow abort')
if __name__=='__main__':main()
