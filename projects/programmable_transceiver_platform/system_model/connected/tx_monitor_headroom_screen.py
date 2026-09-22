"""Connect passive monitor attenuation to finite power calibration and DAC range."""
import json
import numpy as np
from chip_model import P
from rf_monitor_load import solve
from tx_iq_calibration import probes,fit
from tx_dac_correction import DacCorrection
from tx_output_stage import output_envelope
from tx_power_detector import PowerDetector
from rf_quality_screen import quality

def main():
    network=solve(2.412e9);pad=network['relative_output']
    tap=network['monitor']/network['output'];ratio=abs(tap)**2
    params=dict(gain_imbalance_db=.25,phase_error_deg=2.,lo_feedthrough=.0025)
    probe=probes();detector=PowerDetector(bits=12,fullscale=.1)
    powers=[]
    for value in output_envelope(probe,np.ones(len(probe)),**params)*pad*tap:
        detector.advance(detector.time+2e-6,[(complex(value),0j)])
        detector.request();detector.advance(detector.time+detector.latency,[(complex(value),0j)])
        result=detector.read();assert not result['overflow'];powers.append(result['power'])
    rows=[]
    test=.22*np.exp(1j*np.arange(1024)*.13)+.09*np.exp(-1j*np.arange(1024)*.37)
    for name,estimate in [('ignored',1.),('exact',ratio),('estimate_low',ratio*.9),('estimate_high',ratio*1.1)]:
        cal=fit(probe,np.array(powers)/estimate)
        actuator=DacCorrection(cal,12)
        corrected=np.array([actuator(0,z) for z in test])
        measured=output_envelope(corrected,np.ones(len(test)),**params)*pad
        q=quality(list(test),list(measured))
        high_ok=True
        try:actuator(0,.8+.8j)
        except ValueError:high_ok=False
        rows.append(dict(normalization=name,power_ratio_estimate=estimate,
            quality=q,high_sample_accepted=high_ok,coefficient_matrix=cal['matrix']))
    assert rows[0]['quality']['gain_magnitude']>1.25 and not rows[0]['high_sample_accepted']
    assert abs(rows[1]['quality']['gain_magnitude']-1)<.01 and rows[1]['high_sample_accepted']
    assert rows[0]['quality']['screen_pass'] # Deliberate normalized-quality false reassurance.
    assert all(r['quality']['screen_pass'] for r in rows)
    r=dict(status='passed',actual_monitor_to_pad_power_ratio=ratio,cases=rows,
        limitations=['Narrowband carrier transfer with local finite detector; no full-chip supply or package model.',
        'Exact normalization is an oracle control; actual ratio must be independently characterized or bounded.',
        '10% ratio errors are assumed, not measured. Absolute output-amplitude tolerance is not yet specified.'])
    (P/'evidence/connected-tx-monitor-headroom.json').write_text(json.dumps(r,indent=2,default=lambda v:v.item())+'\n')
    print([(x['normalization'],x['quality']['gain_magnitude'],x['high_sample_accepted']) for x in rows])
if __name__=='__main__':main()
