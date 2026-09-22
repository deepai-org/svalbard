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
    report=dict(status='passed',samples_before_abort=samples,detector_epoch_before=old_epoch,
        detector_epoch_after=c.tx_detector.epoch,retained_detector_value=detector,
        retained_network_norm=float(np.linalg.norm(voltage)),reference_charge_c=charge,
        limitations=['One nonzero pending conversion cancelled by reference loss; restart/full-chain quality remain open.',
        'Exact controller boundary test; SPI command timing tested separately.',
        'No physical ADC/mux isolation qualification.'])
    (P/'evidence/connected-shared-tx-cancel.json').write_text(json.dumps(report,indent=2)+'\n');print(report)

if __name__=='__main__':main()
