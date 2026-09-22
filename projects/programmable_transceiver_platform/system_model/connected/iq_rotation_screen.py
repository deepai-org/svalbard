"""Check I/Q correction ordering; known impairment inverse is diagnostic only."""
import hashlib
import json
from pathlib import Path
import numpy as np
from rf_blocks import iq_error


def run():
    fs=20e6
    t=np.arange(4096)/fs
    rng=np.random.default_rng(677)
    labels=rng.integers(0,4,len(t))
    x=((1-2*(labels&1))+1j*(1-2*((labels>>1)&1)))/np.sqrt(2)
    train=np.arange(512)
    test=np.arange(1024,len(t))
    cases=[]
    for gain in (-.1,.1):
        for phase in (-5,5):
            phi=np.deg2rad(phase)
            # Independently derived widely-linear coefficients y=a*z+b*conj(z).
            a=((1+gain)+(1-gain)*np.cos(phi)+1j*np.sin(phi))/2
            b=((1+gain)-(1-gain)*np.cos(phi)+1j*np.sin(phi))/2
            determinant=abs(a)**2-abs(b)**2
            assert determinant>.8
            for offset in (-100e3,0,100e3):
                rotation=np.exp(2j*np.pi*offset*t)
                z=x*rotation
                y,_=iq_error(z,gain,phase)
                assert np.max(abs(y-(a*z+b*z.conj())))<1e-14
                derotated=y/rotation
                predicted=a*x+b*x.conj()/rotation**2
                assert np.max(abs(derotated-predicted))<1e-14
                # A fixed real matrix fitted after derotation cannot in general
                # remove an image term rotating at twice the frequency offset.
                features=np.column_stack((derotated.real,derotated.imag))
                target=np.column_stack((x.real,x.imag))
                fitted=np.linalg.lstsq(features[train],target[train],rcond=None)[0]
                wrong=features[test]@fitted
                wrong_rms=float(np.sqrt(np.mean(np.sum((wrong-target[test])**2,axis=1))))
                # Exact known-parameter inverse before frequency correction.
                recovered=(a.conjugate()*y-b*y.conj())/determinant/rotation
                inverse_rms=float(np.sqrt(np.mean(abs(recovered[test]-x[test])**2)))
                assert inverse_rms<1e-14
                if offset==0:
                    assert wrong_rms<1e-14
                else:
                    assert wrong_rms>.1
                cases.append(dict(gain_error=gain,phase_error_deg=phase,offset_hz=offset,
                    fixed_post_derotation_fit_rms=wrong_rms,
                    known_inverse_before_derotation_rms=inverse_rms))
    p=Path(__file__).resolve().parents[2]
    report=dict(status='ordering_identity_and_negative_controls_passed',cases=cases,
        training_samples=len(train),held_out_samples=len(test),
        limitations=['Synthetic memoryless mismatch; no filters, ADC, noise or transport.',
                     'Exact inverse uses known impairment parameters: not achieved calibration.',
                     'Actual estimator must identify imbalance before derotation or include rotating image basis.'],
        source_hashes={str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest()
                       for f in (Path(__file__).resolve(),Path(__file__).with_name('rf_blocks.py').resolve())})
    (p/'evidence/connected-iq-rotation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(cases=len(cases),maximum_static_fit_rms=max(c['fixed_post_derotation_fit_rms'] for c in cases),maximum_known_inverse_rms=max(c['known_inverse_before_derotation_rms'] for c in cases))))


if __name__=='__main__':
    run()
