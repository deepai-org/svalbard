"""Continuous rail-to-clock response: analytic integral and full-chip switching."""
import json
import math
from autonomous_pll import AutonomousPLL
from autonomous_rf_lifecycle import AutonomousRFChip
from oscillator_supply_lifecycle import OscillatorSupplyChip
from shared_supply_lifecycle import Supply
from sustained_lifecycle import run,TrafficFault
from chip_model import P,encode


def analytic():
    rows=[]
    for divider in (31.25,60.,62.5):
        for sign in (-1,1):
            p=AutonomousPLL(divider=divider,free_hz=40e6*divider,phase_cycles=0.)
            p.set_reference(False,0.)
            rail=Supply();rail.draw(0,1e-12);k=sign*1e8;tau=rail.r*rail.c
            p.set_supply(0,rail.delta,tau,k)
            edge=p.edge_time(20.)
            residual=p.free_hz*edge+k*rail.delta*tau*(-math.expm1(-edge/tau))-20.
            assert abs(residual)<1e-9
            t1=5e-9;t2=50e-9;first=k*rail.delta*tau*(-math.expm1(-t1/tau))
            p.advance(t1);old=p.output_phase_cycles
            rail.draw(t1,1e-12);p.set_supply(t1,rail.delta,tau,k)
            assert p.output_phase_cycles==old
            expected=p.free_hz*t2+first+k*rail.delta*tau*(-math.expm1(-(t2-t1)/tau))
            p.advance(t2);error=abs(p.output_phase_cycles-expected)
            assert error<1e-9
            assert abs(p.rail_frequency(t2)-k*rail.delta*math.exp(-(t2-t1)/tau))<1e-8
            rows.append(dict(divider=divider,sign=sign,phase_integral_error_cycles=error,edge_residual_cycles=abs(residual)))
    return rows


def trajectory_controls():
    import copy
    import numpy as np
    from autonomous_pll import SupplyTrajectory
    from sampled_pll import SampledPLL
    from limited_coupled_driver import LimitedCoupledDriver
    from driver_sensitive_reference import DriverSensitiveReference
    errors=[];edge_errors=[]
    for cls in (AutonomousPLL,SampledPLL):
        for sign in (-1,1):
            times=(0.,7e-9,19e-9,50e-9)
            volts=(0.,-.2,-.08,-.12)
            trajectory=SupplyTrajectory(times,volts)
            p=cls(free_hz=2.4e9,phase_cycles=0.)
            p.set_reference(False,0.);p.set_supply_trajectory(trajectory,sign*1e8)
            phase=p.output_phase_cycles
            edge=p.edge_time(40.)
            def integral(end):
                result=0.
                for a,b in zip(times,times[1:]):
                    stop=min(b,end)
                    if stop>a:result+=(trajectory.voltage(a)+trajectory.voltage(stop))*(stop-a)/2
                return result
            edge_errors.append(abs(p.free_hz*edge+sign*1e8*integral(edge)-40.))
            assert edge_errors[-1]<1e-8 and p.output_phase_cycles==phase
            before=copy.copy(p).__dict__
            for operation in (lambda:p.advance(51e-9),lambda:p.edge_time(1000.)):
                try:operation()
                except ValueError:pass
                else:raise AssertionError('Unknown future supply silently extrapolated')
                assert p.__dict__==before
            split=copy.copy(p)
            p.advance(times[-1])
            for t in np.linspace(0,times[-1],51)[1:]:split.advance(float(t))
            errors.append(abs(p.output_phase_cycles-(p.free_hz*times[-1]+sign*1e8*integral(times[-1]))))
            assert errors[-1]<1e-8 and abs(p.output_phase_cycles-split.output_phase_cycles)<1e-8
    # Actual driver/reference rail trajectory, with interpolation refinement.
    r=DriverSensitiveReference();r.voltage=.8
    d=LimitedCoupledDriver(reference=r)
    d.network.configure(True,False)
    d.advance(100e-9,.3+.1j,rtol=1e-10,atol=1e-13,rail_trace_step_s=.25e-9)
    trace=d.rail_trajectory
    phases=[]
    for stride in (8,4,2,1):
        indices=list(range(0,len(trace.times)-1,stride))+[len(trace.times)-1]
        history=SupplyTrajectory(tuple(trace.times[i] for i in indices),tuple(trace.deltas[i] for i in indices))
        p=SampledPLL(free_hz=2.4e9,phase_cycles=0.);p.set_reference(False,0.)
        p.set_supply_trajectory(history,1e8);p.advance(history.times[-1])
        phases.append(p.output_phase_cycles)
    differences=[abs(v-phases[-1]) for v in phases[:-1]]
    assert differences[2]<differences[1]<differences[0] and differences[2]<1e-4, differences
    return dict(max_phase_integral_error_cycles=max(errors),max_edge_error_cycles=max(edge_errors),
        out_of_horizon_atomic_rejection=True,rail_interpolation_phase_errors_cycles=differences,
        final_rail_v=d.rail_v,full_chip_feedback_closed=False)

