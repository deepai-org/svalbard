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
    if getattr(driver,"domains",None) is not None:raise ValueError("Use trajectory feedback for domain supplies")
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
                                 phase_tolerance=1e-9,rail_tolerance=1e-8,max_iterations=12,receive_transform=None,inactive_rf=False,quiet_rf=False,solver_method="Radau"):
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
    if quiet_rf:
        if any(a!=0 for a,_ in source_terms) or not zero_rf_state(driver):
            raise ValueError('Quiet powered RF requires zero source and signal state')
        local,clock=forecast_inactive_rf(driver,pll,end,hz_per_v,step_s,quiet_powered=True)
        return local,clock,dict(iterations=1,rail_residual_v=0.,phase_residual_cycles=0.,
                               step_s=step_s,quiet_powered_rf=True)
    if inactive_rf:
        if any(a!=0 for a,_ in source_terms):raise ValueError('Inactive RF requires zero source')
        local,clock=forecast_inactive_rf(driver,pll,end,hz_per_v,step_s)
        return local,clock,dict(iterations=1,rail_residual_v=0.,phase_residual_cycles=0.,
                               step_s=step_s,rf_inactive=True)
    start=driver.time;carrier=driver.network.omega/(2*math.pi)
    times=np.linspace(start,end,max(1,math.ceil((end-start)/step_s))+1)
    domains=getattr(driver,'domains',None)
    initial_rail=(domains.voltage[driver.reference_domain]-domains.nominal[driver.reference_domain]) if domains is not None else driver.rail_v-driver.law.nominal_v
    rail=np.full(len(times),initial_rail)
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
        if domains is not None:local.domains=copy.deepcopy(domains)
        local.host_bank=copy.deepcopy(getattr(driver,'host_bank',None))
        local.pad_branch=copy.deepcopy(getattr(driver,'pad_branch',None))
        local.network=copy.deepcopy(driver.network)
        local.detector=copy.copy(driver.detector) if driver.detector is not None else None
        local.reference=copy.copy(driver.reference) if driver.reference is not None else None
        local.rx_bank=copy.deepcopy(driver.rx_bank)
        def angle(t):return 2*math.pi*float(np.interp(t,times,phase))
        def command(t):
            return sum(a*np.exp(r*(t-start)) for a,r in source_terms)*np.exp(1j*angle(t))
        local.receive=lambda t,pad:(receive_transform(t,pad,angle(t)) if receive_transform is not None else pad*np.exp(-1j*angle(t)))
        local.advance(end,command,rail_trace_step_s=step_s,rtol=1e-10,atol=1e-13,solver_method=solver_method)
        trace=local.domain_trajectories['PLL'] if domains is not None else local.rail_trajectory
        new_rail=np.asarray(trace.deltas)
        rail_error=float(np.max(abs(new_rail-rail)))
        phase_error=math.inf if previous_phase is None else float(np.max(abs(phase-previous_phase)))
        if rail_error<=rail_tolerance and phase_error<=phase_tolerance:
            return local,clock,dict(iterations=iteration,rail_residual_v=rail_error,
                phase_residual_cycles=phase_error,step_s=step_s)
        previous_phase=phase;rail=new_rail
    raise ValueError('Coupled rail/PLL interval did not converge')


def inactive_rf_solver(driver):
    """Explicit solve only on an exactly dormant RF invariant subspace.

    forecast_inactive_rf also replaces receive forcing with zero. Any retained
    RF charge, filter/detector history or enabled driver keeps the stiff solver.
    """
    return 'RK45' if not driver.driver_enabled and zero_rf_state(driver) else 'Radau'


def zero_rf_state(driver):
    return (all(v==0 for v in driver.network.voltage) and
        (driver.rx_bank is None or all(v==0 for v in driver.rx_bank['states'])) and
        (driver.detector is None or (driver.detector.value==0 and driver.detector.readout_value==0)))


def forecast_inactive_rf(driver,pll,end,hz_per_v,step_s,*,quiet_powered=False):
    from autonomous_pll import SupplyTrajectory
    if quiet_powered and not zero_rf_state(driver):
        raise ValueError("Quiet powered forecast requires zero RF states")
    if not quiet_powered and (pll.powered or driver.driver_enabled):
        raise ValueError('RF clock and driver must both be disabled')
    if (driver.time!=pll.time or not all(math.isfinite(x) for x in (end,hz_per_v,step_s))
            or end<=driver.time or step_s<=0):
        raise ValueError('Aligned positive forecast interval required')
    local=copy.copy(driver)
    for name in ('domains','host_bank','pad_branch','network','rx_bank'):
        setattr(local,name,copy.deepcopy(getattr(driver,name)))
    for name in ('detector','reference'):
        setattr(local,name,copy.copy(getattr(driver,name)))
    local.receive=lambda t,pad:0j
    local.advance(end,lambda t:0j,rail_trace_step_s=step_s,rtol=1e-10,atol=1e-13,solver_method="RK45" if quiet_powered else inactive_rf_solver(local))
    trace=local.domain_trajectories['PLL'] if local.domains is not None else local.rail_trajectory
    clock=copy.copy(pll)
    clock.set_supply_trajectory(trace,hz_per_v);clock.advance(end)
    return local,clock
