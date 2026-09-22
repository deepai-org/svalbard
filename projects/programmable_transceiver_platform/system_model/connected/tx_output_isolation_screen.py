"""Connected calibration, transmission and stop checks for finite isolation."""
import json, math
from chip_model import P
from managed_resources import command
from tx_output_isolation import OutputIsolation, IsolatedTxCalibrationChip
from tx_calibration_inflight_screen import prepared
from tx_envelope_observer import observe_tx, tx_components
from tx_output_stage import output_envelope
import numpy as np

def raw(c):
    z,r=tx_components(c,2412000000)
    return complex(output_envelope(np.array([z]),np.array([r]),**c.tx_output_parameters)[0])

def main():
    # Exact subdivision/retargeting must preserve gate charge, never teleport it.
    a=OutputIsolation();b=OutputIsolation()
    a.command(True,0);b.command(True,0)
    for t in (5e-9,10e-9,15e-9):b.command(True,t)
    assert abs(a.at(30e-9)-b.at(30e-9))<1e-15
    v=a.at(30e-9);a.command(False,30e-9)
    assert a.at(30e-9)==v and a.off<a.at(50e-9)<v
    assert math.isclose(a.at(1e-6),a.off,abs_tol=1e-15)
    for options in ({'off_amplitude':0},{'tau_s':0},{'on_amplitude':2}):
        try:OutputIsolation(**options)
        except ValueError:pass
        else:raise AssertionError('Invalid isolation parameters admitted')
    c=IsolatedTxCalibrationChip(watchdog_s=1e-3)
    assert command(c,'rf_coarse_start',2412000000)['accepted']
    c.advance(c.time+50e-6)
    assert command(c,'tx_cal_start')['accepted']
    calibration=[]
    while c.tx_cal.next_event is not None:
        c.advance(c.tx_cal.next_event)
        assert not c.tx_output_isolation.enabled
        value=observe_tx(c,2412000000)
        assert abs(value-c.tx_output_isolation.off*raw(c))<1e-15
        calibration.append(abs(value))
    assert c.tx_cal.state=='ready' and max(c.tx_cal.powers)>.01
    rows=[]
    for cause in ('stop','reference_loss','tx_cal_abort'):
        c=prepared(IsolatedTxCalibrationChip)
        assert not c.tx_output_isolation.enabled
        assert c.tx.accept(.2+.1j)
        c.schedule(1,c.time+100e-9)
        c.advance(c.time+2e-6)
        assert c.tx_output_isolation.enabled
        assert abs(observe_tx(c,2412000000)-raw(c))<1e-14
        before=observe_tx(c,2412000000);states=c.tx.reconstruction.states.copy()
        if cause=='reference_loss':c.set_reference(False,c.time)
        else:c.execute_management(cause,0,c.time)
        assert not c.tx_output_isolation.enabled and c.state=='draining'
        assert all(states==c.tx.reconstruction.states)
        assert abs(abs(observe_tx(c,2412000000))-abs(before))<1e-12
        origin=c.time;measurements=[]
        for delay in (20e-9,200e-9,2e-6,10e-6):
            c.advance(origin+delay)
            transfer=c.tx_pad_transfer(c.time)
            assert abs(transfer-(.001+.999*math.exp(-delay/20e-9)))<1e-10
            assert abs(observe_tx(c,2412000000)-transfer*raw(c))<1e-15
            measurements.append(dict(delay=delay,transfer=transfer,pad_magnitude=abs(observe_tx(c,2412000000))))
        assert 2e-6<measurements[-1]['pad_magnitude']<3e-6
        rows.append(dict(cause=cause,measurements=measurements))
    report=dict(status='passed',calibration_peak_pad_magnitude=max(calibration),cases=rows,
        assumptions=dict(off_amplitude=.001,on_amplitude=1.,tau_s=20e-9),
        limitations=['Experimental subclass only; default/full-chain quality profiles not promoted.',
            'Detector is upstream of isolation, unlike a pad-side detector; topology is explicit but unqualified.',
            'No additive bypass leakage, charge injection, impedance, package coupling or supply-current model.',
            'First DAC completion opens the gate; startup waveform quality and recovery reopening remain untested.',
            '60dB off attenuation and20ns time constant are declared sensitivity assumptions, not GF180 evidence.'])
    (P/'evidence/connected-tx-output-isolation.json').write_text(json.dumps(report,indent=2)+'\n')
    print('calibration pad peak',max(calibration))
    for r in rows:print(r['cause'],r['measurements'][-1])

if __name__=='__main__':main()
