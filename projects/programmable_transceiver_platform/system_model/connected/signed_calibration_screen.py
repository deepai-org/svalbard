"""Signed measurement fitting and controller boundaries, without RF startup."""
import json
from types import SimpleNamespace
import numpy as np
from chip_model import P,encode_iq
from tx_iq_calibration import probes,fit
from shared_tx_detector import SharedAdcDetector,SharedAdcLoadedTxChip
from tx_calibration_sequence import TxCalibrationSequence

def main():
    z=probes();p=abs(z)**2-1e-4
    assert p[0]<0
    cal=fit(z,p,relative_gain=True,signed_observations=True)
    assert np.allclose(cal['matrix'],np.eye(2)) and np.allclose(cal['offset'],0)
    # Additive measurement pedestal affects the fitted intercept, not H or h.
    ref=fit(z,p+.01,relative_gain=True)
    assert cal['matrix']==ref['matrix'] and cal['offset']==ref['offset']
    for values,signed in [(p,False),(-abs(z)**2,True),(np.full(9,np.nan),True)]:
        try:fit(z,values,relative_gain=True,signed_observations=signed)
        except ValueError:pass
        else:raise AssertionError('Invalid input/curvature admitted')
    # Shared ADC predicate: preserve a negative signed code, reject physical
    # overrange and quantizer clipping independently. No ideal ADC substitution
    # in a whole-chip run is implied by this boundary stub.
    for power,clip,expected in [(0,False,False),(.101,False,True),(-.001,False,True),(0,True,True)]:
        c=SimpleNamespace(time=0.,tx=SimpleNamespace(time=0.),tx_cal=SimpleNamespace(busy=True),
            quiet=lambda:True,adc_pending=[],maintenance_pending=None,tx_detector=SimpleNamespace(fullscale=.1),
            adc_diagnostics={'clipped_samples':0},tx_adc_samples=0)
        def convert(value):
            c.adc_diagnostics['clipped_samples']+=int(clip)
            return encode_iq(-.001+0j,12)
        c.convert_adc=convert
        value,invalid=SharedAdcLoadedTxChip._sample_detector(c,power,0.)
        assert value<0 and invalid==expected and c.tx_adc_samples==1
    for overflow in (False,True):
        readings=iter(p);commits=[]
        d=SharedAdcDetector(lambda value,time:(float(next(readings)),overflow))
        s=TxCalibrationSequence(d,lambda t,z:None,commits.append,lambda t:None,relative_gain=True)
        s.start(0.,epoch=1,quiet=True,probes=z)
        while s.next_event is not None:
            t=s.next_event;d.advance(t,[(0j,0j)]);s.service(t,epoch=1,quiet=True)
        if overflow:
            assert s.state=='cancelled' and not commits
        else:
            assert s.state=='ready' and s.powers[0]<0
            s.accept(s.time,epoch=1,generation=s.generation,quiet=True)
            assert s.valid and len(commits)==1
    report=dict(status='passed',negative_observation_preserved=float(p[0]),
        checks=['signed pedestal invariance','negative curvature rejected','nonfinite observations rejected',
                'physical overrange and ADC clipping rejected','signed controller commit','overflow cancellation'],
        limitations=['Local fit, readout predicate and sequence tests; integrated noisy quality must be rerun.'])
    (P/'evidence/connected-signed-calibration.json').write_text(json.dumps(report,indent=2)+'\n')
    print(report)

if __name__=='__main__':main()
