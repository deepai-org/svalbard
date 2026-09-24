"""Actual acquisition and shared-ADC calibration with driver-to-PLL feedback."""
import json,time
from chip_model import P
from managed_resources import command
from managed_driver_feedback import ManagedDriverFeedbackChip
from programmable_calibration_dwell import calibrate_until_complete

def main(chip_class=ManagedDriverFeedbackChip, *,
         report_name='connected-managed-feedback-calibration.json',
         coupling_limitation='Driver rail pulls RF PLL; reference load is real but direct driver-rail/reference-voltage coupling absent.'):
    start=time.monotonic()
    c=chip_class(adc_latency_s=30e-9,tx_relative_gain=True,watchdog_s=1e-3)
    assert command(c,'rf_coarse_start',2412000000)['accepted']
    print('Coarse search command accepted',c.time,flush=True)
    c.advance(c.time+50e-6)
    assert c.coarse.qualified
    print('Coarse search qualified',c.time,flush=True)
    before=c.tx_adc_samples;charge=c.adc_reference.charge
    result=calibrate_until_complete(c,timeout_s=150e-6)
    assert result['accepted'] and c.tx_cal.valid and c.tx_adc_samples-before==9
    assert c.adc_reference.charge>charge
    assert c.loaded_tx.driver.detector is c.tx_detector is c.tx_cal.detector
    assert not c.execute_management('resource_status',0,c.time)['value']&256
    report=dict(status='passed',elapsed_s=time.monotonic()-start,final_time_s=c.time,
        feedback_steps=c.driver_feedback_steps,driver_rail_v=c.loaded_tx.driver.rail_v,
        shared_adc_samples=c.tx_adc_samples-before,reference_charge_c=c.adc_reference.charge-charge,
        correction=c.tx_cal.candidate,powers=c.tx_cal.powers,
        limitations=['Managed autonomous acquisition and quiet shared-ADC calibration, no payload quality.',
            coupling_limitation,
            'Assumed driver/readout/sensitivity parameters and finite coupling-step error remain unqualified.'])
    (P/'evidence'/report_name).write_text(json.dumps(report,indent=2)+'\n')
    print(report,flush=True)

if __name__=='__main__':main()
