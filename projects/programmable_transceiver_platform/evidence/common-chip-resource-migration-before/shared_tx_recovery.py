"""Shared detector ADC ownership, cancellation, restart and retune invalidation."""
import hashlib
import json
import time
from pathlib import Path
from shared_tx_traffic import SharedOutputChip,scenario
from managed_resources import command


def rejects(call):
    try:call()
    except ValueError:return
    raise AssertionError('Operation unexpectedly admitted')


def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    p=scenario.architecture.P;start=time.monotonic()
    files=list(scenario.architecture.D.glob('*.py'))+list(Path(__file__).parent.glob('*.py'))+[p/'verification/stream_codec.py']
    hashes={str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    report=dict(status='running',source_sha256=hashes,cases=[],physical_qualification=False,
        limitations=['Selected exact event boundaries; not all serialized-command races.',
                     'Readout/mux/ADC assumptions remain physically unqualified.'])
    output=p/'evidence/fast-shared-tx-recovery.json'
    def save():output.write_text(json.dumps(report,indent=2)+'\n')
    save()
    try:
        for mode in (0,1):
            c=SharedOutputChip(watchdog_s=1e-3);c.advance(10e-6)
            reply=command(c,'tx_cal_start');assert reply['accepted']
            generation=reply['value']
            while c.tx_adc_samples<2 or c.tx_detector.pending is None:
                assert c.tx_cal.next_event is not None
                c.advance(c.tx_cal.next_event)
            assert c.tx_cal.state=='convert'
            rejects(lambda:c.capture(1,c.time+1e-6))
            rejects(lambda:c.execute_management('cal_start',48,c.time))
            deadline=c.tx_detector.pending[0]
            detector=c.tx_detector.value;readout=c.tx_detector.readout_value
            count=c.tx_adc_samples;charge=c.adc_reference.charge
            c.set_reference(False,c.time)
            assert c.tx_cal.state=='cancelled' and not c.tx_cal.valid
            assert c.tx_detector.pending is None
            assert c.tx_detector.value==detector and c.tx_detector.readout_value==readout
            assert not c.execute_management('resource_status',0,c.time)['value']&256
            c.advance(deadline+1e-6)
            assert c.tx_adc_samples==count and c.adc_reference.charge==charge
            rejects(c.tx_detector.read)
            assert not command(c,'tx_cal_commit',generation)['accepted']
            c.set_reference(True,c.time);c.advance(c.time+10e-6)
            assert c.rf_pll.locked
            restart=command(c,'tx_cal_start');assert restart['accepted']
            c.advance(c.time+25e-6)
            assert c.tx_cal.state=='ready'
            assert command(c,'tx_cal_commit',restart['value'])['accepted']
            assert c.tx_cal.valid and restart['value']!=generation
            # Quiet retune must expire the committed correction before traffic.
            c.configure_rf_carrier(2437000000)
            assert not c.tx_cal.valid
            rejects(lambda:c.descriptor(1))
            c.advance(c.time+10e-6)
            again=command(c,'tx_cal_start');assert again['accepted']
            c.advance(c.time+25e-6)
            assert command(c,'tx_cal_commit',again['value'])['accepted']
            assert command(c,'configure_mode',mode)['accepted']
            assert c.tx.sample_correction.bits==(12 if mode==0 else 8)
            report['cases'].append(dict(mode=mode,cancelled_sample_count=count,
                reference_charge_at_cancel_c=charge,retained_detector_value=detector,
                stale_result_rejected=True,ownership_released=True,restarted=True,
                retune_invalidates=True,recalibrated_generation=again['value']))
            save();print('mode',mode,'passed',flush=True)
        assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
        report.update(status='passed',elapsed_s=time.monotonic()-start)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));raise
    finally:save()

if __name__=='__main__':main()
