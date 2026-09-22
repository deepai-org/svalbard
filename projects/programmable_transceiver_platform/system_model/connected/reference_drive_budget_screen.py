"""Reference drive budget: repetitive charge, finite RC recovery and rail loading."""
import json,math
import numpy as np
from chip_model import P
from managed_unified_reference import CoupledReference
from driver_sensitive_reference import DriverSensitiveReference
from rf_driver_transient import CoupledDriver
from reference_buffer_power import account

def run(resistance,rtol):
    cap=100e-12;load=2e-12;period=25e-9
    r=CoupledReference(resistance=resistance,capacitance=cap,load_capacitance=load,driver_v_per_v=.05)
    d=CoupledDriver(reference=r)
    rows=[]
    for k in range(64):
        d.advance((k+1)*period,.15+.05j,rtol=rtol,atol=rtol*.001)
        value=(.6+.3j)*(-1 if k%2 else 1)
        pre=r.voltage;charge=r.charge
        r.dac_update(d.time,value,load)
        sampled=r.sample(d.time,value)
        target=1+r.driver_sensitivity*(d.rail_v-r.driver_nominal)
        power=account(r.voltage,target,r.r,d.rail_v)
        rows.append((pre,r.voltage,abs(sampled/value),d.rail_v,r.charge-charge,power['output_current_a']))
    # Independent steady periodic recurrence, fixed at final target. Alternating
    # DAC codes give activity=.45, ADC activity=.9 after the first event.
    fd=1-load/cap*(.25+.75*.45)
    fa=1-load/cap*(.25+.75*.9)
    decay=math.exp(-period/(resistance*cap))
    periodic_pre=target*(1-decay)/(1-decay*fd*fa)
    predicted_gain=1/(periodic_pre*fd)
    # Check the recurrence against an independently advanced fixed-rail RC.
    # The coupled rail ripples, so its endpoint target is only an approximation.
    fixed=DriverSensitiveReference(resistance=resistance,capacitance=cap,load_capacitance=load,driver_v_per_v=.05)
    fixed.set_driver_rail(0.,d.rail_v)
    for k in range(128):
        t=(k+1)*period;value=(.6+.3j)*(-1 if k%2 else 1)
        fixed.dac_update(t,value,load)
        observed=abs(fixed.sample(t,value)/value)
    assert abs(observed-predicted_gain)<1e-10
    return np.array(rows),predicted_gain

def main():
    cases=[]
    for resistance in (50.,200.,1000.):
        a,_=run(resistance,1e-7);b,predicted=run(resistance,1e-9)
        delta=float(np.max(np.abs(a-b)));assert delta<1e-6
        cases.append(dict(resistance_ohm=resistance,capacitance_f=100e-12,load_f=2e-12,
            max_sample_gain=float(b[:,2].max()),last_sample_gain=float(b[-1,2]),
            fixed_rail_periodic_gain=predicted,fixed_rail_approximation_error=float(b[-1,2]-predicted),min_reference_v=float(b[:,1].min()),
            min_rail_v=float(b[:,3].min()),mean_conversion_current_a=float(b[-16:,4].mean()/25e-9),
            max_observed_post_event_buffer_current_a=float(b[:,5].max()),numerical_difference=delta))
    report=dict(status='passed',cases=cases,limitations=[
        'Convergence and independent periodic recurrence checked, not system quality or physical feasibility.',
        'Buffer resistance changes at fixed assumed bias; achievable impedance/current/bandwidth/power tradeoff is unqualified.',
        'Observed post-event current is not a bound on all transient or SAR bit-trial current.',
        '64 direct paired events, held RF source; no full host or autonomous PLL in this local screen.'])
    (P/'evidence/connected-reference-drive-budget.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
