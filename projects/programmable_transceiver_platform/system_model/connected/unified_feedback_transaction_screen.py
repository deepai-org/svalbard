"""Rollback includes charged reference, pending ADC readout and live identities."""
import pickle,json
from chip_model import P
from driver_feedback_transaction_screen import FailsLate
from rf_driver_transient import CoupledDriver
from driver_sensitive_reference import DriverSensitiveReference
from buffered_shared_detector import BufferedSharedDetector
from pulse_clock_service import PulseClockService
from driver_pll_feedback import advance_feedback

def sample(value,time):return value,False

def setup(cls):
    r=DriverSensitiveReference(driver_v_per_v=.05)
    r.sample(0,.2+.1j);r.dac_update(0,.1,1e-12)
    detector=BufferedSharedDetector(sample);detector.value=.003;detector.readout_value=.002
    detector.request()
    return cls(reference=r,detector=detector),PulseClockService(40e6,60,2.4e9)

def main():
    d,p=setup(FailsLate);identities=(d.network,d.detector,d.reference)
    before=pickle.dumps((d,p))
    try:advance_feedback(d,p,5e-9,[(.2+0j,0j)],1e6,1e-9)
    except ValueError as e:assert str(e)=='Injected late integration failure'
    else:raise AssertionError('Expected failure')
    assert pickle.dumps((d,p))==before
    assert all(a is b for a,b in zip(identities,(d.network,d.detector,d.reference)))
    d,p=setup(CoupledDriver);identities=(d.network,d.detector,d.reference)
    pending=d.detector.pending;charge=d.reference.charge
    advance_feedback(d,p,2e-9,[(.2+0j,0j)],1e6,1e-9)
    assert d.detector.pending==pending and d.reference.charge==charge
    assert d.reference.samples==d.reference.dac_updates==1
    assert d.time==p.time==d.detector.time==d.reference.time==2e-9
    assert all(a is b for a,b in zip(identities,(d.network,d.detector,d.reference)))
    report=dict(status='passed',checks=['late failure rolls back all charged states','pending sample unchanged',
        'conversion charge/counters unchanged by analog advance','all public identities retained','all clocks aligned'],
        limitations=['Local transaction test; full managed calibration run remains separate.'])
    (P/'evidence/connected-unified-feedback-transaction.json').write_text(json.dumps(report,indent=2)+'\n');print(report)

if __name__=='__main__':main()