def feedback_controls():
    import copy
    import numpy as np
    from sampled_pll import SampledPLL
    from limited_coupled_driver import LimitedCoupledDriver
    from driver_sensitive_reference import DriverSensitiveReference
    from driver_pll_feedback import forecast_trajectory_feedback
    r=DriverSensitiveReference();r.voltage=.8
    from rf_cascade_state import RfCascadeState
    from session import Session
    from buffered_shared_detector import BufferedSharedDetector
    rx=RfCascadeState(Session());rx.set_butterworth(5,9.1574070557e6)
    detector=BufferedSharedDetector(lambda value,time:(value,False))
    driver=LimitedCoupledDriver(reference=r,rx_bank=rx.rx_bank,detector=detector)
    driver.network.configure(True,False)
    clock=SampledPLL(free_hz=2.412e9,phase_cycles=0.)
    clock.set_reference(False,0.)
    result=[]
    for step in (1e-9,.5e-9,.25e-9):
        d,p,metrics=forecast_trajectory_feedback(driver,clock,20e-9,[(.3+.1j,0j)],1e8,step)
        result.append((d,p,metrics))
        assert driver.time==clock.time==0 and driver.reference.voltage==.8
    differences=[abs(p.output_phase_cycles-result[-1][1].output_phase_cycles) for d,p,m in result[:-1]]
    assert differences[1]<differences[0] and differences[1]<1e-4, differences
    first,p,_=forecast_trajectory_feedback(driver,clock,10e-9,[(.3+.1j,0j)],1e8,.25e-9)
    split,sp,_=forecast_trajectory_feedback(first,p,20e-9,[(.3+.1j,0j)],1e8,.25e-9)
    assert abs(sp.output_phase_cycles-result[-1][1].output_phase_cycles)<1e-7
    assert np.max(abs(split.network.voltage-result[-1][0].network.voltage))<1e-7
    assert abs(split.received-result[-1][0].received)<1e-7
    assert abs(split.received)>0 and split.detector.value>0
    assert driver.rx_bank['states']==[0j]*5 and driver.detector.value==0
    # Nonconvergence cannot partially advance the live analog/clock objects.
    try:forecast_trajectory_feedback(driver,clock,20e-9,[(.3+.1j,0j)],1e8,1e-9,max_iterations=2)
    except ValueError:pass
    else:raise AssertionError('Deliberately incomplete iteration unexpectedly converged')
    assert driver.time==clock.time==0 and driver.reference.voltage==.8
    return dict(iterations=[m for d,p,m in result],step_phase_differences_cycles=differences,
        split_phase_error_cycles=abs(sp.output_phase_cycles-result[-1][1].output_phase_cycles),
        nonconvergence_preserves_live_state=True,receive_filter_and_detector_included=True,full_chip_event_scheduler_connected=False)

def traffic(mode,sign):
    chips=[]
    def factory(**kw):
        c=OscillatorSupplyChip(rf_hz_per_v=sign*1e6,wire_hz_per_v=sign*1e6,
            wire_reference_ppm=100,return_charge_per_transition=50e-15,**kw)
        chips.append(c);return c
    row=run(mode,100,frames=16,chip_factory=factory,matched_reference=True,host_ppm=-100)
    c=chips[0];m=row['reference_metrics']['oscillator_supply']
    assert m['events']>100 and m['maximum_rf_pull_hz']>1000 and m['maximum_wire_pull_hz']>1000
    assert c.return_charge>0 and c.supply.charge>c.return_charge
    assert c.rf_continuity_error<1e-8
    actual_delta=c.supply.delta*math.exp(-(c.time-c.supply.time)/(c.supply.r*c.supply.c))
    assert abs(c.rf_pll.rail_frequency(c.time)-sign*1e6*actual_delta)<1e-6
    assert abs(c.wire_pll.rail_frequency(c.time)-sign*1e6*actual_delta)<1e-6
    row.update(sign=sign,phase_continuity_error_rad=c.rf_continuity_error)
    return row


def independent(mode,sign):
    outputs=[];analog=[]
    for sensitivity in (0.,sign*10e6):
        c=OscillatorSupplyChip(rf_hz_per_v=sensitivity,wire_hz_per_v=sign*1e6,
            return_charge_per_transition=50e-15,watchdog_s=50e-6)
        c.configure_rx('external_tone',1,5e6,5e6,.3+.1j,0.)
        c.configure(mode,0);c.advance(5e-6);c.capture(32,c.time+100e-9)
        c.advance(c.time+3e-6);c.host_decoder.finish()
        assert c.state=='active' and c.host_samples==c.adc_words and len(c.adc_words)==32
        assert c.rf_continuity_error<1e-8
        outputs.append(c.adc_words);analog.append(c.analog_samples)
    difference=max(abs(a-b) for a,b in zip(*analog))
    assert difference>1e-6
    return dict(mode=mode,sign=sign,maximum_analog_difference=difference,
                changed_samples=sum(a!=b for a,b in zip(*outputs)))


