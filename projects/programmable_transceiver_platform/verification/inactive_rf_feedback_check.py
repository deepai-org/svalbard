"""Candidate off-RF single-solve equivalence probe; not installed in chip."""
import copy,time,json,hashlib,math
from pathlib import Path
from full_chip_model import make_chip
from driver_pll_feedback import forecast_trajectory_feedback
from autonomous_pll import SupplyTrajectory
import limited_coupled_driver as ode
import numpy as np


def inactive(driver,pll,end,hz_per_v,step_s):
    if pll.powered or driver.driver_enabled:
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
    local.advance(end,lambda t:0j,rail_trace_step_s=step_s,rtol=1e-10,atol=1e-13)
    trace=local.domain_trajectories['PLL']
    clock=copy.copy(pll)
    clock.set_supply_trajectory(trace,hz_per_v);clock.advance(end)
    return local,clock

def numeric_state(driver,clock):
    result={}
    def collect(prefix,value):
        if isinstance(value,(int,float,complex,np.number)):
            result[prefix]=np.asarray(value).copy()
        elif isinstance(value,np.ndarray) and value.dtype.kind in 'biufc':
            result[prefix]=value.copy()
        elif isinstance(value,dict):
            for key,item in value.items():collect(prefix+'.'+str(key),item)
        elif isinstance(value,(tuple,list)):
            for i,item in enumerate(value):collect(prefix+'.'+str(i),item)
    objects={'driver':driver,'clock':clock}
    objects.update({name:getattr(driver,name) for name in
                   ('network','domains','host_bank','reference','detector','pad_branch')})
    for name,obj in objects.items():
        if obj is not None:collect(name,vars(obj))
    return result


def unchanged(before,driver,clock):
    after=numeric_state(driver,clock)
    assert before.keys()==after.keys()
    for key in before:np.testing.assert_array_equal(before[key],after[key],err_msg=key)


original=ode.solve_ivp;calls=[]
def counted(*a,**kw):
    calls.append(1);return original(*a,**kw)
ode.solve_ivp=counted
rows=[]
for duration in (2e-9,20e-9):
 for loaded in (False,True):
    c=make_chip();c.configure_resources(engine='wire',line_rate_bps=1.62e9)
    if loaded:c.emitted_return_word(1023,0.)
    c.configure_analog_loads();driver=c.analog_owner;clock=c.rf_pll
    # Nonzero stored analog state must decay normally, not be erased by shutdown.
    driver.network.voltage[:2]=(.03+.02j,.01-.01j)
    initial=driver.network.voltage.copy();before=numeric_state(driver,clock)
    calls.clear();start=time.perf_counter()
    reference,refclock,metrics=forecast_trajectory_feedback(driver,clock,duration,[(0j,0j)],1e6,.5e-9,receive_transform=lambda t,p,a:0j)
    full_time=time.perf_counter()-start;full_calls=len(calls)
    calls.clear();start=time.perf_counter();candidate,newclock=inactive(driver,clock,duration,1e6,.5e-9)
    fast_time=time.perf_counter()-start;fast_calls=len(calls)
    checks=[(candidate.network.voltage,reference.network.voltage),(candidate.host_bank.state,reference.host_bank.state),
      (candidate.domains.voltage,reference.domains.voltage),(candidate.rx_bank['states'],reference.rx_bank['states']),
      ([candidate.reference.voltage,candidate.source_energy_j,candidate.load_energy_j,candidate.extra_load_energy_j],
       [reference.reference.voltage,reference.source_energy_j,reference.load_energy_j,reference.extra_load_energy_j]),
      ([newclock.time,newclock.integral,newclock.hold_voltage,newclock.output_phase_cycles],
       [refclock.time,refclock.integral,refclock.hold_voltage,refclock.output_phase_cycles])]
    errors=[float(np.max(abs(np.asarray(a)-np.asarray(b)))) for a,b in checks]
    assert max(errors)<1e-10,errors
    assert np.array_equal(driver.network.voltage,initial) and driver.time==clock.time==0
    left=numeric_state(candidate,newclock);right=numeric_state(reference,refclock)
    assert left.keys()==right.keys()
    ledger_fields=0
    for key in left:
        ledger=any(token in key for token in ('energy','charge','loss','dissipat'))
        ledger_fields+=int(ledger)
        np.testing.assert_allclose(left[key],right[key],rtol=2e-12,
            atol=1e-24 if ledger else 1e-12,err_msg=key)
    for name,trace in candidate.domain_trajectories.items():
        np.testing.assert_allclose(trace.deltas,reference.domain_trajectories[name].deltas,rtol=0,atol=1e-14)
    unchanged(before,driver,clock)
    assert ledger_fields>10
    assert fast_calls==1 and full_calls>=2
    rows.append(dict(duration_s=duration,host_edge=loaded,original_solves=full_calls,candidate_solves=fast_calls,
                     max_checked_state_difference=max(errors),numeric_fields=len(left),ledger_fields=ledger_fields,original_s=full_time,candidate_s=fast_time))
# Reject active RF and invalid intervals without touching caller state.
c=make_chip();c.configure_resources(engine='rf');c.configure_analog_loads()
before=numeric_state(c.analog_owner,c.rf_pll)
try:inactive(c.analog_owner,c.rf_pll,2e-9,1e6,.5e-9)
except ValueError:pass
else:raise AssertionError('Active RF accepted')
unchanged(before,c.analog_owner,c.rf_pll)
c.configure_resources(engine='wire');c.configure_analog_loads()
before=numeric_state(c.analog_owner,c.rf_pll)
for end,step in ((0.,.5e-9),(2e-9,0.),(float('nan'),.5e-9)):
    try:inactive(c.analog_owner,c.rf_pll,end,1e6,step)
    except ValueError:pass
    else:raise AssertionError('Invalid forecast accepted')
    unchanged(before,c.analog_owner,c.rf_pll)
# A solver failure must leave all numerical caller state untouched.
def fail(*args,**kwargs):raise ValueError('injected solver failure')
ode.solve_ivp=fail
try:inactive(c.analog_owner,c.rf_pll,2e-9,1e6,.5e-9)
except ValueError:pass
else:raise AssertionError('Solver failure swallowed')
finally:ode.solve_ivp=original
unchanged(before,c.analog_owner,c.rf_pll)
print(json.dumps(rows,indent=2))
root=Path(__file__).resolve().parents[1]
files=[Path(__file__),root/'system_model/connected/driver_pll_feedback.py',
       root/'system_model/connected/limited_coupled_driver.py',root/'verification/fast_exclusive_engine.py']
report=dict(status='passed',cases=rows,installed=False,active_rf_rejected=True,invalid_intervals_rejected=True,solver_failure_rollback=True,
    scope='four frozen-boundary RF-disabled forecast comparisons; not complete-system equivalence',
    source_sha256={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
(root/'evidence/inactive-rf-feedback.json').write_text(json.dumps(report,indent=2)+'\n')
