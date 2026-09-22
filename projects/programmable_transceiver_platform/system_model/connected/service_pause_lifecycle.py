"""H2D clock pauses while production, DAC, ADC, wired and return clocks continue."""
import json
from chip_model import P
from shared_supply_lifecycle import CoupledChip
from sustained_lifecycle import run,TrafficFault

def main():
    rows=[];negative=[]
    for mode in (0,1):
        for ppm in (-100,100):
            for pauses in ({32:16,80:16},{48:64}):
                row=run(mode,ppm,chip_factory=CoupledChip,matched_reference=True,host_ppm=-ppm,
                        visibility_edges=2,service_pauses=pauses,disturbance_sign=1)
                assert len(row['service_pauses'])==len(pauses)
                for pause in row['service_pauses']:
                    assert pause['dac_consumed']>0 and pause['wired_consumed']>0 and pause['adc_captured']>0
                rows.append(row)
        try:
            run(mode,100,chip_factory=CoupledChip,matched_reference=True,host_ppm=-100,service_pauses={48:256})
        except TrafficFault as error:
            assert error.event[1] in ('wired underflow','DAC underflow'),error.event
            negative.append(dict(mode=mode,event=error.event))
        else:raise AssertionError('Long host pause did not expose missing payload')
    report=dict(status='passed',cases=rows,negative_controls=negative,complete_architecture=False,physical_qualification=False,
        limitations=['H2D pauses at frame boundaries only; arbitrary in-frame clock interruption remains untested.',
        'Source production and all chip clocks continue; only host service stops.',
        'Selected pauses and finite runs are not a universal service-curve/queue bound.',
        'External source queues are observed but not modeled as a complete FPGA memory implementation.'])
    (P/'evidence/connected-service-pause-lifecycle.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed eight service-pause cases and two long-pause fault controls')

if __name__=='__main__':main()
