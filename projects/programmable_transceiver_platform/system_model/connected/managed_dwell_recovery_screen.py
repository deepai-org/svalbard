"""Serialized dwell, timeout cleanup and fresh calibration with real RF startup."""
import json
from chip_model import P
from managed_resources import command
from programmable_calibration_dwell import ProgrammableDwellChip,calibrate_until_complete

def main():
    c=ProgrammableDwellChip(adc_latency_s=30e-9,readout_tau_s=2e-6,
        tx_relative_gain=True,watchdog_s=1e-3)
    reply=command(c,'tx_cal_dwell',400)
    assert reply['accepted'] and reply['value']==400
    assert not command(c,'tx_cal_dwell',79)['accepted']
    assert c.tx_cal_dwell_ticks==400
    assert command(c,'rf_coarse_start',2412000000)['accepted']
    c.advance(c.time+50e-6)
    print('RF startup complete',c.time,flush=True)
    try:calibrate_until_complete(c,timeout_s=25e-6)
    except TimeoutError:pass
    else:raise AssertionError('Short deadline did not time out')
    assert c.tx_cal.state=='cancelled' and not c.tx_cal.valid and c.tx_detector.pending is None
    assert not c.execute_management('resource_status',0,c.time)['value']&256
    cancelled=dict(time_s=c.time,generation=c.tx_cal.generation,detector=c.tx_detector.value,
        readout=c.tx_detector.readout_value,samples=c.tx_adc_samples)
    assert cancelled['samples']>0 and cancelled['readout']>0
    print('Timeout released ADC',cancelled,flush=True)
    before=c.tx_adc_samples
    result=calibrate_until_complete(c,timeout_s=250e-6)
    assert result['accepted'] and c.tx_cal.valid and c.tx_adc_samples-before==9
    assert c.tx_cal.generation>cancelled['generation']
    assert not c.execute_management('resource_status',0,c.time)['value']&256
    report=dict(status='passed',timeout_state=cancelled,new_generation=c.tx_cal.generation,
        fresh_samples=c.tx_adc_samples-before,correction=c.tx_cal.candidate,
        phase_substeps=c.phase_steps,final_time_s=c.time,
        limitations=['Quiet buffered shared-ADC calibration and timeout restart, no host payload traffic.',
            'Assumed 2us readout tau and 10us dwell; not physical settling qualification or waveform accuracy.'])
    (P/'evidence/connected-managed-dwell-recovery.json').write_text(json.dumps(report,indent=2)+'\n');print(report,flush=True)

if __name__=='__main__':main()
