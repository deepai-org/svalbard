"""Independent ODE, zero-coupling equivalence and conversion-load retention."""
import json,copy
from scipy.integrate import solve_ivp
from chip_model import P
from causal_reference_lifecycle import Reference
from driver_sensitive_reference import DriverSensitiveReference

def main():
    r=DriverSensitiveReference(driver_v_per_v=.05)
    r.set_driver_rail(0,3.1,-1e6);split=copy.deepcopy(r)
    end=100e-9;tau=r.r*r.c
    ode=solve_ivp(lambda t,y:[(1+.05*(3.1-1e6*t-3.3)-y[0])/tau],(0,end),[1.],rtol=1e-11,atol=1e-13)
    r.advance(end);split.advance(30e-9);split.advance(end)
    error=abs(r.voltage-ode.y[0,-1])
    assert error<1e-10 and abs(r.voltage-split.voltage)<1e-14
    before=r.voltage;r.set_driver_rail(end,3.2);assert r.voltage==before
    zero=DriverSensitiveReference(driver_v_per_v=0);base=Reference()
    zero.set_driver_rail(0,3.0,1e6)
    for i in range(10):
        t=i*10e-9
        assert abs(zero.sample(t,.2+.1j)-base.sample(t,.2+.1j))<1e-14
        assert abs(zero.dac_update(t,.1+.05j,1e-12)-base.dac_update(t,.1+.05j,1e-12))<1e-14
    assert zero.samples==base.samples==10 and zero.dac_updates==base.dac_updates==10
    assert abs(zero.charge-base.charge)<1e-24
    report=dict(status='passed',ode_error_v=error,reference_voltage_v=r.voltage,
        conversion_charge_c=zero.charge,limitations=['Local reference response and existing impulse-load laws; no live driver connection yet.',
            'Assumed linear supply sensitivity; physical buffer headroom, PSRR, noise and reverse rail-current coupling excluded.'])
    (P/'evidence/connected-driver-reference.json').write_text(json.dumps(report,indent=2)+'\n');print(report)

if __name__=='__main__':main()
