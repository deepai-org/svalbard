"""Combined managed TX/host candidate reference-loss and opposite-mode recovery."""
import json
from chip_model import P
from managed_resources import command
from managed_tx_quality import ManagedTxHostChip,calibration_window
from tx_host_precondition import conditioner

def ready(c,target,mode):
    assert command(c,'rf_coarse_start',target)['accepted']
    c.advance(c.time+50e-6)
    calibration_window(False)(c)
    assert c.tx_cal.valid
    assert command(c,'configure_mode',mode)['accepted']
    c.advance(c.time+30e-6)
    assert c.state=='active'
    conditioner('switching')(c,mode)
    assert c.host_activation.ready(c.time,c.epoch)

def burst(c):
    base=c.dac_pipeline_updates
    for z in (.2+.1j,-.1+.15j,.05-.1j):assert c.tx.accept(z)
    c.schedule(3,c.time+100e-9);c.capture(8,c.time+120e-9)
    c.advance(c.time+2e-6)
    assert c.dac_pipeline_updates==base+3
    assert not c.tx.queue and not c.dac_pending
    return c.dac_accounting()

def main():
    rows=[]
    for mode in (0,1):
        c=ManagedTxHostChip(rf_fast_fraction=.30,watchdog_s=1e-3,dac_latency_s=20e-9)
        ready(c,2412000000,mode);first=burst(c)
        old_epoch=c.epoch;generation=c.tx_cal.generation
        state=c.tx.reconstruction.states.copy();time=c.time
        c.set_reference(False,time)
        assert c.state=='draining' and not c.tx_cal.valid
        assert not c.host_activation.ready(time,old_epoch)
        assert all(state==c.tx.reconstruction.states)
        c.acknowledge_host_abort(c.epoch,c.time);c.acknowledge_drain(c.epoch,c.time)
        c.set_reference(True,c.time)
        assert c.epoch==old_epoch+1 and not c.tx_cal.valid
        assert command(c,'detect_rearm')['accepted']
        assert not command(c,'tx_cal_commit',generation)['accepted']
        ready(c,2437000000,1-mode);second=burst(c)
        assert c.tx_cal.valid and c.tx_cal.generation>generation
        assert c.tx.sample_correction.bits==(8 if mode==0 else 12)
        rows.append(dict(initial_mode=mode,recovered_mode=1-mode,epoch=c.epoch,
            first=first,second=second,calibration_generation=c.tx_cal.generation,
            retained_filter_norm=float(sum(abs(state)))))
        print(rows[-1],flush=True)
    (P/'evidence/connected-managed-tx-recovery.json').write_text(json.dumps(dict(status='passed',cases=rows,
        limitations=['Finite RF playback/capture and host training; no full four-path modulation-quality check after recovery.',
        'Default noiseless recovery fixture; full loaded/noisy quality and SPI-only unification remain open.',
        'Internal sample queue injection tests DAC lifecycle; framed payload codec covered separately.']),indent=2)+'\n')
if __name__=='__main__':main()