def excessive(mode,sign):
    chips=[]
    def factory(**kw):
        c=OscillatorSupplyChip(rf_hz_per_v=sign*1e9,wire_hz_per_v=sign*1e9,
            wire_reference_ppm=100,return_charge_per_transition=50e-15,**kw)
        chips.append(c);return c
    try:run(mode,100,frames=16,chip_factory=factory,matched_reference=True,host_ppm=-100)
    except TrafficFault:
        c=chips[0]
        assert c.state=='draining' and c.events[-1][1] in ('RF oscillator lock loss','wired TX clock lock loss')
        return dict(mode=mode,sign=sign,expected_failure=c.events[-1][1],metrics=c.reference_metrics()['oscillator_supply'])
    raise AssertionError('Excessive oscillator pulling passed silently')


def lifecycle(mode):
    chips=[]
    for cls in (AutonomousRFChip,OscillatorSupplyChip):
        def factory(**kw):
            c=cls(wire_reference_ppm=100,return_charge_per_transition=50e-15,**kw)
            chips.append(c);return c
        run(mode,100,frames=4,chip_factory=factory,matched_reference=True,host_ppm=-100)
    assert chips[0].adc_words==chips[1].adc_words and chips[0].wire_times==chips[1].wire_times
    assert chips[1].oscillator_supply_events==0
    c=OscillatorSupplyChip(rf_hz_per_v=1e6,wire_hz_per_v=-1e6,watchdog_s=50e-6)
    c.configure(mode,0);c.advance(5e-6);start=c.time
    rate=250e6 if mode==0 else 312.5e6
    for index,word in enumerate(encode(mode,[],[],0)):
        c.feed(word,c.epoch,start+(index+1)/rate)
    delta=c.supply.delta;assert delta<0
    c.quiesce(c.time,'digital reset test')
    c.acknowledge_host_abort(c.epoch,c.time);c.acknowledge_drain(c.epoch,c.time)
    c.configure(1-mode,c.time)
    assert abs(c.wire_pll.rail_frequency(c.time)+1e6*delta)<1e-6
    start=c.time;c.advance(start+5e-9)
    expected=delta*math.exp(-5e-9/(c.supply.r*c.supply.c))
    assert abs(c.rf_pll.rail_frequency(c.time)-1e6*expected)<1e-6
    assert abs(c.wire_pll.rail_frequency(c.time)+1e6*expected)<1e-6
    return dict(mode=mode,zero_coupling_identical=True,rail_tail_survives_mode_change=True)


def main():
    import argparse,hashlib
    from pathlib import Path
    parser=argparse.ArgumentParser();parser.add_argument('--trajectory-only',action='store_true')
    args=parser.parse_args()
    if args.trajectory_only:
        report=dict(status='passed',trajectory=trajectory_controls(),feedback=feedback_controls(),legacy_analytic=analytic(),
            limitations=['Prescribed piecewise-linear supply history, not closed bidirectional full-chip feedback.',
            'Interpolation requires convergence; forecast horizon is enforced rather than extrapolated.'])
        files=[Path(__file__)]+[P/'system_model/connected'/name for name in ('autonomous_pll.py','sampled_pll.py','limited_coupled_driver.py','driver_pll_feedback.py')]
        report['source_sha256']={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
        (P/'evidence/connected-supply-trajectory.json').write_text(json.dumps(report,indent=2)+'\n')
        print(report['trajectory']);print(report['feedback']);return
    controls=analytic();lifecycle_cases=[lifecycle(m) for m in (0,1)]
    rows=[traffic(m,s) for m in (0,1) for s in (-1,1)]
    inputs=[independent(m,s) for m in (0,1) for s in (-1,1)]
    failures=[excessive(m,s) for m in (0,1) for s in (-1,1)]
    report=dict(status='passed',analytic=controls,lifecycle=lifecycle_cases,traffic=rows,independent_input=inputs,negative_cases=failures,
        complete_architecture=False,physical_qualification=False,
        limitations=['The existing lumped RC rail and assumed Hz/V coefficients are sensitivity fixtures, not extracted power distribution or measured VCO pushing.',
                    'Both host buses drive the common rail; internal oscillator/converter switching current and separate domain/package networks remain incomplete.',
                    'Clock state integrates continuous exponential rail recovery; fractional-divider spurs and stochastic phase noise remain absent.',
                    'Signed passing/failing points do not establish a robust uncertainty envelope or full RF modem quality.'])
    (P/'evidence/connected-oscillator-supply.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed analytic continuous rail pulling, four-path traffic, independent RF response and expected clock-lock failures')


if __name__=='__main__':main()
