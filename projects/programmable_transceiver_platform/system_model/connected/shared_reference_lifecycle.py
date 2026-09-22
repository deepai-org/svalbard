"""ADC/DAC aggregate loading on shared or independent assumed reference networks."""
import json,math
from chip_model import P
from causal_reference_lifecycle import Reference
from playback_memory_lifecycle import PlaybackChip
from sustained_lifecycle import run
from whole_chip_lifecycle import expect_rejection


def controls():
    r=Reference();value=.4+.2j;load=2e-12
    assert r.dac_update(0,value,load)==value
    q=load*(.25+.75*(.6/4));span=1-q/r.c
    assert abs(r.voltage-span)<1e-15
    # Coincident ADC sees DAC's load impulse; held DAC used the pre-impulse span.
    assert abs(r.sample(0,.1)-.1/span)<1e-15
    before=r.voltage
    expected=1+(before-1)*math.exp(-25e-9/(r.r*r.c))
    out=r.dac_update(25e-9,-value,load)
    assert abs(out+value*expected)<1e-15 and r.dac_updates==2 and r.samples==1
    a=Reference();b=Reference()
    a.dac_update(0,.5,load);b.dac_update(0,.5,load)
    a.advance(100e-9)
    for i in range(1,101):b.advance(i*1e-9)
    assert abs(a.voltage-b.voltage)<1e-14
    ideal=Reference(load_capacitance=0)
    for i in range(20):
        assert ideal.dac_update(i*25e-9,value,0)==value
        assert ideal.sample(i*25e-9,value)==value
    bad=Reference(resistance=1e9)
    for i in range(100):
        if bad.voltage<=.1:break
        bad.dac_update(i*1e-9,1 if i%2 else -1,90e-12)
    assert bad.voltage<=.1
    expect_rejection(lambda:bad.dac_update(bad.time,0,90e-12))
    expect_rejection(lambda:bad.sample(bad.time,0))
    expect_rejection(lambda:PlaybackChip(dac_reference_load_capacitance=100e-12))
    return dict(collapse_after_updates=bad.dac_updates,collapsed_span_v=bad.voltage)


def main():
    checks=controls();rows=[]
    for mode in (0,1):
        period=1/(40e6 if mode==0 else 20e6)
        for topology in ('disabled','zero_load','shared','separate'):
            chips=[]
            def factory(**kwargs):
                options={} if topology=='disabled' else dict(dac_reference_load_capacitance=0 if topology=='zero_load' else 2e-12,
                    shared_dac_reference=topology!='separate')
                c=PlaybackChip(load_capacitance=0 if topology in ('disabled','zero_load') else 1e-12,
                    dac_latency_s=1.5*period,adc_latency_s=2*period,**options,**kwargs)
                chips.append(c);return c
            row=run(mode,100,chip_factory=factory,matched_reference=True,host_ppm=-100)
            c=chips[0];c.dac_accounting();c.adc_accounting()
            if topology!='disabled':assert c.dac_reference.dac_updates==c.tx.consumed
            row['reference_topology']=topology;rows.append(row)
        cases=rows[-4:]
        assert cases[0]['adc_sha256']==cases[1]['adc_sha256']
        assert len({r['adc_sha256'] for r in cases[1:]})==3
    report=dict(status='passed',controls=checks,cases=rows,complete_architecture=False,physical_qualification=False,
        limitations=['Shared versus separate references are architecture sensitivity choices; neither is physically qualified.',
        'DAC aggregate impulse uses clock activity plus code-transition magnitude; no transistor switching or glitch waveform is claimed.',
        'DAC output uses pre-impulse reference span; a coincident ADC sample sees the post-DAC impulse by the declared event ordering.',
        'Reference span <=0.1V rejects further conversions as outside model range, not implemented hardware undervoltage telemetry.',
        'Electrical source/sink asymmetry, package paths, ADC bit-trial loading and reference noise remain open.'])
    (P/'evidence/connected-shared-reference-lifecycle.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed eight sustained shared/separate reference cases and causal, zero-load and collapse controls')

if __name__=='__main__':main()
