"""Autonomous oscillator drives the existing bit/channel serializer."""
import json
from pathlib import Path
from autonomous_pll import AutonomousPLL
from autonomous_pll_screen import settle
from pll_serializer import PLLSerializer
from wired_blocks import WiredChannel


def run(rate,sign):
    p=AutonomousPLL(divider=rate/40e6,free_hz=rate*(1+sign*.04))
    settle(p,5e-6);assert p.locked
    s=PLLSerializer(WiredChannel(rate),p.time,p)
    words=[17,801,0,1023,511,7]*3;out=[];periods=[]
    start=p.time;phase=p.output_phase_cycles
    for index,word in enumerate(words):
        deadline=p.edge_time(phase+10*index)
        if index:periods.append(deadline-start)
        start=deadline;s.start(word,deadline,1/rate)
        disturbed=False
        while s.active:
            if index==3 and s.bit==4 and s.stage=='sample' and not disturbed:
                intervention=(p.time+s.deadline)/2
                old=s.deadline
                p.disturb(intervention,frequency_hz=sign*10e6)
                s.retime();assert (s.deadline-old)*sign<0
                disturbed=True
            value=s.step()
            if value is not None:out.append(value)
    assert out==words and s.channel.errors==0
    assert max(periods)-min(periods)>1e-12
    assert s.accounting()==dict(started=len(words),completed=len(words),aborted=0,pending=0)
    return dict(rate_hz=rate,disturbance_sign=sign,words=len(words),
                minimum_word_period_s=min(periods),maximum_word_period_s=max(periods))


def bounded_controls(rate):
    import math,copy
    from autonomous_pll import SupplyTrajectory
    p=AutonomousPLL(divider=rate/40e6,free_hz=rate,phase_cycles=0.)
    p.set_reference(False,0.)
    sensitivity=1e6;voltage=-.2;frequency=rate+sensitivity*voltage
    step=.1/frequency
    p.set_supply_trajectory(SupplyTrajectory((0.,step),(voltage,voltage)),sensitivity)
    s=PLLSerializer(WiredChannel(rate),0.,p,bounded=True)
    words=[17,801,0,1023,511,7];out=[];pending=0;events=[]
    for index,word in enumerate(words):
        start=10*index/frequency
        if start>p.time:
            p.set_supply_trajectory(SupplyTrajectory((p.time,start),(voltage,voltage)),sensitivity)
            p.advance(start)
        p.set_supply_trajectory(SupplyTrajectory((p.time,p.time+step),(voltage,voltage)),sensitivity)
        s.start(word,p.time,1/rate)
        while s.active:
            if s.pending_phase:
                before=(s.bit,s.stage,s.result,s.time,p.time,p.output_phase_cycles)
                try:s.step()
                except ValueError:pass
                else:raise AssertionError('Pending edge executed without rail history')
                assert before==(s.bit,s.stage,s.result,s.time,p.time,p.output_phase_cycles)
                end=p.supply_trajectory.times[-1]
                s.advance(end);p.advance(end)
                p.set_supply_trajectory(SupplyTrajectory((end,end+step),(voltage,voltage)),sensitivity)
                s.retime();pending+=1
                continue
            events.append(s.deadline)
            value=s.step()
            if value is not None:out.append(value)
    assert out==words and s.channel.errors==0 and pending>100
    expected=[(10*i+j*.5)/frequency for i in range(len(words)) for j in range(20)]
    error=max(abs(a-b) for a,b in zip(events,expected))
    assert len(events)==len(expected) and error<1e-17
    assert s.accounting()==dict(started=6,completed=6,aborted=0,pending=0)
    # An edge exactly at the horizon is resolvable without advancing the clock.
    q=AutonomousPLL(free_hz=rate,phase_cycles=0.);q.set_reference(False,0.)
    q.set_supply_trajectory(SupplyTrajectory((0.,1/rate),(0.,0.)),0.)
    target=copy.copy(q);target.advance(1/rate)
    assert q.edge_time_before(target.output_phase_cycles,1/rate)==1/rate and q.time==0
    assert q.edge_time_before(target.output_phase_cycles+1,1/rate) is None
    exact=PLLSerializer(WiredChannel(rate),0.,q,bounded=True)
    exact.start(17,0.,1/rate);exact.step();exact.step()
    assert abs(exact.deadline-1/rate)<1e-20
    exact.step();assert exact.bit==1 and exact.stage=='sample' and exact.pending_phase
    exact.retime();assert exact.bit==1 and exact.pending_phase
    # Abort clears a deferred edge so extending the rail history cannot revive it.
    p.set_supply_trajectory(SupplyTrajectory((p.time,p.time+step),(voltage,voltage)),sensitivity)
    s.start(1023,p.time,1/rate);s.step();assert s.pending_phase
    s.abort(p.time);s.retime()
    assert not s.pending_phase and math.isinf(s.deadline) and s.accounting()['aborted']==1
    return dict(rate_hz=rate,words=len(words),deferred_forecasts=pending,
        maximum_edge_error_s=error,exact_horizon_once=True,abort_cancels_pending=True)


if __name__=='__main__':
    report=dict(status='passed',complete_architecture=False,physical_qualification=False,bounded_cases=[bounded_controls(r) for r in (1.25e9,2.5e9)],cases=[run(r,s) for r in (1.25e9,2.5e9) for s in (-1,1)],
                limitations=['Connected host scheduling, lock gating and shared supply callback are not yet attached.',
                             'Ideal average divider and assumed VCO parameters; no phase-noise qualification.'])
    (Path(__file__).resolve().parents[2]/'evidence/connected-pll-serializer.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
