"""Finite output-isolation reopening on the managed host recovery composition."""
import json, math
from chip_model import P
from managed_resources import command
from managed_tx_recovery_screen import ready
from tx_output_isolation import IsolatedManagedTxHostChip
from tx_envelope_observer import observe_tx

def launch(c,carrier):
    assert not c.tx_output_isolation.enabled
    initial=c.tx_pad_transfer(c.time)
    assert math.isclose(initial,c.tx_output_isolation.off,abs_tol=1e-12)
    count=c.dac_pipeline_updates
    assert c.tx.accept(.2+.1j)
    c.schedule(1,c.time+100e-9)
    c.advance(c.next_sample)
    assert c.dac_pending and not c.tx_output_isolation.enabled
    deadline=c.dac_pending[0][0]
    c.advance(deadline)
    assert c.dac_pipeline_updates==count+1 and c.tx_output_isolation.enabled
    assert math.isclose(c.tx_pad_transfer(c.time),initial,abs_tol=1e-12)
    rows=[]
    for delay in (0.,20e-9,100e-9,500e-9):
        c.advance(deadline+delay)
        expected=.001+.999*(-math.expm1(-delay/20e-9))
        assert math.isclose(c.tx_pad_transfer(c.time),expected,abs_tol=1e-10)
        rows.append(dict(delay=delay,transfer=c.tx_pad_transfer(c.time),
                         output_magnitude=abs(observe_tx(c,carrier))))
    return rows

def main():
    rows=[]
    for mode in (0,1):
        c=IsolatedManagedTxHostChip(rf_fast_fraction=.30,watchdog_s=1e-3,dac_latency_s=20e-9)
        ready(c,2412000000,mode)
        first=launch(c,2412000000)
        old_epoch=c.epoch;generation=c.tx_cal.generation
        gate_before=c.tx_pad_transfer(c.time)
        states=c.tx.reconstruction.states.copy()
        c.set_reference(False,c.time)
        assert c.state=='draining' and not c.tx_cal.valid and not c.tx_output_isolation.enabled
        assert c.tx_pad_transfer(c.time)==gate_before
        assert all(states==c.tx.reconstruction.states)
        assert not c.host_activation.ready(c.time,old_epoch)
        c.acknowledge_host_abort(c.epoch,c.time);c.acknowledge_drain(c.epoch,c.time)
        c.set_reference(True,c.time)
        assert c.epoch==old_epoch+1
        assert command(c,'detect_rearm')['accepted']
        assert not command(c,'tx_cal_commit',generation)['accepted']
        assert not c.tx_output_isolation.enabled
        ready(c,2437000000,1-mode)
        assert not c.tx_output_isolation.enabled and c.tx_cal.generation>generation
        second=launch(c,2437000000)
        rows.append(dict(initial_mode=mode,recovered_mode=1-mode,epoch=c.epoch,
                         first_launch=first,recovered_launch=second))
        print('reopened',mode,'to',1-mode,flush=True)
    report=dict(status='passed',cases=rows,limitations=[
        'Finite managed host composition, two recovery directions; noiseless clock fixture.',
        'Launch attenuation measured, not full modulation EVM or spectrum qualification.',
        'Internal queue injection; external framed payload and concurrent wired traffic not exercised here.',
        'Isolation parameters and pre-isolation monitor remain unqualified assumptions.'])
    (P/'evidence/connected-isolated-tx-recovery.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
