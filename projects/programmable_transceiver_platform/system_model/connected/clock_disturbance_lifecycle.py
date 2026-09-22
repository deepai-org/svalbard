"""Active phase/frequency interventions invalidate both pending sample clocks."""
import json,math
from loop_driven_edges import PhasedChip,controls
from chip_model import P,encode,encode_iq
from burst_codec import BurstEncoder

def run(mode,sign,near_edge=False):
    c=PhasedChip(watchdog_s=20e-6);c.configure(mode,0)
    while c.state!='active':c.advance(c.next_reference)
    begin=c.time;rate=250e6 if mode==0 else 312.5e6;start=begin+192/rate
    c.descriptor(3);e=BurstEncoder(2*c.bits,3);words=[]
    for v in (.5,-.25,.125):words+=e.push(encode_iq(v,c.bits))
    words+=e.finish();c.schedule(3,start);c.capture(3,start+10e-9)
    c.schedule_wire(2,start);c.incoming_wire([3,511,97],begin)
    for i,w in enumerate(encode(mode,[17,801],words,0)):c.feed(w,c.epoch,begin+(i+1)/rate)
    c.finish_burst();c.advance(start+12e-9)
    old=c.next_sample;old_adc=c.next_adc
    at=old-1e-12 if near_edge else c.time
    success=c.disturb_clock(at,phase_cycles=sign*.001,frequency_hz=sign*500)
    if near_edge:
        assert not success and c.state=='draining'
        assert math.isinf(c.next_sample) and math.isinf(c.next_adc)
        assert c.tx.consumed==1 and c.tx.discarded==2
        delivered=len(c.host_samples);c.advance(c.time+1e-6)
        assert len(c.host_samples)==delivered
        return dict(mode=mode,near_edge=True,explicit_fault=True)
    assert success and (c.next_sample-old)*sign<0 and (c.next_adc-old_adc)*sign<0
    shifted=c.next_sample
    c.advance(begin+3e-6);c.host_decoder.finish()
    assert c.played[1][0]==shifted and c.tx.consumed==3
    assert c.host_samples==c.adc_words and len(c.adc_words)==3
    assert c.host_wire==[3,511,97] and c.wired_output==[17,801]
    return dict(mode=mode,sign=sign,dac_shift_s=shifted-old,completed=True)

def main():
    controls()
    rows=[run(m,s) for m in (0,1) for s in (-1,1)]+[run(m,1,True) for m in (0,1)]
    report=dict(status='passed',cases=rows,complete_architecture=False,physical_qualification=False,
        limitations=['Discrete externally injected interventions in a linear near-lock model, not stochastic PLL noise.',
        'Edges crossed by a phase jump fault explicitly; nonlinear cycle-slip recovery is not modeled.',
        'Only ADC/DAC deadlines follow loop phase; serializer and host clocks remain prescribed.'])
    (P/'evidence/connected-clock-disturbance-lifecycle.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed four active retiming and two causal-edge fault cases')

if __name__=='__main__':main()
