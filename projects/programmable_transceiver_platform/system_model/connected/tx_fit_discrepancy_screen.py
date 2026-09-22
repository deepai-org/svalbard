"""Measure affine-model discrepancy in the implemented nonlinear probe chain.

Truth is used only to audit the model assumption, never as available calibration
telemetry. Measured discrepancies are not future device uncertainty bounds.
"""
import json
import numpy as np
from chip_model import P
from tx_iq_calibration import probes,fit
from tx_calibration_verification import verification_probes
from tx_dac_correction_screen import make
from tx_detector_transfer import ImpairedPowerDetector
from tx_output_candidate import PARAMETERS
from tx_output_stage import output_envelope
from tx_output_terms import output_terms
from tx_fit_uncertainty import bound

def measure(values):
    tx=make(12);det=ImpairedPowerDetector(gain=1.1,offset=.0002,curvature=.2,bits=10)
    dc=float(tx.reconstruction.response([0])[0].real)
    inputs=(np.round(values.real/dc*2048)+1j*np.round(values.imag/dc*2048))/2048
    coords=inputs*dc;measured=[]
    for v in inputs:
        tx.apply_sample(v,tx.time)
        for delay,sample in ((2e-6,True),(det.latency,False)):
            end=tx.time+delay
            det.advance(end,output_terms(tx.transmit_terms(),**PARAMETERS));tx.advance(end)
            if sample:det.request()
        result=det.read();assert not result['overflow'];measured.append(result['power'])
    affine=dict(PARAMETERS);affine['cubic']=0
    truth=1.1*abs(output_envelope(coords,np.ones(len(coords)),**affine))**2+.0002
    return coords,np.array(measured),truth,det.fullscale/((1<<det.bits)-1)/2

def design(z):return np.column_stack((z.real**2,2*z.real*z.imag,z.imag**2,2*z.real,2*z.imag,np.ones(len(z))))
def main():
    z,measured,truth,half_lsb=measure(probes());cal=fit(z,measured,relative_gain=True)
    quant_only=bound(z,measured,half_lsb,cal)
    discrepancy=abs(measured-truth)
    # Retrospective all-probe discrepancy inflation is a diagnostic, not an implementable gate.
    inflated=bound(z,measured,float(max(discrepancy))+half_lsb,cal)
    exact=np.linalg.lstsq(design(z),truth,rcond=None)[0]
    H=np.array([[exact[0],exact[1]],[exact[1],exact[2]]]);C=np.array(cal['matrix'])
    eig=np.linalg.eigvalsh(C.T@H@C)
    def contains(r):
        lo,hi=r['corrected_gram_eigenvalue_bounds'];return bool(lo<=eig[0] and hi>=eig[-1])
    assert max(discrepancy)>half_lsb*10
    assert contains(inflated)
    other,obs,actual,_=measure(verification_probes())
    fitted=np.linalg.lstsq(design(z),measured,rcond=None)[0]
    validation_residual=float(max(abs(obs-design(other)@fitted)))
    r=dict(status='characterized',half_lsb=half_lsb,training_max_affine_discrepancy=float(max(discrepancy)),
        independent_max_fit_residual=validation_residual,quantization_only=quant_only,
        quantization_only_contains_true_gram=contains(quant_only),diagnostic_inflated=inflated,
        true_corrected_gram_eigenvalues=eig.tolist(),
        limitations=['Truth-assisted assumption audit only; no detector error bound established by finite probes.',
        'Independent probes test different amplitudes/phases but cannot exclude arbitrary unobserved nonlinearity.',
        'One reconstruction, dwell and transfer setting; full operating-envelope bounds remain open.'])
    (P/'evidence/connected-tx-fit-discrepancy.json').write_text(json.dumps(r,indent=2)+'\n')
    print('half LSB',half_lsb,'discrepancy',max(discrepancy),'validation',validation_residual,'quant enclosure',contains(quant_only))
if __name__=='__main__':main()
