"""RF TX calibration admission must not prohibit independent RF RX mode setup."""
import json
from chip_model import P
from managed_resources import command
from tx_calibration_chip import TxCalibrationChip

def main():
    rows=[]
    for mode in (0,1):
        c=TxCalibrationChip(watchdog_s=1e-3)
        assert command(c,'rf_coarse_start',2412000000)['accepted']
        c.advance(c.time+50e-6)
        assert command(c,'configure_mode',mode)['accepted']
        c.advance(c.time+20e-6)
        assert not c.tx_cal.valid
        before=(c.tx.accepted,len(c.tx.queue),c.decoder)
        for action in (lambda:c.descriptor(4),lambda:c.schedule(4,c.time+1e-6),lambda:c.tx.accept(.1)):
            try:action()
            except ValueError:pass
            else:raise AssertionError('Uncalibrated RF TX admitted')
        assert before==(c.tx.accepted,len(c.tx.queue),c.decoder)
        c.capture(8,c.time+1e-6)
        c.advance(c.time+5e-6)
        assert len(c.adc_words)==8
        rows.append(dict(mode=mode,uncalibrated_rx_samples=len(c.adc_words),rejected_tx_paths=3))
    (P/'evidence/connected-tx-admission.json').write_text(json.dumps(dict(status='passed',cases=rows,
        limitations=['RF RX independently exercised; wired full traffic remains separate regression.',
        'TX admission checks sequencing validity, not independently verified calibration accuracy.']),indent=2)+'\n')
    print(rows)
if __name__=='__main__':main()
