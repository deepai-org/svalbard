"""Low-rail readout clipping must cancel managed calibration and deny commit."""
import json
from chip_model import P
from tx_calibration_chip import TxCalibrationChip
from managed_resources import command

def main():
    c=TxCalibrationChip(tx_detector_options=dict(offset=-.0002),rf_fast_fraction=.30,watchdog_s=1e-3)
    assert command(c,'rf_coarse_start',2412000000)['accepted'];c.advance(c.time+50e-6)
    r=command(c,'tx_cal_start');assert r['accepted']
    c.advance(c.time+25e-6)
    assert c.tx_cal.state=='cancelled' and c.tx_cal.reason=='detector saturated'
    assert not c.tx_cal.valid and c.tx_detector.pending is None and c.tx.held==0
    assert not command(c,'tx_cal_commit',r['value'])['accepted']
    report=dict(status='passed',reason=c.tx_cal.reason,detector_options=c.tx_detector_options,
        limitation='One assumed negative-offset case; does not establish a physical detector transfer bound.')
    (P/'evidence/connected-tx-detector-managed.json').write_text(json.dumps(report,indent=2)+'\n');print(report)
if __name__=='__main__':main()
