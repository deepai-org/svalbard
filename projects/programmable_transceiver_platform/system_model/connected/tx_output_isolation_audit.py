"""Expose output-isolation gaps in the actual managed TX observation path.

Characterization only: no synthetic gate is inserted to make quiet output zero.
"""
import json
from chip_model import P
from managed_resources import command
from tx_calibration_chip import TxCalibrationChip
from tx_calibration_inflight_screen import prepared
from tx_envelope_observer import observe_tx

CARRIER=2412000000

def snapshot(c,label):
    z=observe_tx(c,CARRIER)
    return dict(label=label,time=c.time,state=c.state,calibration=c.tx_cal.state,
        held_real=c.tx.held.real,held_imag=c.tx.held.imag,
        reconstruction_state_norm=float(sum(abs(c.tx.reconstruction.states))),
        output_magnitude=abs(z),dac_updates=c.dac_pipeline_updates)

def main():
    c=TxCalibrationChip(watchdog_s=1e-3)
    assert command(c,'rf_coarse_start',CARRIER)['accepted']
    c.advance(c.time+50e-6)
    calibration=[snapshot(c,'before calibration')]
    assert command(c,'tx_cal_start')['accepted']
    # Follow actual converter events. Probe output must not be assumed isolated
    # merely because the management FSM reports quiet.
    while c.tx_cal.next_event is not None:
        c.advance(c.tx_cal.next_event)
        calibration.append(snapshot(c,'calibration event'))
    assert c.tx_cal.state=='ready'
    rows=[]
    for cause in ('stop','reference_loss'):
        c=prepared()
        assert c.tx.accept(.2+.1j)
        c.schedule(1,c.time+100e-9);c.advance(c.time+2e-6)
        before=snapshot(c,'transmitting')
        modal=c.tx.reconstruction.states.copy()
        if cause=='stop':c.execute_management('stop',0,c.time)
        else:c.set_reference(False,c.time)
        assert c.state=='draining' and c.tx.held==0 and not c.dac_pending
        assert all(modal==c.tx.reconstruction.states)
        after=[snapshot(c,'at stop')]
        origin=c.time
        for delay in (20e-9,200e-9,2e-6,10e-6):
            c.advance(origin+delay);after.append(snapshot(c,f'{delay:g}s after stop'))
        # Preserve demonstrated failures as assertions on the current model.
        assert after[0]['output_magnitude'] > .1
        assert after[-1]['output_magnitude'] > .002
        rows.append(dict(cause=cause,before=before,after=after))
    peak=max(r['output_magnitude'] for r in calibration)
    assert peak>.1
    report=dict(status='characterized',isolation_requirement_satisfied=False,
        calibration_peak_output=peak,calibration=calibration,stop_cases=rows,
        findings=['Quiet calibration excites the same ungated envelope observed at the RF output.',
            'Stopping clears the held code but preserves reconstruction energy; immediate output remains nonzero.',
            'After reconstruction settles, configured LO feedthrough remains at the observed output.'],
        limitations=['No physical pad switch, driver-disable attenuation, switching transient or leakage floor is modeled.',
            'Observed magnitudes are normalized model units, not volts, watts or measured emissions.',
            'Internal pre-isolation calibration versus pad-side measurement must be an explicit topology choice.'])
    (P/'evidence/connected-tx-output-isolation-audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print('calibration peak',peak)
    for row in rows:print(row['cause'],[r['output_magnitude'] for r in row['after']])

if __name__=='__main__':main()
