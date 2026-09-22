"""Driver/network/detector/reference use one physical rail state."""
import copy,json
from chip_model import P
from rf_driver_transient import CoupledDriver
from driver_sensitive_reference import DriverSensitiveReference
from buffered_shared_detector import BufferedSharedDetector
from driver_pll_feedback import advance_feedback
from pulse_clock_service import PulseClockService

def main():
    r=DriverSensitiveReference(driver_v_per_v=.05)
    detector=BufferedSharedDetector(lambda value,time:(value,False))
    d=CoupledDriver(reference=r,detector=detector);split=copy.deepcopy(d)
    d.advance(2e-6,0j);split.advance(.5e-6,0j);split.advance(2e-6,0j)
    assert abs(d.rail_v-3.09)<1e-8 and abs(r.voltage-.9895)<1e-8
    assert abs(d.rail_v-split.rail_v)<1e-8 and abs(r.voltage-split.reference.voltage)<1e-8
    rail=d.rail_v;r.sample(d.time,.5+.2j);r.dac_update(d.time,.1,1e-12)
    assert d.rail_v==rail and r.samples==r.dac_updates==1
    d.advance(d.time+10e-9,0j);assert d.rail_v<rail
    # PLL feedback staging must retain the live reference object and counters.
    ref=DriverSensitiveReference(driver_v_per_v=.05);c=CoupledDriver(reference=ref)
    pll=PulseClockService(40e6,60,2.4e9)
    advance_feedback(c,pll,5e-9,[(.2+0j,0j)],1e6,1e-9)
    assert c.reference is ref and ref.time==c.time==pll.time and ref.voltage<1
    report=dict(status='passed',loaded_rail_v=d.rail_v,reference_voltage_v=r.voltage,
        conversion_counts=[r.samples,r.dac_updates],feedback_reference_v=ref.voltage,
        limitations=['Local unified state with reference loading and PLL feedback; managed converter-event integration remains.',
            'Physical current limits, supply-dependent output impedance and parameter envelopes remain unqualified.'])
    (P/'evidence/connected-unified-driver-reference.json').write_text(json.dumps(report,indent=2)+'\n');print(report)

if __name__=='__main__':main()
