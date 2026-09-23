"""Local causal partitioned driver-rail/PLL feedback reference.

Driver pull is held at interval-start rail voltage. PLL phase events drive the
RF load during that interval; new rail voltage affects the next interval.
Finite coupling-step convergence is required, not assumed exact.
"""
import copy,math
from driver_clock_forcing import DriverPulledSpectrum
from managed_coupled_driver import CoupledLoad
from rf_phase_forcing import advance_phase

def _advance_feedback(driver,pll,end,source_terms,hz_per_v,step_s):
    import numpy as np
    if not all(math.isfinite(x) for x in (end,hz_per_v,step_s)) or step_s<=0 or end<driver.time or driver.time!=pll.time:
        raise ValueError('Aligned clocks and valid coupling interval required')
    origin=driver.time;tones=pll.frequency_noise.tones;load=CoupledLoad(driver);steps=0
    carrier=driver.network.omega/(2*math.pi)
    while driver.time<end:
        start=driver.time;stop=min(end,start+step_s)
        trial=copy.copy(pll)
        offset=hz_per_v*(driver.rail_v-driver.law.nominal_v)
        trial.set_noise(start,DriverPulledSpectrum(tones,offset))
        future=copy.copy(trial)
        if not future.advance(stop):raise ValueError('PLL forecast failed')
        events=sorted(set(t for t,_ in future.transitions if start<t<stop))
        def phase(t):
            forecast=copy.copy(trial)
            if not forecast.advance(t):raise ValueError('PLL phase forecast failed')
            return 2*math.pi*(forecast.output_phase_cycles-carrier*t)
        terms=[(a*np.exp(p*(start-origin)),p) for a,p in source_terms]
        advance_phase(load,stop,terms,phase,step_s,events)
        if not trial.advance(stop):raise ValueError('PLL commit forecast failed')
        pll.__dict__.update(trial.__dict__);steps+=1
    return steps


def advance_feedback(driver,pll,end,source_terms,hz_per_v,step_s):
    """Commit all coupled states together; preserve external object identities."""
    local=copy.copy(driver)
    local.network=copy.deepcopy(driver.network)
    # A shallow detector copy preserves its ADC callback/owner; the solve only
    # changes numeric state, not pending conversion or callback-owned objects.
    local.detector=copy.copy(driver.detector) if driver.detector is not None else None
    local.reference=copy.copy(driver.reference) if driver.reference is not None else None
    clock=copy.copy(pll)
    steps=_advance_feedback(local,clock,end,source_terms,hz_per_v,step_s)
    driver.network.__dict__.update(local.network.__dict__)
    if driver.detector is not None:driver.detector.__dict__.update(local.detector.__dict__)
    if driver.reference is not None:driver.reference.__dict__.update(local.reference.__dict__)
    driver.rail_v=local.rail_v;driver.time=local.time
    pll.__dict__.update(clock.__dict__)
    return steps


def forecast_trajectory_feedback(driver,pll,end,source_terms,hz_per_v,step_s,
                                 phase_tolerance=1e-9,rail_tolerance=1e-8,max_iterations=12):
    """Iterate rail -> PLL phase -> loaded RF until the interval agrees.

    Returns candidate states without mutating either caller. Source terms are
    baseband coefficients at driver.time; one shared LO mixes TX and RX. This is
    a local interval solver, not the chip scheduler: the caller must split at all
    converter, switch, host and management events and qualify step refinement.
    """
    import numpy as np
    from autonomous_pll import SupplyTrajectory
    if not all(math.isfinite(v) for v in (end,hz_per_v,step_s,phase_tolerance,rail_tolerance)):
        raise ValueError('Finite feedback parameters required')
    if driver.time!=pll.time or end<=driver.time or min(step_s,phase_tolerance,rail_tolerance)<=0:
        raise ValueError('Aligned clocks and positive interval/tolerances required')
    if type(max_iterations) is not int or max_iterations<2:raise ValueError('At least two feedback iterations required')
    if not source_terms or any(not np.isfinite(a) or not np.isfinite(r) for a,r in source_terms):
        raise ValueError('Finite nonempty source terms required')
    start=driver.time;carrier=driver.network.omega/(2*math.pi)
    times=np.linspace(start,end,max(1,math.ceil((end-start)/step_s))+1)
    rail=np.full(len(times),driver.rail_v-driver.law.nominal_v)
    previous_phase=None
    for iteration in range(1,max_iterations+1):
        clock=copy.copy(pll)
        clock.set_supply_trajectory(SupplyTrajectory(tuple(times),tuple(rail)),hz_per_v)
        phases=[]
        for t in times:
            clock.advance(float(t))
            phases.append(clock.output_phase_cycles-carrier*t)
        phase=np.asarray(phases)
        local=copy.copy(driver)
        local.network=copy.deepcopy(driver.network)
        local.detector=copy.copy(driver.detector) if driver.detector is not None else None
        local.reference=copy.copy(driver.reference) if driver.reference is not None else None
        local.rx_bank=copy.deepcopy(driver.rx_bank)
        def angle(t):return 2*math.pi*float(np.interp(t,times,phase))
        def command(t):
            return sum(a*np.exp(r*(t-start)) for a,r in source_terms)*np.exp(1j*angle(t))
        local.receive=lambda t,pad:pad*np.exp(-1j*angle(t))
        local.advance(end,command,rail_trace_step_s=step_s,rtol=1e-10,atol=1e-13)
        new_rail=np.asarray(local.rail_trajectory.deltas)
        rail_error=float(np.max(abs(new_rail-rail)))
        phase_error=math.inf if previous_phase is None else float(np.max(abs(phase-previous_phase)))
        if rail_error<=rail_tolerance and phase_error<=phase_tolerance:
            return local,clock,dict(iterations=iteration,rail_residual_v=rail_error,
                phase_residual_cycles=phase_error,step_s=step_s)
        previous_phase=phase;rail=new_rail
    raise ValueError('Coupled rail/PLL interval did not converge')
