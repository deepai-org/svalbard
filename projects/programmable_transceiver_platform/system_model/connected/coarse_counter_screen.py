"""Finite counter wrap, all endpoint freshness combinations and timed cancellation."""
import json,math
from chip_model import P
from coarse_counter import CoarseCounter
from coarse_startup_lifecycle import CoarseStartupChip
from managed_resources import command

def main():
    checks=0
    for ages in ((0,0),(0,1),(1,0),(1,1)):
        counter=CoarseCounter(2e-6,ages=ages)
        for first in (0,4094,4095,4096,8191):
            for increment in (287,312,353,375):
                start=counter.snapshot(first,0);end=counter.snapshot(first+increment,1)
                delta=counter.delta(start,end)
                assert 0<=start<4096 and 0<=end<4096
                assert abs(delta-increment)<=1
                checks+=1
    try:CoarseCounter(30e-6)
    except ValueError:pass
    else:raise AssertionError('Aliased multiwrap measurement accepted')
    try:CoarseStartupChip(rf_free_offset=.2)
    except ValueError:pass
    else:raise AssertionError('Counter frequency envelope ignored')
    rows=[]
    for ages in ((0,0),(0,1),(1,0),(1,1)):
        c=CoarseStartupChip(rf_free_offset=-.08,coarse_counter_ages=ages,control_hz=20e6 if ages==(1,1) else 40e6,watchdog_s=1e-3)
        assert c.coarse.counter.latency==2*c.control_period
        # Start after the free-running count has crossed its first modulus.
        c.advance(40.75e-6)
        assert command(c,'rf_coarse_start',2500000000)['accepted'];c.advance(c.time+30e-6)
        assert c.coarse.qualified
        assert any(r['modular_wrap'] for r in c.coarse.history)
        for r in c.coarse.history:
            truth=c.rf_pll.base_free+c.rf_pll.bank_hz[r['code']]
            assert abs(r['frequency_hz']-truth)<=r['error_bound_hz']+1e-5
        assert command(c,'configure_mode',0)['accepted'];c.advance(c.time+40e-6)
        assert c.state=='active' and c.rf_pll.locked
        rows.append(dict(ages=ages,bank=c.rf_pll.bank_code,observations=c.coarse.history))
    # A cancellation between capture and publication discards the pending value.
    c=CoarseStartupChip(watchdog_s=1e-3)
    c.execute_management('rf_coarse_start',2437000000,0.)
    c.advance(c.coarse.next_event)
    assert c.coarse.state=='start_wait' and c.coarse.snapshot_pending is not None
    c.execute_management('rf_coarse_abort',0,c.time)
    c.advance(c.time+1e-6)
    assert c.coarse.snapshot_pending is None and c.coarse.state=='cancelled' and not c.coarse.history
    # An inconsistent held snapshot must fail without selecting a new bank.
    bad=CoarseStartupChip(watchdog_s=1e-3)
    bad.execute_management('rf_coarse_start',2437000000,0.)
    while bad.coarse.state!='end_wait':bad.advance(bad.coarse.next_event)
    bad.coarse.snapshot_pending=(bad.coarse.generation,(bad.coarse.begin_count+1000)%4096)
    bad.advance(bad.coarse.next_event)
    assert bad.coarse.state=='failed' and not bad.coarse.qualified
    assert bad.rf_pll.bank_code==8 and not bad.rf_pll.present
    assert bad.coarse.snapshot_pending is None and bad.coarse.next_event is None
    report=dict(status='passed' ,modular_cases=checks,cases=rows,
        pending_snapshot_cancelled=True,inconsistent_snapshot_rejected=True,complete_architecture=False,physical_qualification=False,
        assumptions=['12-bit /16 counter; source frequency bounded by 3GHz.',
        'Coherent held snapshots with two control-clock publication cycles and at most one prescaled-count age.',
        'Frequency/CDC bounds are a model contract requiring transistor/digital implementation validation.'])
    (P/'evidence/connected-coarse-counter.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed finite counter wrap, CDC freshness bounds and pending-snapshot cancellation')
if __name__=='__main__':main()
