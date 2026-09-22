"""Dense derivative assembly equivalence with optional states and switched loads."""
import json,time,pickle
import numpy as np
from chip_model import P
from guarded_limited_driver import GuardedLimitedDriver
from dense_limited_driver import DenseLimitedDriver
from managed_unified_reference import CoupledReference
from buffered_shared_detector import BufferedSharedDetector
from rf_driver_supply import DriverSupplyLaw

def sample(value,time):return value,False

def run(cls,with_ref,with_detector):
    r=CoupledReference(resistance=50.,load_capacitance=2e-12,driver_v_per_v=.05) if with_ref else None
    det=BufferedSharedDetector(sample) if with_detector else None
    d=cls(reference=r,detector=det);rows=[];start=time.perf_counter()
    for k,config in enumerate(((False,True),(True,False),(True,True),(False,False))):
        d.network.configure(*config)
        if r is not None:
            r.dac_update(d.time,(-1)**k*(.6+.3j),2e-12);r.sample(d.time,.5+.2j)
        d.advance((k+1)*25e-9,lambda t:.2+.03j*np.exp(2j*np.pi*3e6*t))
        rows.append(np.r_[d.network.voltage.real,d.network.voltage.imag,d.rail_v,
            [] if r is None else [r.voltage,r.charge],
            [] if det is None else [det.value,det.readout_value]])
    elapsed=time.perf_counter()-start
    d.law=DriverSupplyLaw(bias_a=.02);before=pickle.dumps(d)
    try:d.advance(d.time+100e-9,.2+0j)
    except ValueError:pass
    else:raise AssertionError('Overload admitted')
    assert pickle.dumps(d)==before
    return np.array(rows),elapsed

def main():
    rows=[]
    for ref in (False,True):
        for det in (False,True):
            a,ta=run(GuardedLimitedDriver,ref,det);b,tb=run(DenseLimitedDriver,ref,det)
            error=float(np.max(abs(a-b)));assert error<1e-10
            rows.append(dict(reference=ref,detector=det,max_state_difference=error,
                baseline_s=ta,dense_s=tb,observed_speedup=ta/tb))
    report=dict(status='passed',cases=rows,limitations=[
        'Local switched ODE equivalence and rollback; full managed PLL/host quality not yet checked.',
        'Single wall-time observation per case under concurrent load; speedup is indicative.'])
    (P/'evidence/connected-dense-driver.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
