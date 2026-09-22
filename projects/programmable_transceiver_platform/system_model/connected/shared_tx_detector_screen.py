"""Real ADC reference loading and resource visibility during TX calibration."""
import json
from chip_model import P
from managed_resources import command
from shared_tx_detector import SharedAdcLoadedTxChip

def main():
    c=SharedAdcLoadedTxChip(watchdog_s=1e-3,adc_latency_s=50e-9,tx_relative_gain=True)
    assert command(c,'rf_coarse_start',2412000000)['accepted'];c.advance(c.time+50e-6)
    before=c.adc_reference.samples;charge=c.adc_reference.charge
    reply=command(c,'tx_cal_start');assert reply['accepted']
    status=c.execute_management('resource_status',0,c.time)['value'];assert status&256 and status&255==11
    try:c.capture(1,c.time+1e-6)
    except ValueError:pass
    else:raise AssertionError('Shared ADC capture conflict admitted')
    c.advance(c.time+25e-6)
    assert c.tx_cal.state=='ready' and c.tx_adc_samples==9
    assert c.adc_reference.samples-before==9 and c.adc_reference.charge>charge
    assert command(c,'tx_cal_commit',reply['value'])['accepted']
    assert not (c.execute_management('resource_status',0,c.time)['value']&256)
    report=dict(status='passed',shared_adc_samples=c.tx_adc_samples,reference_charge_c=c.adc_reference.charge-charge,
        probe_powers=c.tx_cal.powers,correction=c.tx_cal.candidate,
        limitations=['Experimental loaded fixed-carrier adapter without autonomous phase forcing.',
        'ADC transfer/reference path reused; analog mux buffer loading/settling and readout curvature remain unmodeled.',
        'Detector front end remains resource10; no independent monitor quantizer is used.',
        'Full-chain quality, reference-loss conversion cancellation and shared-resource recovery remain to verify.'])
    (P/'evidence/connected-shared-tx-detector.json').write_text(json.dumps(report,indent=2)+'\n');print(report)

if __name__=='__main__':main()
