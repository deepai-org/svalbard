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

def main():
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
    report=dict(status='passed',energy_residual_w=residual,cases=cases,limitations=[
        'Local reference/rail model; full RF network, PLL and host integration remains.',
        'Hard current limiting and constant bias are assumptions, not transistor feasibility.',
        'Pass checks energy and numerical convergence; gain error is not a system quality pass.'])
    (P/'evidence/connected-current-limited-reference.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
