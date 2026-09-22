"""Full accepted RF carrier grid: actual pulse-loop acquisition and lock continuity.

This is a characterization screen. Unsupported points remain explicit failures
of the candidate operating envelope, not failures of the measurement script.
"""
import json,math
from chip_model import P
from fractional_rf_chip import ShapedRFClock

def measure(target,bandwidth_hz=350e3,fast_fraction=.5):
    p=ShapedRFClock(reference_hz=40e6,divider=60,free_hz=2.4e9*.96,bandwidth_hz=bandwidth_hz,fast_fraction=fast_fraction)
    p.retarget(0,target)
    first=None;losses=0;tail=[];fault=None
    for index in range(1,2401):
        time=index/40e6
        try:
            p.advance(time);was=p.locked;locked=p.observe_lock()
        except ValueError as error:
            fault=str(error);break
        if locked and first is None:first=time
        if was and not locked:losses+=1
        if index>=1600:tail.append((time,p.output_phase_cycles,p.error,p.frequency_hz,locked))
    stable=fault is None and first is not None and first<=40e-6 and losses==0 and bool(tail) and all(x[4] for x in tail)
    return dict(fast_fraction=fast_fraction,target_hz=target,bandwidth_hz=bandwidth_hz,acquired_by_40us=first is not None and first<=40e-6,
        first_lock_s=first,lock_losses_after_first=losses,final_locked=p.locked,
        sustained_qualification=stable,fault=fault,
        max_tail_phase_error_cycles=max((abs(x[2]) for x in tail),default=None),
        max_tail_frequency_error_hz=max((abs(x[3]/p.divider-p.reference_hz) for x in tail),default=None),
        divider_pattern_denominator=p.sequence.ratio.denominator,
        minimum_compliance_margin_v=p.metrics()['minimum_compliance_margin_v'])

def main(bandwidth_hz=350e3,output='connected-fractional-grid.json',fast_fraction=.5):
    rows=[]
    for mhz in range(2300,2501):
        rows.append(measure(mhz*1000000,bandwidth_hz,fast_fraction))
        if mhz%20==0:print('Measured through',mhz,'MHz',flush=True)
    failures=[r['target_hz'] for r in rows if not r['sustained_qualification']]
    report=dict(status='characterized',cases=rows,
        summary=dict(total=len(rows),sustained=len(rows)-len(failures),unqualified_targets_hz=failures),
        assumptions=dict(fast_fraction=fast_fraction,bandwidth_hz=bandwidth_hz,free_hz=2.4e9*.96,initial_phase_cycles=.2,
            reference_hz=40e6,acquisition_deadline_s=40e-6,observation_end_s=60e-6),
        complete_architecture=False,physical_qualification=False,
        limitations=['One nominal startup state per target; no noise, rail forcing or full-chip traffic.',
        'Reference-edge lock observations do not measure intra-reference phase noise or RF waveform error.',
        'Candidate must keep qualification after first acquisition; a later reacquisition does not undo a chip fault.'])
    (P/'evidence'/output).write_text(json.dumps(report,indent=2)+'\n')
    assert len(rows)==201 and all(r['fault'] is None for r in rows)
    print(report['summary'],flush=True)
if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--bandwidth-hz',type=float,default=350e3)
    parser.add_argument('--fast-fraction',type=float,default=.5)
    parser.add_argument('--output',default='connected-fractional-grid.json')
    args=parser.parse_args();main(args.bandwidth_hz,args.output,args.fast_fraction)
