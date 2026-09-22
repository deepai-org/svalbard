"""Unknown monitor gain must not dictate overall DAC gain."""
import json
import numpy as np
from chip_model import P
from tx_iq_calibration import probes,fit
from tx_dac_correction import DacCorrection
from tx_output_stage import output_envelope
from rf_monitor_load import solve
from rf_quality_screen import quality

def main():
    probe=probes();params=dict(gain_imbalance_db=.25,phase_error_deg=2.,lo_feedthrough=.0025)
    training=abs(output_envelope(probe,np.ones(len(probe)),**params))**2
    rows=[];matrices=[]
    z=.22*np.exp(1j*np.arange(1024)*.13)+.09*np.exp(-1j*np.arange(1024)*.37)
    for gain in (.01,.1,.5604789528018422,1.,10.):
        cal=fit(probe,training*gain,relative_gain=True);matrices.append(cal['matrix'])
        actuator=DacCorrection(cal,12);corrected=np.array([actuator(0,v) for v in z])
        y=output_envelope(corrected,np.ones(len(z)),**params)*solve(2.412e9)['relative_output']
        q=quality(list(z),list(y));assert q['corrected_relative_rms']<.003
        assert .98<q['gain_magnitude']<1.01
        actuator(0,.8+.8j)
        rows.append(dict(monitor_power_gain=gain,quality=q,calibration=cal,high_sample_accepted=True))
    assert all(np.array_equal(matrices[0],m) for m in matrices)
    # Constant monitor offset is absorbed by the fitted intercept, absent clipping.
    biased=fit(probe,training*.56+.0002,relative_gain=True)
    assert np.array_equal(biased['matrix'],matrices[0])
    # Actual common TX gain remains unknown: relative correction must not hide it.
    actual_gain=.7
    cal=fit(probe,training*.56*actual_gain**2,relative_gain=True)
    assert np.array_equal(cal['matrix'],matrices[0])
    r=dict(status='passed',cases=rows,monitor_offset_control=biased,
        limitations=['Exact unquantized power-gain invariance; finite ADC/settling/readout curvature must be requalified.',
        'Relative gain correction does not regulate absolute RF output power or remove actuator headroom limits.',
        'Unit determinant is a policy choice preserving geometric mean gain; not a measured circuit property.'])
    (P/'evidence/connected-tx-relative-calibration.json').write_text(json.dumps(r,indent=2,default=lambda v:v.item())+'\n')
    print('Passed five monitor gains, offset invariance, retained common gain and DAC headroom')
if __name__=='__main__':main()
