"""Check declared bounds against continuous nonlinear probe histories."""
import json
from itertools import product
from scipy.integrate import quad
import numpy as np
from chip_model import P
from tx_iq_calibration import probes, fit
from tx_fit_uncertainty import bound
from tx_probe_error_bound import probe_error_bound
from tx_dac_correction_screen import make
from tx_detector_transfer import ImpairedPowerDetector
from tx_output_candidate import PARAMETERS
from tx_output_terms import output_terms


def main():
    # Independent numerical integration checks the coincident-pole limit and
    # both sides of it, including long dwell (underflow-safe evaluation).
    for rate, dwell in product((.5, 1., 1.+1e-12, 2.), (.01, 1., 100.)):
        r=probe_error_bound(amplitude=.1,tail=.2,decay_rate=rate,dwell=dwell,
            tau=1.,initial_interval=(0.,0.),cubic=0.,gain=1.,curvature=0.,
            fullscale=1.,bits=12)
        integral=quad(lambda t: np.exp(-(dwell-t))*(.04*np.exp(-rate*t)
                     +.04*np.exp(-2*rate*t)),0,dwell,epsabs=1e-13)[0]
        assert abs(r['settling']-integral)<1e-11
    cases=[]
    for dwell, curvature in product((1e-6, 2e-6, 4e-6), (0., .2)):
        tx=make(12)
        det=ImpairedPowerDetector(gain=1.1,offset=.0002,curvature=curvature,bits=10)
        dc=float(tx.reconstruction.response([0])[0].real)
        inputs=(np.round(probes().real/dc*2048)+1j*np.round(probes().imag/dc*2048))/2048
        rows=[];observed=[];errors=[]
        for z in inputs:
            tx.apply_sample(z,tx.time)
            affine=dict(PARAMETERS);affine['cubic']=0
            terms=output_terms(tx.transmit_terms(),**affine)
            steady=sum(a for a,p in terms if p == 0)
            transient=[(a,p) for a,p in terms if p != 0]
            assert all(p.real < 0 for a,p in transient)
            # Modal triangle bound is valid for all t>=0, not sampled from a trace.
            tail=sum(abs(a) for a,p in transient)
            rate=min((-p.real for a,p in transient),default=det.pole)
            assert 0 <= det.value <= det.fullscale
            result=probe_error_bound(amplitude=abs(steady),tail=tail,decay_rate=rate,
                dwell=dwell,tau=1/det.pole,initial_interval=(0,det.fullscale),
                cubic=PARAMETERS['cubic'],gain=det.gain,curvature=det.curvature,
                fullscale=det.fullscale,bits=det.bits)
            end=tx.time+dwell
            det.advance(end,output_terms(tx.transmit_terms(),**PARAMETERS));tx.advance(end)
            det.request()
            end=tx.time+det.latency
            det.advance(end,output_terms(tx.transmit_terms(),**PARAMETERS));tx.advance(end)
            sample=det.read();assert not sample['overflow']
            actual=abs(sample['power']-(det.gain*abs(steady)**2+det.offset))
            assert actual <= result['absolute_error']+1e-12,(actual,result)
            rows.append(dict(error=actual,bound=result,tail=tail,decay_rate=rate))
            observed.append(sample['power']);errors.append(result['absolute_error'])
        cal=fit(inputs*dc,np.array(observed),relative_gain=True)
        enclosure=bound(inputs*dc,np.array(observed),np.array(errors),cal)
        cases.append(dict(dwell=dwell,curvature=curvature,probes=rows,fit_uncertainty=enclosure))
    report=dict(status='passed',cases=cases,limitations=[
        'Model modal states and coefficients supply the envelope; no physical process bound is established.',
        'Initial detector interval is assumed and explicitly checked for these histories.',
        'No clipping allowed; gain/offset uncertainty, stochastic noise and coordinate uncertainty excluded.',
        'Conservative error intervals can reject an adequate fit; no managed accuracy gate promoted.'])
    (P/'evidence/connected-tx-probe-error-bound.json').write_text(json.dumps(report,indent=2)+'\n')
    for c in cases:
        u=c['fit_uncertainty']
        print(c['dwell'],c['curvature'],max(r['error'] for r in c['probes']),
              max(r['bound']['absolute_error'] for r in c['probes']),u['relative_axis_spread_bound'])

if __name__=='__main__':main()
