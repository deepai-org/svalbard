"""Timed calibration with driver/supply/readout feedback and independent DC probes."""
import json
import numpy as np
from chip_model import P,encode_iq,decode_iq
from tx_dac_correction_screen import make
from tx_dac_correction import DacCorrection
from tx_calibration_sequence import TxCalibrationSequence
from tx_iq_calibration import probes,correct
from tx_output_candidate import PARAMETERS
from tx_output_stage import output_envelope
from buffered_shared_detector import BufferedSharedDetector
from rf_driver_transient import CoupledDriver
from reconstructed_driver_supply import advance
from rf_quality_screen import quality

def main():
    tx=make(12);reads=[]
    def sample(power,time):
        code=encode_iq(complex(8*power,0),12)
        measured=decode_iq(code,12).real/8
        reads.append(dict(time_s=time,power=power,measured=measured,rail_v=driver.rail_v))
        return measured,not 0<=power<=.1
    detector=BufferedSharedDetector(sample,readout_tau_s=20e-9,latency=30e-9)
    driver=CoupledDriver(detector=detector)
    dc=float(tx.reconstruction.response([0])[0].real)
    z=probes()/dc;z=(np.round(z.real*2048)+1j*np.round(z.imag*2048))/2048*dc
    seq=TxCalibrationSequence(detector,lambda t,v:tx.apply_sample(v/dc,t),
        lambda cal:setattr(tx,'sample_correction',DacCorrection(cal,12,dc)),
        lambda t:setattr(tx,'held',0j),relative_gain=True)
    gen=seq.start(0.,epoch=0,quiet=True,probes=z)
    while seq.next_event is not None:
        t=seq.next_event;advance(tx,driver,t,PARAMETERS,max_step=10e-9)
        seq.service(t,epoch=0,quiet=True)
    assert seq.state=='ready' and len(reads)==9
    seq.accept(tx.time,epoch=0,generation=gen,quiet=True)
    driver.network.configure(True,False)
    test=.15*np.exp(2j*np.pi*np.arange(128)/128)
    def static(values):
        out=[]
        commands=output_envelope(values,np.ones(len(values),complex),**PARAMETERS)
        for command in commands:
            op=driver.law.operating_point(driver.network,command,driver.r)
            source=driver.law.source(command,op['rail_v'])
            out.append(complex(driver.network.steady(source)[1]))
        return out
    raw=quality(list(test),static(test));q=quality(list(test),static(correct(test,seq.candidate)))
    report=dict(status='characterized',sequence_committed=seq.valid,reads=reads,correction=seq.candidate,
        uncorrected_static_quality=raw,corrected_static_quality=q,
        limitations=['Timed local reconstruction/driver/network/rail/detector sequence; local12bit quantizer only.',
            'Held-out static output points include self-consistent rail loading but exclude playback transients.',
            'Autonomous LO, shared reference and managed whole-chip ownership remain unconnected in this local test.',
            'Ready/commit does not certify waveform quality; driver and detector laws are assumptions.'])
    (P/'evidence/connected-coupled-driver-calibration.json').write_text(json.dumps(report,indent=2,default=lambda v:v.item())+'\n')
    print('Static error raw/corrected',raw['corrected_relative_rms'],q['corrected_relative_rms'],flush=True)

if __name__=='__main__':main()
