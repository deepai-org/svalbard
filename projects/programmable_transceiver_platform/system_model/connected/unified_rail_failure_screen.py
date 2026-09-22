"""Declared rail-envelope failure preserves loaded reference and pending readout."""
import json,pickle
from chip_model import P
from rf_driver_transient import CoupledDriver
from rf_driver_supply import DriverSupplyLaw
from driver_sensitive_reference import DriverSensitiveReference
from buffered_shared_detector import BufferedSharedDetector
from pulse_clock_service import PulseClockService
from driver_pll_feedback import advance_feedback

def sample(value,time):return value,False

def setup(bias):
    r=DriverSensitiveReference(driver_v_per_v=.05)
    r.sample(0,.2+.1j)
    det=BufferedSharedDetector(sample);det.value=.003;det.readout_value=.002;det.request()
    return CoupledDriver(law=DriverSupplyLaw(bias_a=bias),reference=r,detector=det)

def main():
    rows=[]
    for bias in (.002,.006,.01,.02):
        d=setup(bias);before=pickle.dumps(d)
        try:d.advance(200e-9,0j)
        except ValueError as error:
            assert 'rail envelope' in str(error),str(error)
            assert pickle.dumps(d)==before
            rows.append(dict(bias_a=bias,result='rejected_without_state_change'))
        else:
            assert d.rail_v>=2.5 and d.reference.samples==1 and d.detector.pending is not None
            rows.append(dict(bias_a=bias,result='accepted',rail_v=d.rail_v))
    assert [r['result'] for r in rows]==['accepted','accepted','rejected_without_state_change','rejected_without_state_change']
    d=setup(.02);pll=PulseClockService(40e6,60,2.4e9);before=pickle.dumps((d,pll))
    try:advance_feedback(d,pll,50e-9,[(0j,0j)],1e6,1e-9)
    except ValueError as error:assert 'rail envelope' in str(error)
    else:raise AssertionError('Overloaded coupled PLL run admitted')
    assert pickle.dumps((d,pll))==before
    report=dict(status='passed',cases=rows,pll_transaction_rollback=True,
        limitations=['Assumed100ohm rail and2.5V floor; not GF180 operating-current limits.',
            'Numerical domain rejection, not implemented brownout detection or managed fault/drain behavior.'])
    (P/'evidence/connected-unified-rail-failure.json').write_text(json.dumps(report,indent=2)+'\n');print(report)

if __name__=='__main__':main()
