"""Independent probes, bounded observer error, and power-verification blind spots."""
import json
import numpy as np
from chip_model import P
from tx_iq_calibration import probes,fit,correct
from tx_output_stage import output_envelope
from tx_calibration_verification import verification_probes,assess

def main():
    training=probes();test=verification_probes()
    params=dict(gain_imbalance_db=.5,phase_error_deg=5.,lo_feedthrough=.01+.005j)
    cal=fit(training,abs(output_envelope(training,np.ones(len(training)),**params))**2)
    y=output_envelope(correct(test,cal),np.ones(len(test)),**params)
    good=assess(test,abs(y)**2,absolute_error_bound=1e-5)
    assert good['power_verified'] and not good['waveform_verified']
    bad=assess(test,abs(output_envelope(test,np.ones(len(test)),**params))**2,absolute_error_bound=1e-5)
    assert not bad['power_verified']
    uncertain=assess(test,abs(y)**2,absolute_error_bound=.001)
    assert not uncertain['power_verified']
    # Detector saturation/nonlinear radial response must not be mistaken for a good fit.
    compressed=assess(test,abs(y)**2*(1-3*abs(y)**2),absolute_error_bound=1e-5)
    assert not compressed['power_verified']
    # Explicit counterexample: identical measured powers, gross waveform change.
    conjugate=assess(test,abs(test.conjugate())**2,absolute_error_bound=0)
    phase_distorted=test*np.exp(1j*12*abs(test)**2)
    phase=assess(test,abs(phase_distorted)**2,absolute_error_bound=0)
    assert conjugate['power_verified'] and phase['power_verified']
    quantized=[]
    for bits in (8,10,12):
        step=.1/((1<<bits)-1)
        power=np.rint(abs(y)**2/step)*step
        result=assess(test,power,absolute_error_bound=step/2)
        assert result['power_verified']==(bits>=10)
        quantized.append(dict(bits=bits,**result))
    report=dict(quantized=quantized,status='passed',corrected=good,uncorrected=bad,uncertain=uncertain,
        radial_nonlinearity=compressed,blind_spots=dict(conjugation=conjugate,amplitude_dependent_phase=phase),
        limitations=['Instantaneous synthetic verification measurements, not yet timed chip observations.',
        'Power verification is necessary under this candidate contract but not sufficient for modulation quality.',
        '1e-5 absolute observer bound and 4% radial-power limit are provisional assumptions.'])
    (P/'evidence/connected-tx-calibration-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(report)
if __name__=='__main__':main()
