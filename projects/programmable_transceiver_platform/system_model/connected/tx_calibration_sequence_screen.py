"""Joined filter/detector/controller sequence and cancellation boundaries."""
import json
import numpy as np
from chip_model import P
from tx_dac_correction_screen import make
from tx_power_detector import PowerDetector,modulator_terms
from tx_calibration_sequence import TxCalibrationSequence
from tx_dac_correction import DacCorrection
from tx_iq_calibration import probes

def fixture():
    tx=make(12);det=PowerDetector();commits=[];dc=float(tx.reconstruction.response([0])[0].real)
    def write(t,z):
        # Sequence probes are the physically attainable settled output coordinates.
        tx.apply_sample(z/dc,t)
    def commit(cal):
        tx.sample_correction=DacCorrection(cal,12,dc);commits.append(cal)
    def release(t):tx.advance(t);tx.held=0j
    seq=TxCalibrationSequence(det,write,commit,release)
    values=probes();codes=np.round(values.real/dc*2048)/2048+1j*np.round(values.imag/dc*2048)/2048
    seq.start(0.,epoch=4,quiet=True,probes=list(codes*dc))
    def advance():
        t=seq.next_event
        det.advance(t,modulator_terms(tx.transmit_terms(),.5,5.,.01+.005j));tx.advance(t)
        seq.service(t,epoch=4,quiet=True)
    return tx,det,seq,commits,advance

def main():
    tx,det,s,commits,step=fixture();events=0
    while s.next_event is not None:step();events+=1
    assert s.state=='ready' and len(s.powers)==9 and not commits and tx.held==0
    for kwargs in (dict(epoch=3,generation=s.generation,quiet=True),dict(epoch=4,generation=s.generation-1,quiet=True),dict(epoch=4,generation=s.generation,quiet=False)):
        try:s.accept(s.time,**kwargs)
        except ValueError:pass
        else:raise AssertionError('Invalid commit accepted')
    state=tx.reconstruction.states.copy()
    s.accept(s.time,epoch=4,generation=s.generation,quiet=True)
    assert len(commits)==1 and s.valid and np.array_equal(state,tx.reconstruction.states)
    s.service(s.time,epoch=5,quiet=True)
    assert not s.valid and s.state=='cancelled'
    cancelled=[]
    for count in (0,1,2,17,18):
        tx,det,s,commits,step=fixture()
        for _ in range(count):step()
        charge=det.value;state=tx.reconstruction.states.copy()
        s.service(s.time,epoch=5,quiet=True)
        assert s.state=='cancelled' and not s.valid and not commits and det.pending is None
        assert det.value==charge and np.array_equal(state,tx.reconstruction.states) and tx.held==0
        cancelled.append(count)
    tx,det,s,commits,step=fixture();s.service(0.,epoch=4,quiet=False)
    assert s.state=='cancelled' and not commits
    report=dict(status='passed',sequence_events=events,sequence_duration_s=18.9e-6,cancel_after_events=cancelled,
        limitations=['Local controller composition; parent whole-chip command scheduler and ownership predicates not connected yet.',
        'Release zeroes DAC hold; physical RF output isolation remains a separate obligation.',
        'Commit means coefficients installed, not independent residual-quality qualification.'])
    (P/'evidence/connected-tx-calibration-sequence.json').write_text(json.dumps(report,indent=2)+'\n')
    print(report)
if __name__=='__main__':main()
