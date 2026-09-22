"""Timed calibration and independent playback through one loaded RF network."""
import json
import numpy as np
from chip_model import P
from rf_loaded_detector import LoadedDetector
from tx_dac_correction_screen import make
from tx_dac_correction import DacCorrection
from tx_calibration_sequence import TxCalibrationSequence
from tx_iq_calibration import probes
from tx_output_terms import output_terms
from tx_output_candidate import PARAMETERS
from tx_power_detector import PowerDetector
from rf_quality_screen import quality

def advance(tx,load,end,parameters):
    load.advance(end,output_terms(tx.transmit_terms(),**parameters) or [(0j,0j)])
    tx.advance(end)

def calibrate(bits):
    tx=make(12);load=LoadedDetector(detector=PowerDetector(bits=bits))
    dc=float(tx.reconstruction.response([0])[0].real)
    z=probes()/dc;z=(np.round(z.real*2048)+1j*np.round(z.imag*2048))/2048*dc
    def write(time,value):tx.apply_sample(value/dc,time)
    def commit(cal):tx.sample_correction=DacCorrection(cal,12,dc)
    def release(time):tx.advance(time);tx.held=0j
    seq=TxCalibrationSequence(load.detector,write,commit,release,relative_gain=True)
    generation=seq.start(0.,epoch=0,quiet=True,probes=list(z))
    peak=0.
    while seq.next_event is not None:
        time=seq.next_event
        advance(tx,load,time,PARAMETERS)
        peak=max(peak,abs(load.network.voltage[1]))
        seq.service(time,epoch=0,quiet=True)
    assert seq.state=='ready'
    seq.accept(tx.time,epoch=0,generation=generation,quiet=True)
    assert seq.valid
    return tx,load,seq,peak

def main():
    rows=[]
    for bits in (10,12):
        tx,load,seq,peak=calibrate(bits)
        # Preserve calibrated analog charge through output-enable transition.
        retained=load.network.voltage.copy();load.network.configure(True,False)
        assert np.array_equal(retained,load.network.voltage)
        ideal=make(12);ideal_load=LoadedDetector();ideal_load.network.configure(True,False)
        raw=make(12);raw_load=LoadedDetector();raw_load.network.configure(True,False)
        origin=tx.time
        advance(ideal,ideal_load,origin,{})
        advance(raw,raw_load,origin,PARAMETERS)
        reference=[];corrected=[];uncorrected=[]
        for i in range(160):
            t=origin+i/40e6
            value=0j if i<32 else .15*np.exp(2j*np.pi*1.3e6*(t-origin))+.1*np.exp(-2j*np.pi*3.1e6*(t-origin))
            for a,b,params in ((tx,load,PARAMETERS),(ideal,ideal_load,{}),(raw,raw_load,PARAMETERS)):
                advance(a,b,t,params)
                a.apply_sample(value,t)
                advance(a,b,t+20e-9,params)
            reference.append(complex(ideal_load.network.voltage[1]))
            corrected.append(complex(load.network.voltage[1]))
            uncorrected.append(complex(raw_load.network.voltage[1]))
        q=quality(reference[32:],corrected[32:]);before=quality(reference[32:],uncorrected[32:])
        rows.append(dict(detector_bits=bits,calibration=seq.candidate,probe_powers=seq.powers,
            sampled_calibration_pad_peak=peak,corrected_quality=q,uncorrected_quality=before))
        print(bits,q['corrected_relative_rms'],before['corrected_relative_rms'],flush=True)
    report=dict(status='characterized',cases=rows,limitations=[
        'Local timed calibration/controller and electrical network; not managed full-chip lifecycle or shared ADC ownership.',
        'Fixed ideal carrier and prescribed Thevenin source, with actual reconstruction and nonlinear modulator terms.',
        'Switch transition retains charge but waveform scoring follows32 settling samples; startup remains separate.',
        'Monitor and pad use one network state; no normalization by hidden monitor gain.',
        'Finite multitone record and assumed electrical parameters; not a physical or protocol certificate.'])
    (P/'evidence/connected-rf-loaded-calibration.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
