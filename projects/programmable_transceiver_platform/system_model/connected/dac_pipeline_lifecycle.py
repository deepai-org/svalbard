"""DAC consumption versus analog update, finite pipeline and cancellation."""
import json,math
from chip_model import P,encode_iq
from playback_memory_lifecycle import PlaybackChip,ready
from sustained_lifecycle import run
from whole_chip_lifecycle import expect_rejection


def local(mode,action):
    period=1/(40e6 if mode==0 else 20e6)
    c=PlaybackChip(dac_latency_s=2.25*period,dac_pipeline_capacity=1 if action=='overflow' else 4,watchdog_s=20e-6)
    for i in range(32):c.write_playback(i,encode_iq(.25,12 if mode==0 else 8))
    c.select_playback(True);ready(c,mode)
    start=c.time+100e-9;c.schedule(32,start);c.advance(c.next_sample);first=c.time
    assert c.tx.consumed==1 and c.tx.held==0 and not c.played and c.tx.filtered==0
    expect_rejection(lambda:c.schedule(1,c.time+1e-6))
    if action=='abort':
        c.set_reference(False,c.time)
        assert c.dac_accounting()['cancelled']==1
        epoch=c.epoch;c.acknowledge_host_abort(epoch,c.time);c.acknowledge_drain(epoch,c.time)
        c.advance(first+3e-6)
        assert c.epoch==epoch+1 and not c.played and c.tx.held==0
    elif action=='overflow':
        c.advance(first+1.5*period)
        assert c.state=='draining' and c.dac_accounting()['cancelled']==1 and not c.played
    else:
        update=first+c.dac_latency
        # Evaluate analog gain at update time, not digital consumption time.
        c.tx.dac_gain=lambda t:.8 if t>=update else 1.
        c.advance(update-.01*period)
        assert len(c.dac_pending)==3 and c.tx.held==0 and c.tx.filtered==0
        c.advance(update)
        assert c.tx.held==.2 and c.played==[(update,.2)] and c.tx.filtered==0
        c.advance(update+10e-9)
        assert abs(c.tx.filtered-.2*(1-math.exp(-c.tx.pole*10e-9)))<1e-13
        c.advance(first+35*period)
        assert c.dac_accounting()['updated']==32 and not c.dac_pending
    return dict(mode=mode,action=action,accounting=c.dac_accounting())


def main():
    for latency,capacity in ((-1,4),(math.nan,4),(0,0)):
        expect_rejection(lambda:PlaybackChip(dac_latency_s=latency,dac_pipeline_capacity=capacity))
    rows=[local(m,a) for m in (0,1) for a in ('complete','abort','overflow')];sustained=[]
    for mode in (0,1):
        chips=[];period=1/(40e6 if mode==0 else 20e6)
        def factory(**kwargs):
            c=PlaybackChip(dac_latency_s=1.5*period,adc_latency_s=2*period,**kwargs);chips.append(c);return c
        row=run(mode,100,chip_factory=factory,matched_reference=True,host_ppm=-100)
        row['dac_pipeline']=chips[0].dac_accounting();row['adc_pipeline']=chips[0].adc_accounting()
        assert row['dac_pipeline']['pending']==row['adc_pipeline']['pending']==0
        sustained.append(row)
    report=dict(status='passed',cases=rows,sustained_cases=sustained,complete_architecture=False,physical_qualification=False,
        contract=['Digital sample consumption schedules analog update at fixed latency; held DAC output changes only on completion.',
        'DAC supply gain is evaluated at analog update; existing continuous TX/RX state is propagated first.',
        'Due updates precede coincident consumption and ADC sampling; finite capacity exhaustion faults.',
        'Reset mutes held output and cancels pending updates while retaining continuous filter decay.'],
        limitations=['Fixed latency is an assumed interface contract, not transistor DAC settling or glitch qualification.',
        'Completion does not mean analog filters have settled; their state continues independently.',
        'Variable delay, conversion-code-dependent glitches and DAC reference charge loading remain open.'])
    (P/'evidence/connected-dac-pipeline-lifecycle.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed six DAC pipeline cases and two sustained four-path cases with both converter delays')

if __name__=='__main__':main()
