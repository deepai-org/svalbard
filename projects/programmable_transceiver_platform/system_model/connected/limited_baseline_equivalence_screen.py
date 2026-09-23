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

def receive_controls():
    import cmath,copy
    from session import Session
    from rf_cascade_state import RfCascadeState,convolution
    from rf_loaded_detector import voltage_terms
    from rf_driver_supply import DriverSupplyLaw
    class LinearOracleLaw(DriverSupplyLaw):
        def source(self,command,rail):return command
    cascade=RfCascadeState(Session());cascade.set_butterworth(5,9.1574070557e6)
    errors=[]
    # Independent modal convolution checks pad loading and a nonzero mixer offset.
    for with_reference in (False,True):
        d,_=build(LimitedCoupledDriver)
        if not with_reference:d.reference=None;d.detector=None
        d.law=LinearOracleLaw();d.rx_bank=copy.deepcopy(cascade.rx_bank)
        omega=2*np.pi*1.3e6
        d.receive=lambda t,pad:pad*np.exp(-1j*omega*t)
        d.network.configure(True,False)
        terms=voltage_terms(d.network,[(.2+.03j,0j)])
        end=30e-9
        expected=[sum(v[1]*convolution(rate-1j*omega,pole,end) for v,rate in terms)
                  for pole in d.rx_bank['poles']]
        d.advance(end,.2+.03j,rtol=1e-10,atol=1e-13)
        error=float(np.max(abs(np.array(expected)-d.rx_bank['states'])))
        assert error<1e-8;errors.append(error)
    # Actual nonlinear driver/reference/detector/filter share one trajectory.
    a,_=build(LimitedCoupledDriver);a.rx_bank=copy.deepcopy(cascade.rx_bank)
    a.network.configure(True,False);b=copy.deepcopy(a)
    a.advance(30e-9,.3+.1j)
    for k in range(1,7):b.advance(k*5e-9,.3+.1j)
    difference=abs(a.received-b.received)
    assert difference<1e-8
    before=copy.deepcopy(a)
    def invalid(t,pad):return complex(float('nan'),0)
    a.receive=invalid
    try:a.advance(40e-9,.3+.1j)
    except ValueError:pass
    else:raise AssertionError('Invalid receiver accepted')
    assert a.time==before.time and a.reference.voltage==before.reference.voltage
    assert a.detector.value==before.detector.value and a.rail_v==before.rail_v
    assert np.array_equal(a.network.voltage,before.network.voltage)
    assert a.rx_bank==before.rx_bank and a.received==before.received
    return dict(modal_filter_error=max(errors),subdivision_error=difference,failed_solve_preserves_state=True)

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
    report=dict(status='passed',receive_controls=receive_controls(),max_state_difference=max(errors),switch_cases=4,
        limitations=['Nonbinding current-limit regression on finite local PLL/network intervals, not payload quality.',
        'No physical parameter qualification; finite-limit managed calibration remains separate.'])
    (P/'evidence/connected-limited-baseline-equivalence.json').write_text(json.dumps(report,indent=2)+'\n');print(report)
if __name__=='__main__':main()
