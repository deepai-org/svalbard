"""Exploratory reference reservoir sensitivity under repeated paired conversion load."""
import json
import numpy as np
from chip_model import P
from managed_unified_reference import CoupledReference
from rf_driver_transient import CoupledDriver

def run(cap,load,rtol):
    r=CoupledReference(capacitance=cap,load_capacitance=load,driver_v_per_v=.05)
    d=CoupledDriver(reference=r)
    rows=[]
    for k in range(32):
        d.advance((k+1)*25e-9,.15+.05j,rtol=rtol,atol=rtol*.001)
        value=(.6+.3j)*(-1 if k%2 else 1)
        rail=d.rail_v
        r.dac_update(d.time,value,load)
        sampled=r.sample(d.time,value)
        assert d.rail_v==rail and r.time==d.time
        rows.append((r.voltage,d.rail_v,abs(sampled/value)))
    assert r.samples==r.dac_updates==32
    return np.array(rows)

def main():
    cases=[]
    for cap,load in ((50e-12,.5e-12),(50e-12,2e-12),(200e-12,.5e-12),(200e-12,2e-12)):
        a=run(cap,load,1e-7);b=run(cap,load,1e-9)
        error=float(np.max(np.abs(a-b)))
        assert error<1e-6
        cases.append(dict(reservoir_f=cap,conversion_load_f=load,numerical_difference=error,
            min_reference_v=float(b[:,0].min()),min_rail_v=float(b[:,1].min()),
            max_adc_reference_gain=float(b[:,2].max())))
    report=dict(status='passed',cases=cases,limitations=[
        'Pass means numerical refinement agrees; it does not mean signal quality meets requirements.',
        'Exploratory component values, 32 paired updates at 40 MS/s; not a qualified operating envelope.',
        'Direct conversion events and held RF source; autonomous PLL, host scheduler and aperture are excluded.'])
    (P/'evidence/connected-unified-reference-envelope.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
