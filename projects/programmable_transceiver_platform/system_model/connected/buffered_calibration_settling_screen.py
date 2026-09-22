"""Readout bandwidth sensitivity through loaded, timed nine-probe calibration."""
import json
import numpy as np
from chip_model import P,encode_iq,decode_iq
from buffered_shared_detector import BufferedSharedDetector
from rf_loaded_detector import LoadedDetector
from rf_loaded_calibration_screen import advance
from tx_dac_correction_screen import make
from tx_calibration_sequence import TxCalibrationSequence
from tx_iq_calibration import probes,correct
from tx_output_stage import output_envelope
from rf_quality_screen import quality
from tx_output_candidate import PARAMETERS

def run(tau,dwell):
    tx=make(12);samples=[]
    def sample(power,time):
        # Declared detector-to-ADC voltage scale; local quantizer only.
        voltage=8*power
        measured=decode_iq(encode_iq(complex(voltage,0),12),12).real/8
        samples.append(dict(time_s=time,detector=detector.value,readout=power,measured=measured))
        return measured,not 0<=power<=.1
    detector=BufferedSharedDetector(sample,readout_tau_s=tau,latency=30e-9)
    load=LoadedDetector(detector=detector)
    dc=float(tx.reconstruction.response([0])[0].real)
    z=probes()/dc;z=(np.round(z.real*2048)+1j*np.round(z.imag*2048))/2048*dc
    seq=TxCalibrationSequence(detector,lambda t,v:tx.apply_sample(v/dc,t),lambda c:None,
        lambda t:setattr(tx,'held',0j),relative_gain=True)
    seq.start(0.,epoch=0,quiet=True,probes=z,dwell=dwell)
    while seq.next_event is not None:
        t=seq.next_event;advance(tx,load,t,PARAMETERS);seq.service(t,epoch=0,quiet=True)
    heldout=None
    if seq.candidate is not None:
        ztest=.15*np.exp(2j*np.pi*np.arange(128)/128)
        corrected=correct(ztest,seq.candidate)
        reference=list(ztest)
        actual=list(output_envelope(corrected,np.ones(128,complex),**PARAMETERS))
        heldout=quality(reference,actual)
    return dict(heldout_static_quality=heldout,readout_tau_s=tau,dwell_s=dwell,state=seq.state,reason=getattr(seq,'reason',None),
        duration_s=tx.time,correction=seq.candidate,samples=samples,
        max_readout_lag=max(abs(s['detector']-s['readout']) for s in samples))

def main():
    rows=[run(tau,dwell) for tau,dwell in [(20e-9,2e-6),(500e-9,2e-6),(2e-6,2e-6),(10e-6,2e-6),(2e-6,10e-6)]]
    assert rows[0]['state']=='ready'
    report=dict(status='characterized',cases=rows,limitations=[
        'Actual local reconstruction, modulator, loaded network and sequence; fixed ideal carrier.',
        'Local signed12bit quantizer, not shared ADC frontend/reference/ownership or noisy whole-chip run.',
        'Held-out static phase-circle check excludes timed DAC playback, autonomous LO and post-switch transients.',
        'Readout time constants are assumed; reverse mux loading and ADC kickback excluded.'])
    (P/'evidence/connected-buffered-calibration-settling.json').write_text(json.dumps(report,indent=2,default=lambda v:v.item())+'\n')
    for r in rows:print({k:v for k,v in r.items() if k not in ('samples','correction')},flush=True)

if __name__=='__main__':main()
