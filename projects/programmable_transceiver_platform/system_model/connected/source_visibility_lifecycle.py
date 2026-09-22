"""Bounded source-to-host visibility lag with unchanged queues and prefill."""
import json
from chip_model import P
from shared_supply_lifecycle import CoupledChip
from sustained_lifecycle import run,TrafficFault

def main():
    rows=[];negative=[]
    for mode in (0,1):
        for ppm in (-100,100):
            for delay in (2,32):
                for phase in (-.49,.49):
                    rows.append(run(mode,ppm,chip_factory=CoupledChip,disturbance_sign=1,
                        matched_reference=True,host_ppm=-ppm,visibility_edges=delay,source_phase_edges=phase))
        try:
            run(mode,100,chip_factory=CoupledChip,matched_reference=True,host_ppm=-100,visibility_edges=256)
        except TrafficFault as error:
            assert error.event[1] in ('wired underflow','DAC underflow'),error.event
            negative.append(dict(mode=mode,visibility_edges=256,observed_fault=error.event))
        else:raise AssertionError('Unavailable payload was silently synthesized or playback stalled')
    report=dict(status='passed',cases=rows,negative_controls=negative,complete_architecture=False,physical_qualification=False,
        limitations=['Visibility delay is fixed per run, expressed in H2D word periods; arbitrary variable CDC delay is not covered.',
        'Source phase perturbs availability at frame snapshots; host pin sampling/metastability is not simulated.',
        'Passing selected endpoints does not prove all intermediate phases or an infinite-time queue bound.',
        'Excessive lag faults with unchanged three-frame prefill; no credit/flow-control mechanism is inferred.'])
    (P/'evidence/connected-source-visibility-lifecycle.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed16 visibility/phase cases and two excessive-lag underflow controls')

if __name__=='__main__':main()
