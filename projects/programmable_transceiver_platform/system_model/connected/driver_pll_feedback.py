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
