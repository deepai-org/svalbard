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

def energy_controls():
    import math
    d=LimitedCoupledDriver();d.driver_enabled=False;d.extra_current=lambda t,v:.001
    d.advance(30e-9,0j)
    expected=3.3-.1*(1-math.exp(-3))
    error=abs(d.rail_v-expected)
    residual=d.source_energy_j-d.rail_resistor_energy_j-d.load_energy_j-.5*d.c*(d.rail_v**2-3.3**2)
    assert error<1e-9 and abs(residual)<1e-18
    before=(d.time,d.rail_v,d.source_energy_j,d.load_energy_j,d.rail_resistor_energy_j,d.extra_load_energy_j)
    d.extra_current=lambda t,v:.1
    try:d.advance(100e-9,0j)
    except ValueError:pass
    else:raise AssertionError('Overload accepted')
    assert before==(d.time,d.rail_v,d.source_energy_j,d.load_energy_j,d.rail_resistor_energy_j,d.extra_load_energy_j)
    return dict(analytic_voltage_error_v=error,energy_residual_j=residual,overload_rolls_back=True)

def domain_controls():
    from shared_supply_lifecycle import DomainSupply
    from driver_sensitive_reference import DriverSensitiveReference
    names=('CORE','HOST_A','HOST_B','WIRE_A','WIRE_B','RF','PLL')
    supply=DomainSupply(names,[3.3]*7,[2.]*7,[100e-12]*7,.1)
    d=LimitedCoupledDriver(domain_supply=supply,domain_minimum_v=[2.5]*7,
        domain_load=lambda t,v:[.02,.02,.02,0,0,.01,.008],reference=DriverSensitiveReference())
    d.advance(5e-9,0j,rail_trace_step_s=.1e-9)
    r=d.domains
    stored=.5*np.sum(r.c*(r.voltage**2-r.nominal**2))
    residual=r.source_energy_j-r.feed_loss_j-r.load_energy_j-stored
    assert abs(residual)<1e-18
    assert abs(d.rail_v-r.voltage[5])<1e-12 and d.reference.driver_voltage==r.voltage[6]
    assert len(d.domain_trajectories)==7 and r.voltage[5]!=r.voltage[6]
    before=np.r_[r.voltage,d.network.voltage.real,d.network.voltage.imag,d.reference.voltage,r.time,r.source_energy_j]
    from autonomous_pll import AutonomousPLL
    from driver_pll_feedback import forecast_trajectory_feedback
    clock=AutonomousPLL();clock.advance(d.time)
    trial,future,metrics=forecast_trajectory_feedback(d,clock,7e-9,[(0j,0j)],1e6,.1e-9)
    assert d.time==clock.time==r.time==5e-9
    assert np.array_equal(before,np.r_[r.voltage,d.network.voltage.real,d.network.voltage.imag,d.reference.voltage,r.time,r.source_energy_j])
    assert trial.time==trial.domains.time==future.time==7e-9
    d.domain_load=lambda t,v:[1.]*7
    try:d.advance(10e-9,0j)
    except ValueError:pass
    else:raise AssertionError('Domain overload accepted')
    after=np.r_[r.voltage,d.network.voltage.real,d.network.voltage.imag,d.reference.voltage,r.time,r.source_energy_j]
    assert np.array_equal(before,after)
    return dict(feedback_iterations=metrics["iterations"],forecast_preserves_live_domains=True,energy_residual_j=float(residual),separate_rf_and_reference_supplies=True,
        overload_preserves_analog_and_domains=True,full_chip_connected=False)

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
    report=dict(status='passed',energy_controls=energy_controls(),receive_controls=receive_controls(),max_state_difference=max(errors),switch_cases=4,
        limitations=['Nonbinding current-limit regression on finite local PLL/network intervals, not payload quality.',
        'No physical parameter qualification; finite-limit managed calibration remains separate.'])
    (P/'evidence/connected-limited-baseline-equivalence.json').write_text(json.dumps(report,indent=2)+'\n');print(report)
if __name__=='__main__':
    import sys
    if '--domain-controls' in sys.argv:print(domain_controls())
    else:main()
