"""Nonbinding reference limits preserve unified baseline state and PLL feedback."""
import json
import numpy as np
from chip_model import P
from managed_unified_reference import CoupledReference
from buffered_shared_detector import BufferedSharedDetector
from rf_driver_transient import CoupledDriver
from limited_coupled_driver import LimitedCoupledDriver
from pulse_clock_service import PulseClockService
from driver_pll_feedback import advance_feedback

def build(cls):
    r=CoupledReference(resistance=50.,load_capacitance=2e-12,driver_v_per_v=.05)
    det=BufferedSharedDetector(lambda value,time:(value,False))
    extra=dict(source_limit_a=1.,sink_limit_a=1.) if cls is LimitedCoupledDriver else {}
    d=cls(reference=r,detector=det,**extra)
    return d,PulseClockService(40e6,60,2.4e9)

def observe(d,pll):
    return np.r_[d.network.voltage.real,d.network.voltage.imag,d.rail_v,
        d.reference.voltage,d.detector.value,d.detector.readout_value,pll.output_phase_cycles]

def main():
    a,pa=build(CoupledDriver);b,pb=build(LimitedCoupledDriver)
    errors=[]
    for k,config in enumerate(((False,True),(True,False),(True,True),(False,False))):
        for d,pll in ((a,pa),(b,pb)):
            d.network.configure(*config)
            d.reference.dac_update(d.time,(-1)**k*(.6+.3j),2e-12)
            d.reference.sample(d.time,.5+.2j)
            advance_feedback(d,pll,(k+1)*10e-9,[(.2+.03j,0j)],1e6,1e-9)
        error=float(np.max(abs(observe(a,pa)-observe(b,pb))))
        assert error<1e-8
        assert a.reference.samples==b.reference.samples==k+1
        assert a.reference.dac_updates==b.reference.dac_updates==k+1
        assert abs(a.reference.charge-b.reference.charge)<1e-20
        errors.append(error)
    report=dict(status='passed',max_state_difference=max(errors),switch_cases=4,
        limitations=['Nonbinding current-limit regression on finite local PLL/network intervals, not payload quality.',
        'No physical parameter qualification; finite-limit managed calibration remains separate.'])
    (P/'evidence/connected-limited-baseline-equivalence.json').write_text(json.dumps(report,indent=2)+'\n');print(report)
if __name__=='__main__':main()
