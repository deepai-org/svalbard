"""Detector transfer uncertainty sweep; independent verification waveform."""
import json,itertools
import numpy as np
from chip_model import P
from tx_detector_transfer import ImpairedPowerDetector
from tx_iq_calibration import probes,fit,correct
from tx_output_stage import output_envelope
from tx_output_candidate import PARAMETERS
from rf_quality_screen import quality

def main():
    rows=[];probe=probes();test=.16*np.exp(1j*np.arange(1024)*.17)+.07*np.exp(-1j*np.arange(1024)*.31)
    for gain,offset,curve in itertools.product((.9,1.,1.1),(-.0002,0.,.0002),(-.2,0.,.2)):
        detector=ImpairedPowerDetector(gain=gain,offset=offset,curvature=curve)
        powers=[];invalid=False
        for value in output_envelope(probe,np.ones(len(probe)),**PARAMETERS):
            # Held local RF envelope: finite detector memory retained across probes.
            detector.advance(detector.time+2e-6,[(complex(value),0j)])
            detector.request();detector.advance(detector.time+detector.latency,[(complex(value),0j)])
            sample=detector.read();invalid|=sample['overflow'];powers.append(sample['power'])
        row=dict(gain=gain,offset=offset,curvature=curve,rail_rejected=invalid)
        if not invalid:
            cal=fit(probe,powers)
            y=output_envelope(correct(test,cal),np.ones(len(test)),**PARAMETERS)
            row['quality']=quality(list(test),list(y))
        rows.append(row)
    assert all(r['rail_rejected'] for r in rows if r['offset']<0)
    assert any(not r['rail_rejected'] for r in rows)
    for kwargs in (dict(gain=0),dict(curvature=-.6),dict(offset=float('nan'))):
        try:ImpairedPowerDetector(**kwargs)
        except ValueError:pass
        else:raise AssertionError('Invalid transfer accepted')
    errors=[r['quality']['corrected_relative_rms'] for r in rows if 'quality' in r]
    report=dict(status='passed',cases=rows,accepted_min_error=float(min(errors)),accepted_max_error=float(max(errors)),
        limitations=['Local held-probe detector followed by independent multitone, not full-chip noise/clock replay.',
        'Gain/offset/curvature are assumed normalized readout uncertainties, not GF180 measurements.',
        'Negative readout clipping rejects; no silent clamp-and-fit path.'])
    (P/'evidence/connected-tx-detector-transfer.json').write_text(json.dumps(report,indent=2,default=lambda v:v.item())+'\n')
    print('cases',len(rows),'rejected',sum(r['rail_rejected'] for r in rows),'accepted error',min(errors),max(errors))
if __name__=='__main__':main()
