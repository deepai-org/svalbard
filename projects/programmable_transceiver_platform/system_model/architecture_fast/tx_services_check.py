"""Timed TX detector/correction ownership on the fast service composition."""
import hashlib
import json
import time
from pathlib import Path
from tx_services import FastTxServiceChip,architecture
from managed_resources import command


def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    p=architecture.P;start=time.monotonic()
    files=list(architecture.D.glob('*.py'))+list(Path(__file__).parent.glob('*.py'))+[p/'verification/stream_codec.py']
    hashes={str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    report=dict(status='running',source_sha256=hashes,cases=[],physical_qualification=False,
        limitations=['Independent idealized detector ADC; shared-ADC loading still requires integration.',
                     'Committed correction is not a physical accuracy qualification.',
                     'No full four-path traffic or external TX waveform qualification in this check.'])
    output=p/'evidence/fast-tx-services.json'
    def save():output.write_text(json.dumps(report,indent=2)+'\n')
    save()
    try:
        for mode,bits in ((0,12),(1,8)):
            c=FastTxServiceChip(watchdog_s=1e-3)
            try:c.execute_management('tx_cal_start',0,c.time)
            except ValueError:pass
            else:raise AssertionError('Unlocked TX calibration admitted')
            c.advance(c.time+10e-6)
            assert c.rf_pll.locked
            reply=command(c,'tx_cal_start');assert reply['accepted'],reply
            generation=reply['value']
            assert not command(c,'configure_mode',mode)['accepted']
            assert not command(c,'cal_start',48)['accepted']
            c.advance(c.time+25e-6)
            assert c.tx_cal.state=='ready' and not c.tx_cal.valid
            assert not command(c,'tx_cal_commit',generation-1)['accepted']
            assert command(c,'tx_cal_commit',generation)['accepted'] and c.tx_cal.valid
            candidate=c.tx_cal.candidate
            assert command(c,'configure_mode',mode)['accepted']
            assert c.tx.sample_correction.bits==bits
            c.set_reference(False,c.time)
            assert not c.tx_cal.valid and c.tx_detector.pending is None
            report['cases'].append(dict(mode=mode,bits=bits,fit=candidate,
                probe_count=len(c.tx_cal.powers),reference_loss_invalidates=True))
            save();print('mode',mode,'passed',flush=True)
        c=FastTxServiceChip(watchdog_s=1e-3);c.advance(10e-6)
        assert command(c,'tx_cal_start')['accepted']
        c.advance(c.tx_cal.next_event)
        assert c.tx_detector.pending is not None
        c.set_reference(False,c.time);c.advance(c.time+1e-6)
        assert c.tx_cal.state=='cancelled' and not c.tx_cal.valid and c.tx_detector.pending is None
        report['inflight_cancellation']=True
        assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
        report.update(status='passed',elapsed_s=time.monotonic()-start)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));raise
    finally:save()

if __name__=='__main__':main()
