"""Exact detector controls and settled calibration of the live reconstruction."""
import json,math
import numpy as np
from scipy.integrate import quad
from chip_model import P
from tx_power_detector import PowerDetector,modulator_terms
from tx_dac_correction_screen import make
from tx_iq_calibration import probes,fit,correct
from tx_output_stage import output_envelope
from rf_quality_screen import quality

def main():
    d=PowerDetector();terms=[(.2+.1j,0j),(.1-.04j,-2e6+3e6j)]
    t=700e-9;d.advance(t,terms)
    expected=quad(lambda u:abs(sum(a*np.exp(p*u) for a,p in terms))**2*d.pole*math.exp(-d.pole*(t-u)),0,t,epsabs=1e-13)[0]
    assert abs(d.value-expected)<1e-12
    d.request();held=d.value
    try:d.read()
    except ValueError:pass
    else:raise AssertionError('Early read accepted')
    d.abort();assert d.value==held and d.pending is None and d.epoch==1
    try:d.read()
    except ValueError:pass
    else:raise AssertionError('Aborted read accepted')
    rows=[]
    for dwell in (100e-9,500e-9,2e-6,5e-6):
        tx=make(12);det=PowerDetector();powers=[];codes=[]
        requested=probes();dc=float(tx.reconstruction.response([0])[0].real)
        # Input probes expressed at settled reconstruction output; DAC codes finite.
        actual=np.round(requested.real/dc*2048)/2048+1j*np.round(requested.imag/dc*2048)/2048
        for z in actual:
            tx.apply_sample(z,tx.time)
            terms=modulator_terms(tx.transmit_terms(),.5,5.,.01+.005j)
            end=tx.time+dwell;det.advance(end,terms);tx.advance(end);det.request()
            terms=modulator_terms(tx.transmit_terms(),.5,5.,.01+.005j)
            end+=det.latency;det.advance(end,terms);tx.advance(end)
            row=det.read();assert not row['overflow'];powers.append(row['power']);codes.append(row['code'])
        try:
            cal=fit(actual*dc,powers)
            test=.2*np.exp(1j*np.arange(1024)*.13)
            y=output_envelope(correct(test,cal),np.ones(len(test)),gain_imbalance_db=.5,phase_error_deg=5.,lo_feedthrough=.01+.005j)
            q=quality(list(test),list(y));error=float(q['corrected_relative_rms'])
            result=dict(error=error,quality=q)
        except ValueError as exc:result=dict(rejected=str(exc))
        rows.append(dict(dwell_s=dwell,total_time_s=det.time,codes=codes,**result))
    assert rows[-1]['error']<.01
    assert rows[0].get('error',1)>.01
    (P/'evidence/connected-tx-power-detector.json').write_text(json.dumps(dict(status='passed',quadrature_error=abs(d.value-expected),cases=rows,
        limitations=['Local continuous filter / linear IQ modulator / square-law detector; no cubic RF output compression.',
        'No host ownership, monitor loading, detector mismatch or full-chip clock disturbance.',
        'Settling sweep characterizes finite assumed poles, not guaranteed physical settling.']),indent=2,default=lambda v:v.item())+'\n')
    print(rows)
if __name__=='__main__':main()
