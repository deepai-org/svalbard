"""Abort a calibrated TX with queued samples or in-flight DAC conversion."""
import json
from chip_model import P
from managed_resources import command
from tx_calibration_chip import TxCalibrationChip

def prepared(chip_type=TxCalibrationChip):
    c=chip_type(watchdog_s=1e-3,dac_latency_s=100e-9)
    assert command(c,'rf_coarse_start',2412000000)['accepted']
    c.advance(c.time+50e-6)
    r=command(c,'tx_cal_start');assert r['accepted']
    c.advance(c.time+25e-6)
    assert command(c,'tx_cal_commit',r['value'])['accepted']
    assert command(c,'configure_mode',0)['accepted']
    c.advance(c.time+20e-6)
    assert c.state=='active'
    return c

def main():
    rows=[]
    for pending,completion_guard in ((False,False),(True,False),(True,True)):
        c=prepared()
        for value in (.2+.1j,.1-.1j):assert c.tx.accept(value)
        c.schedule(2,c.time+2e-6)
        if pending:
            c.advance(c.next_sample)
            assert c.dac_pending and c.tx.consumed==1
        before=c.dac_pipeline_updates
        # Execute at current control instant to isolate a cancellation boundary;
        # serialized command delivery is covered in the management screen.
        if completion_guard:
            c.tx_cal.valid=False  # Inject loss to exercise the final update boundary.
            c.advance(c.dac_pending[0][0])
        else:c.execute_management('tx_cal_abort',0,c.time)
        assert c.state=='draining' and not c.tx_cal.valid and not c.dac_pending
        assert not c.tx.queue and c.tx.held==0 and c.remaining==0
        state=c.tx.reconstruction.states.copy()
        c.advance(c.time+2e-6)
        assert c.dac_pipeline_updates==before and not c.tx_cal.valid
        rows.append(dict(completion_guard=completion_guard,pending_before_abort=pending,tx=c.tx.accounting(),dac=c.dac_accounting(),
            filter_state_norm_at_abort=float(sum(abs(state)))))
    report=dict(status='passed',cases=rows,limitations=[
        'Active calibration abort uses existing whole-chip fault/drain recovery, interrupting other active streams.',
        'Command delivery latency tested separately; this test isolates application at queue and pipeline boundaries.',
        'DAC cancellation does not prove physical RF output isolation or LO-feedthrough suppression.'])
    (P/'evidence/connected-tx-calibration-inflight.json').write_text(json.dumps(report,indent=2)+'\n');print(report)
if __name__=='__main__':main()
