"""Read current behavior after committed calibration and a direct carrier retarget."""
import json
from chip_model import P
from tx_calibration_chip import TxCalibrationChip
from managed_resources import command

def main():
    c=TxCalibrationChip(watchdog_s=1e-3)
    assert command(c,'rf_coarse_start',2412000000)['accepted']
    c.advance(c.time+50e-6)
    r=command(c,'tx_cal_start');assert r['accepted']
    c.advance(c.time+25e-6)
    assert command(c,'tx_cal_commit',r['value'])['accepted']
    try:c.configure_rf_carrier(2413000000)
    except ValueError:pass
    else:raise AssertionError('Unqualified target accepted')
    assert c.tx_cal.valid
    before=c.tx_cal.valid
    c.configure_rf_carrier(2412000000)
    after=c.tx_cal.valid;locked=c.rf_pll.locked
    c.advance(c.time+30e-6)
    admitted=True
    try:c._require_tx_calibrated()
    except ValueError:admitted=False
    report=dict(status='passed',before_valid=before,after_retarget_valid=after,
        lock_immediately_after=locked,lock_after_wait=c.rf_pll.locked,tx_admitted_without_recalibration=admitted,
        scope='Same-frequency direct retarget resets divider phase/lock state; no calibration provenance refresh requested.')
    (P/'evidence/connected-tx-retune-validity-audit.json').write_text(json.dumps(report,indent=2)+'\n');print(report)
if __name__=='__main__':main()
