"""Tile signal through finite ADC latency, reference loading and host transport."""
import json,math
from chip_model import P,decode_iq
from programmable_chip import ProgrammableChip
from managed_resources import command

def run(mode,loaded):
    c=ProgrammableChip(load_capacitance=1e-12 if loaded else 0,adc_latency_s=30e-9,watchdog_s=100e-6)
    c.configure_rx('external_tone',1,5e6,5e6,-.3+.2j,0)
    c.select_diagnostic(True);c.tile.drive(0,.02,0)
    c.configure(mode,0);c.advance(8e-6)
    assert command(c,'resource_count')['value']==8
    assert command(c,'resource_status',0)['value']&255==8
    start=c.time+100e-9;c.capture(32,start)
    snapshot=(c.diagnostic_selected,c.tile.voltage)
    try:c.select_diagnostic(False)
    except ValueError:pass
    else:raise AssertionError('Live ADC rerouting accepted')
    assert snapshot==(c.diagnostic_selected,c.tile.voltage)
    busy=c.execute_management('resource_status',7,c.time)['value'];assert busy&256
    c.advance(start+32/(40e6 if mode==0 else 20e6)+2e-6);c.host_decoder.finish()
    assert c.host_samples==c.adc_words and len(c.host_samples)==32
    assert not c.execute_management('resource_status',0,c.time)['value']&256
    values=[decode_iq(w,c.bits) for w in c.adc_words]
    assert all(z.real>0 and z.imag==0 for z in values)
    if not loaded:
        expected=[.2*(-math.expm1(-t/10e-6)) for t in c.sample_times]
        assert max(abs(z.real-v) for z,v in zip(values,expected))<=1/(1<<c.bits)+1e-14
    else:assert c.adc_reference.charge>0 and c.adc_reference.minimum<1
    before=c.tile.voltage;c.set_reference(False,c.time)
    assert c.tile.voltage==before
    return dict(mode=mode,loaded=loaded,samples=len(values),minimum_span_v=c.adc_reference.minimum,
        first_sample=values[0].real,last_sample=values[-1].real,owner=8,busy_snapshot=busy)

def main():
    rows=[run(m,l) for m in (0,1) for l in (False,True)]
    report=dict(status='passed',cases=rows,complete_architecture=False,physical_qualification=False,
        limitations=['Static held tile input fixture, not physical internal monitor switching.',
        'Diagnostic selection is a direct disarmed API; timed configuration and trigger routing remain open.',
        'I-ADC diagnostic allocation reserves the converter pair; simultaneous RF reception is unavailable.'])
    (P/'evidence/connected-diagnostic-tile.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed diagnostic tile ADC transport, reference loading and ownership')
if __name__=='__main__':main()
