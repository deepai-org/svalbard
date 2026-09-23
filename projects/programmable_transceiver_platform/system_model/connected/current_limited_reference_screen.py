"""Finite drive: energy conservation, current ceiling and repetitive conversion."""
import json
import numpy as np
from chip_model import P
from managed_unified_reference import CoupledReference
from current_limited_reference import CurrentLimitedReferenceRail,power

def run(limit,tol):
    r=CoupledReference(resistance=50.,capacitance=100e-12,load_capacitance=2e-12,driver_v_per_v=.05)
    d=CurrentLimitedReferenceRail(r,source_limit_a=limit,sink_limit_a=limit)
    rows=[]
    for k in range(128):
        d.advance((k+1)*25e-9,rtol=tol,atol=tol*.001)
        value=(.6+.3j)*(-1 if k%2 else 1)
        r.dac_update(d.time,value,2e-12)
        gain=abs(r.sample(d.time,value)/value)
        rows.append((r.voltage,d.rail_v,gain))
    return np.array(rows)

def fast_controls():
    from scipy.integrate import solve_ivp
    from causal_reference_lifecycle import CurrentLimitedReference,Reference
    errors=[]
    for initial in (.4,.99,1.01,1.6):
        a=CurrentLimitedReference();a.voltage=initial
        b=CurrentLimitedReference();b.voltage=initial
        end=1e-6
        sol=solve_ivp(lambda t,y:[max(-150e-6,min(150e-6,(1-y[0])/1000))/1e-10],
            (0,end),[initial],rtol=1e-10,atol=1e-12,max_step=1e-9)
        assert sol.success
        a.advance(end)
        for i in range(1,101):b.advance(end*i/100)
        errors.append(abs(a.voltage-sol.y[0,-1]))
        assert errors[-1]<1e-9 and abs(a.voltage-b.voltage)<1e-13
        assert abs(a.recharge_c-a.absorbed_c-a.c*(a.voltage-initial))<1e-23
    a=CurrentLimitedReference(source_limit_a=1.,sink_limit_a=1.);b=Reference()
    a.voltage=b.voltage=.5;a.advance(1e-7);b.advance(1e-7)
    assert a.voltage==b.voltage and a.limited_s==0
    weak=CurrentLimitedReference(source_limit_a=1e-6);weak.voltage=.5;weak.advance(1e-7)
    assert weak.voltage<.51 and weak.limited_s==1e-7
    return dict(maximum_ode_voltage_error=max(errors),nonbinding_matches_rc=True,
        insufficient_current_slows_recharge=True,charge_conserved=True)

def main():
    fast=fast_controls()
    residual=0.
    for v in np.linspace(.3,1.7,51):
        p=power(v,1.,50.,3.1,.0002,.0001,.0001,.5)
        assert -.0001<=p['current_a']<=.0002
        assert min(p['resistor_w'],p['limiter_w'],p['buffer_dissipation_w'])>=-1e-16
        residual=max(residual,abs(p['source_w']-p['stored_w']-p['resistor_w']-p['limiter_w']))
    assert residual<1e-15
    cases=[]
    for limit in (50e-6,150e-6,600e-6):
        a=run(limit,1e-7);b=run(limit,1e-9)
        delta=float(np.max(abs(a-b)));assert delta<1e-6
        cases.append(dict(limit_a=limit,minimum_reference_v=float(b[:,0].min()),
            maximum_sample_gain=float(b[:,2].max()),last_sample_gain=float(b[-1,2]),numerical_difference=delta))
    assert cases[0]['maximum_sample_gain']>cases[-1]['maximum_sample_gain']
    report=dict(status='passed',fast_exact_reference=fast,energy_residual_w=residual,cases=cases,limitations=[
        'Local reference/rail model; full RF network, PLL and host integration remains.',
        'Hard current limiting and constant bias are assumptions, not transistor feasibility.',
        'Pass checks energy and numerical convergence; gain error is not a system quality pass.'])
    (P/'evidence/connected-current-limited-reference.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
