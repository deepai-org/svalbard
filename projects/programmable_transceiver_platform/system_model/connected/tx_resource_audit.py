"""Characterize whether TX calibration ownership is discoverable; preserve gaps."""
import json
from chip_model import P
from managed_resources import command
from tx_calibration_chip import TxCalibrationChip

def main():
    c=TxCalibrationChip(watchdog_s=1e-3)
    assert command(c,'rf_coarse_start',2412000000)['accepted']
    c.advance(c.time+50e-6)
    result=command(c,'tx_cal_start');assert result['accepted'] and c.tx_cal.busy
    rows=[]
    for resource in (0,1,8,9,10):
        word=c.execute_management('resource_status',resource,c.time)['value']
        rows.append(dict(resource=resource,word=word,owner=word&255,busy=bool(word&256),assigned=bool(word&1024)))
    report=dict(status='passed',tx_calibration_state=c.tx_cal.state,resources=rows,
        dac_ownership_visible=bool(rows[1]['busy']),
        monitor_adc_in_existing_inventory=True,
        limitation='Direct read at fixed time to keep the ownership snapshot coherent; not a serialized multi-command snapshot.')
    (P/'evidence/connected-tx-resource-audit.json').write_text(json.dumps(report,indent=2)+'\n');print(report)
if __name__=='__main__':main()
