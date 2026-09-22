"""Independent analytic, convergence, acquisition and holdover PLL checks."""
import json
import math
from pathlib import Path
from autonomous_pll import AutonomousPLL


def settle(p,end):
    tick=math.floor(p.time*p.reference_hz)+1
    while tick/p.reference_hz<=end:
        p.advance(tick/p.reference_hz);p.observe_lock();tick+=1
    p.advance(end)


def controls():
    # Exact unsaturated second-order response; no fitting to numerical output.
    p=AutonomousPLL(phase_cycles=.002,free_hz=2.399e9)
    omega=2*math.pi*1e6;zeta=.707;wd=omega*math.sqrt(1-zeta*zeta)
    a=p.error;v=p.reference_hz-p.frequency_hz/p.divider
    b=(v+zeta*omega*a)/wd
    errors=[]
    for j in range(1,101):
        t=j*10e-9;p.advance(t)
        expected=math.exp(-zeta*omega*t)*(a*math.cos(wd*t)+b*math.sin(wd*t))
        errors.append(abs(p.error-expected))
    assert max(errors)<1e-11
    # Saturated capture is independently refined in integration step size.
    trajectories=[]
    for step in (1e-9,.5e-9,.25e-9):
        p=AutonomousPLL(free_hz=2.304e9,phase_cycles=.8,max_step_s=step)
        history=[]
        for t in (50e-9,200e-9,500e-9,1e-6,2e-6):
            p.advance(t);history.extend((p.error,p.integral))
        trajectories.append(history)
    assert max(abs(a-b) for a,b in zip(trajectories[-1],trajectories[-2]))<1e-8
    return dict(analytic_max_phase_error_cycles=max(errors),refined_states=trajectories)


def acquisition():
    rows=[]
    for divider in (31.25,60.,62.5):
        target=40e6*divider
        for sign in (-1,1):
            p=AutonomousPLL(divider=divider,free_hz=target*(1+sign*.04),phase_cycles=sign*3)
            settle(p,20e-6)
            assert p.locked and abs(p.frequency_hz-target)<1
            rows.append(dict(divider=divider,initial_phase_cycles=sign*3,
                             initial_offset_fraction=sign*.04,locked=p.locked,
                             final_phase_cycles=p.error,saturated_s=p.saturation_time))
        # Beyond the VCO range must never report successful acquisition.
        p=AutonomousPLL(divider=divider,free_hz=target+250e6,phase_cycles=0.)
        settle(p,20e-6)
        assert not p.locked and p.error<-1 and abs(p.control()+p.rail)<1e-12
        rows.append(dict(divider=divider,outside_tuning_range=True,locked=p.locked,
                         final_phase_cycles=p.error))
    return rows


def holdover():
    p=AutonomousPLL();settle(p,5e-6);assert p.locked
    p.set_reference(False,p.time);assert not p.locked
    voltage=p.control();old=p.error;start=p.time
    p.disturb(start,frequency_hz=1e6);p.advance(start+2e-6)
    expected=old+(p.reference_hz-(p.free_hz+p.kvco*voltage+1e6)/p.divider)*2e-6
    assert abs(p.error-expected)<1e-10 and p.control()==voltage
    drift=p.error-old
    p.set_reference(True,p.time);settle(p,15e-6);assert p.locked
    p.disturb(p.time,phase_cycles=1.25,frequency_hz=-5e6)
    p.observe_lock();assert not p.locked
    settle(p,25e-6);assert p.locked
    return dict(holdover_phase_drift_cycles=drift,reacquired=True,
                final_frequency_hz=p.frequency_hz,final_phase_cycles=p.error)


def edges():
    rows=[]
    for divider in (31.25,60.,62.5):
        p=AutonomousPLL(divider=divider,free_hz=40e6*divider*.96)
        settle(p,5e-6)
        p.disturb(p.time,frequency_hz=10e6)
        origin=p.output_phase_cycles;previous=p.time;largest=0.
        for index in range(1,65):
            saved=(p.time,p.error,p.integral)
            deadline=p.edge_time(origin+index/2)
            assert (p.time,p.error,p.integral)==saved
            assert deadline>previous
            p.advance(deadline)
            largest=max(largest,abs(p.output_phase_cycles-origin-index/2))
            previous=deadline
        assert largest<1e-9
        rows.append(dict(divider=divider,half_cycle_crossings=64,
                         maximum_phase_residual_cycles=largest))
    return rows


def main():
    report=dict(status='passed',controls=controls(),acquisition=acquisition(),holdover=holdover(),edges=edges(),
                complete_architecture=False,physical_qualification=False,
                limitations=[
                    'Averaged ideal PFD clips unwrapped phase error to half a reference cycle; no gate-level divider or charge-pump pulses.',
                    'Fractional divider ratios represent average frequency only; fractional spurs and edge patterns are absent.',
                    'Declared VCO gain/range and loop bandwidth are assumptions, not public-PDK validation.',
                    'Deterministic oscillator dynamics only; stochastic phase noise and supply-network coupling remain open.',
                    'Standalone clock block has not yet replaced connected serializer or RF mixer timing.'])
    out=Path(__file__).resolve().parents[2]/'evidence/connected-autonomous-pll.json'
    out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
