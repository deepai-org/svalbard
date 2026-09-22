"""Serialized management ownership and commit on experimental chip."""
import json
from chip_model import P
from managed_resources import command
from tx_calibration_chip import TxCalibrationChip

def main():
    c=TxCalibrationChip(watchdog_s=1e-3)
    assert not command(c,'tx_cal_start')['accepted']
    assert command(c,'rf_coarse_start',2412000000)['accepted']
    c.advance(c.time+50e-6)
    assert c.coarse.qualified and c.rf_pll.locked
    r=command(c,'tx_cal_start');assert r['accepted'],r
    generation=r['value']
    assert not command(c,'configure_mode',0)['accepted']
    assert not command(c,'cal_start',48)['accepted']
    c.advance(c.time+25e-6)
    assert c.tx_cal.state=='ready' and not c.tx_cal.valid
    assert not command(c,'tx_cal_commit',generation-1)['accepted']
    assert command(c,'tx_cal_commit',generation)['accepted'] and c.tx_cal.valid
    # A new start invalidates previous calibration; reference loss cancels it.
    assert command(c,'tx_cal_start')['accepted']
    c.advance(c.time+2.05e-6)
    c.set_reference(False,c.time)
    c.advance(c.time+1e-6)
    assert c.tx_cal.state=='cancelled' and not c.tx_cal.valid and c.tx_detector.pending is None
    mode_widths=[]
    for mode,bits in ((0,12),(1,8)):
        a=TxCalibrationChip(watchdog_s=1e-3)
        assert command(a,'rf_coarse_start',2412000000)['accepted']
        a.advance(a.time+50e-6)
        start=command(a,'tx_cal_start');assert start['accepted']
        a.advance(a.time+25e-6)
        assert command(a,'tx_cal_commit',start['value'])['accepted']
        result=command(a,'configure_mode',mode);assert result['accepted'],result
        assert a.tx.sample_correction.bits==bits
        mode_widths.append(bits)
    report=dict(mode_widths=mode_widths,status='passed',generation=generation,final_state=c.tx_cal.state,
        limitations=['Experimental independent power ADC; not the final shared monitor resource.',
        'Both mode widths checked at activation; full streaming and residual verification pending.',
        'RF clock qualification is enforced; independent monitor ADC and output isolation remain assumptions.',
        'No physical RF output isolation or full-chip output-stage coupling qualification.'])
    (P/'evidence/connected-tx-calibration-chip.json').write_text(json.dumps(report,indent=2)+'\n');print(report)
if __name__=='__main__':main()
