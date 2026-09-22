"""Independent waveform/quadrature and subdivision checks for cubic detector."""
import json,cmath
import numpy as np
from scipy.integrate import quad
from chip_model import P
from tx_output_terms import output_terms
from tx_power_detector import PowerDetector
from tx_output_stage import output_envelope
from tx_reconstruction import Reconstruction

def value(terms,t):return sum(a*cmath.exp(p*t) for a,p in terms)
def main():
    f=Reconstruction();f.advance(90e-9,.2+.1j)
    terms=f.terms(-.1+.15j)
    parameters=dict(gain_imbalance_db=.25,phase_error_deg=2.,lo_feedthrough=.0025,cubic=.06)
    expanded=output_terms(terms,**parameters)
    t=np.linspace(0,2e-6,501);z=np.array([value(terms,x) for x in t])
    expected=output_envelope(z,np.ones(len(z)),**parameters)
    actual=np.array([value(expanded,x) for x in t])
    error=float(max(abs(expected-actual)));assert error<1e-12
    d=PowerDetector();end=2e-6;d.advance(end,expanded)
    numeric=quad(lambda u:abs(complex(output_envelope(np.array([value(terms,u)]),np.ones(1),**parameters)[0]))**2*d.pole*np.exp(-d.pole*(end-u)),0,end,epsabs=1e-12,limit=200)[0]
    integration_error=abs(d.value-numeric);assert integration_error<1e-10
    split=PowerDetector();origin=0.
    for at in np.linspace(end/17,end,17):
        shifted=[(a*cmath.exp(p*origin),p) for a,p in expanded]
        split.advance(float(at),shifted);origin=float(at)
    subdivision_error=abs(split.value-d.value);assert subdivision_error<1e-10
    r=dict(status='passed',terms=len(expanded),waveform_error=error,detector_quadrature_error=integration_error,subdivision_error=subdivision_error,
        limitations=['Weak memoryless cubic polynomial; no device noise, thermal memory, supply feedback or RF harmonics.',
        'Expansion does not certify monotonic compression domain for arbitrary inputs; caller must enforce operating envelope.',
        'Targeted local transient, not managed full-chip calibration.'])
    (P/'evidence/connected-tx-output-terms.json').write_text(json.dumps(r,indent=2)+'\n');print(r)
if __name__=='__main__':main()
