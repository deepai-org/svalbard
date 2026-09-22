"""A rejected dual-stream command cannot leave the other engine scheduled."""
import json,math
from chip_model import P
from programmable_chip import ProgrammableChip
from managed_resources import command

def run(mode,conflict):
    c=ProgrammableChip(watchdog_s=100e-6)
    if conflict=='past_rx':c.local_rx_offset_s=-10e-6
    c.configure(mode,0);c.advance(8e-6)
    if conflict=='rx_busy':c.start_rx_stream(c.time+50e-6)
    if conflict=='tx_busy':c.start_tx_stream(c.time+50e-6)
    snapshot=(c.remaining,c.adc_left,c.next_sample,c.next_adc,c.decoder,
        getattr(c,'adc_encoder',None),getattr(c,'host_decoder',None))
    result=command(c,'stream_start',(32<<2)|3)
    assert not result['accepted']
    after=(c.remaining,c.adc_left,c.next_sample,c.next_adc,c.decoder,
        getattr(c,'adc_encoder',None),getattr(c,'host_decoder',None))
    assert snapshot==after
    return dict(mode=mode,conflict=conflict,reason=result['reason'],atomic_rejection=True)

def main():
    rows=[run(m,c) for m in (0,1) for c in ('rx_busy','tx_busy','past_rx')]
    (P/'evidence/connected-atomic-stream.json').write_text(json.dumps(dict(status='passed',cases=rows,
        complete_architecture=False,physical_qualification=False,
        limitations=['Scheduling currently assigns fresh objects; future scheduler changes must preserve staging isolation.',
        'No external or comparator trigger semantics are implied.']),indent=2)+'\n')
    print('Passed six atomic dual-stream rejection cases')
if __name__=='__main__':main()
