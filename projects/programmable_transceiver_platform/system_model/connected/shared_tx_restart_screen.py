"""Cancel real shared-ADC capture without erasing detector or network charge."""
import json
import numpy as np
from chip_model import P
from managed_resources import command
from shared_tx_detector import SharedAdcLoadedTxChip

def main():
    c=SharedAdcLoadedTxChip(watchdog_s=1e-3,adc_latency_s=100e-9,tx_relative_gain=True)
    assert command(c,'rf_coarse_start',2412000000)['accepted'];c.advance(c.time+50e-6)
    reply=command(c,'tx_cal_start');assert reply['accepted']
    # Advance exact controller events until a nonzero probe has been sampled.
    while c.tx_adc_samples<2 or c.tx_detector.pending is None:
        assert c.tx_cal.next_event is not None
        c.advance(c.tx_cal.next_event)
    assert c.tx_cal.state=='convert' and c.tx_detector.pending is not None
    old_pending=c.tx_detector.pending;voltage=c.loaded_tx.network.voltage.copy()
    detector=c.tx_detector.value;samples=c.tx_adc_samples;charge=c.adc_reference.charge
    old_epoch=c.tx_detector.epoch;old_generation=c.tx_cal.generation
    c.set_reference(False,c.time)
    assert c.tx_detector.pending is None and c.tx_detector.epoch>old_epoch
    assert c.tx_cal.state=='cancelled' and not c.tx_cal.valid
    assert np.array_equal(voltage,c.loaded_tx.network.voltage) and c.tx_detector.value==detector
    assert not c.execute_management('resource_status',0,c.time)['value']&256
    c.advance(old_pending[0]+1e-6)
    assert c.tx_adc_samples==samples and c.adc_reference.charge==charge
    try:c.tx_detector.read()
    except ValueError:pass
    else:raise AssertionError('Cancelled conversion returned a result')
    assert not command(c,'tx_cal_commit',old_generation)['accepted']
    c.set_reference(True,c.time)
    assert not c.tx_cal.valid
    assert command(c,'rf_coarse_start',2412000000)['accepted']
    c.advance(c.time+50e-6)
    assert c.coarse.qualified
    conversions=c.tx_adc_samples
    restarted=command(c,'tx_cal_start');assert restarted['accepted']
    assert restarted['value']>old_generation
    c.advance(c.time+25e-6)
    assert c.tx_cal.state=='ready' and c.tx_adc_samples-conversions==9
    assert not command(c,'tx_cal_commit',old_generation)['accepted']
    assert command(c,'tx_cal_commit',restarted['value'])['accepted']
    assert c.tx_cal.valid and c.tx_detector.pending is None
    assert not c.execute_management('resource_status',0,c.time)['value']&256
    report=dict(status='passed',cancelled_generation=old_generation,
        recovered_generation=c.tx_cal.generation,new_shared_adc_samples=c.tx_adc_samples-conversions,
        recovered_powers=c.tx_cal.powers,detector_epoch=c.tx_detector.epoch,
        limitations=['Quiet calibration restart after reference loss, not active traffic recovery.',
        'Non-phase loaded shared-ADC candidate; phase-aware full-chain quality remains separate.',
        'Physical mux/loading and power qualification remain open.'])
    (P/'evidence/connected-shared-tx-restart.json').write_text(json.dumps(report,indent=2)+'\n');print(report)

if __name__=='__main__':main()
