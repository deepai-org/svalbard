"""Finite ADC latency/validity, capture completion, cancellation and capacity faults."""
import json,math
from chip_model import P,encode_iq
from playback_memory_lifecycle import PlaybackChip,ready
from sustained_lifecycle import run
from whole_chip_lifecycle import expect_rejection


def local(mode,action):
    period=1/(40e6 if mode==0 else 20e6)
    c=PlaybackChip(adc_latency_s=2.25*period,adc_pipeline_capacity=1 if action=='overflow' else 4,watchdog_s=20e-6)
    for i in range(32):c.write_playback(i,encode_iq(.2+.1j,12 if mode==0 else 8))
    c.select_playback(True);ready(c,mode)
    start=c.time+100e-9;c.schedule(32,start);c.capture(32,start+10e-9)
    first=c.next_adc;c.advance(first)
    assert c.adc_sampled==1 and c.adc_completed==0 and c.capture_bank.count==0 and not c.adc_words
    expect_rejection(lambda:c.capture(1,c.time+1e-6))
    if action=='abort':
        c.set_reference(False,c.time)
        assert c.adc_accounting()['cancelled']==1 and not c.adc_pending
        epoch=c.epoch;c.acknowledge_host_abort(epoch,c.time);c.acknowledge_drain(epoch,c.time)
        before=list(c.adc_words);c.advance(first+3e-6)
        assert c.epoch==epoch+1 and c.adc_words==before and not c.capture_bank.done
    elif action=='overflow':
        c.advance(first+1.5*period)
        assert c.state=='draining' and c.adc_accounting()['cancelled']==1 and not c.adc_pending
        assert not c.adc_words and c.capture_bank.count==0
    else:
        c.advance(first+c.adc_latency-period*.01)
        assert not c.adc_words and c.capture_bank.count==0 and len(c.adc_pending)==3
        c.advance(first+c.adc_latency)
        assert len(c.adc_words)==1 and c.capture_bank.count==1
        c.advance(first+32*period+2e-6);c.host_decoder.finish()
        assert c.adc_words==c.host_samples and len(c.adc_words)==32 and c.capture_bank.done
        assert c.adc_accounting()['completed']==32 and not c.adc_pending
    return dict(mode=mode,action=action,accounting=c.adc_accounting(),state=c.state)


def main():
    for latency,capacity in ((-1,4),(math.nan,4),(0,0)):
        expect_rejection(lambda:PlaybackChip(adc_latency_s=latency,adc_pipeline_capacity=capacity))
    rows=[local(mode,action) for mode in (0,1) for action in ('complete','abort','overflow')]
    sustained=[]
    for mode in (0,1):
        chips=[];period=1/(40e6 if mode==0 else 20e6)
        def factory(**kwargs):
            c=PlaybackChip(adc_latency_s=2*period,adc_pipeline_capacity=4,**kwargs);chips.append(c);return c
        row=run(mode,100,chip_factory=factory,matched_reference=True,host_ppm=-100)
        row['adc_pipeline']=chips[0].adc_accounting();assert row['adc_pipeline']['pending']==0
        sustained.append(row)
    report=dict(status='passed',cases=rows,sustained_cases=sustained,complete_architecture=False,physical_qualification=False,
        contract=['Analog sample and aggregate reference load occur at sampling time; code becomes valid at sample time plus fixed latency.',
        'Previously due conversions complete before coincident sampling; zero-latency conversions complete before coincident host frame service.',
        'Capture RAM and transport observe only valid codes; final burst padding occurs at final conversion completion.',
        'Stop/reset cancels all pending conversions; capacity exhaustion faults instead of silently stretching the sample clock.'],
        limitations=['Fixed latency and finite throughput are mathematical assumptions, not validated SAR conversion timing.',
        'Reference impulses still aggregate conversion activity at the sample edge, not at individual SAR bit decisions.',
        'Internal comparator metastability, validity timeout and conversion-dependent latency remain unmodeled.',
        'DAC update latency, converter clipping diagnostics and full operating envelopes remain open.'])
    (P/'evidence/connected-adc-pipeline-lifecycle.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed six ADC pipeline lifecycle cases and two sustained four-path latency cases')

if __name__=='__main__':main()
