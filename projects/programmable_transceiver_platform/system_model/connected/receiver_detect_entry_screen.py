"""Exercise managed detector lifecycle through its actual public model entry."""
import json
from chip_model import P
from receiver_detect_lifecycle import ReceiverDetectChip
from receiver_detect_resource_adapter import run


def main():
    chips=[]
    def factory(**kwargs):
        c=ReceiverDetectChip(probe_gain_per_v=1.,probe_sensor_v_per_v=.02,
            rf_hz_per_v=1e6,wire_hz_per_v=1e6,**kwargs)
        chips.append(c);return c
    rows=[run(mode,index,chip_class=factory) for mode in (0,1) for index in (5,6)]
    for row,c in zip(rows,chips):
        assert c.probe_supply_charge>0 and c.oscillator_supply_events>0
        assert c.probe_maximum_sensor_error>0 and c.probe_minimum_gain<1
        row.update(charge_c=c.probe_supply_charge,rail_minimum_v=c.supply.minimum,
            oscillator_events=c.oscillator_supply_events,minimum_probe_gain=c.probe_minimum_gain,
            maximum_sensor_error_v=c.probe_maximum_sensor_error)
    report=dict(status='passed',public_entry='receiver_detect_lifecycle.ReceiverDetectChip',cases=rows,
        complete_architecture=False,physical_qualification=False,
        limitations=['The public detector variant is now supply-coupled, but the historical combined top profile still uses an earlier chip class.',
        'Four nominal-load lifecycle cases do not qualify arbitrary precharge, package/load uncertainty or protocol compliance.',
        'Positive1/V driver gain,0.02V/V sensor offset and1MHz/V clock sensitivity are assumed candidate parameters.'])
    (P/'evidence/connected-receiver-detect-entry.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed public detector entry with timed ownership, supply feedback and post-abort rearm')

if __name__=='__main__':main()
