"""Warm management retune after active capture/stop/drain on same chip."""
import hashlib,json,time
from pathlib import Path
from warm_chip import WarmTransceiverChip
from shared_tx_traffic import scenario
from managed_resources import command

def calibrate(c):
    r=command(c,'tx_cal_start');assert r['accepted'];c.advance(c.time+25e-6)
    assert command(c,'tx_cal_commit',r['value'])['accepted']
    return r['value']

def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    p=scenario.architecture.P;start=time.monotonic()
    files=list(scenario.architecture.D.glob('*.py'))+list(Path(__file__).parent.glob('*.py'))+[p/'verification/stream_codec.py']
    hashes={str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    report=dict(status='running',source_sha256=hashes,cases=[],physical_qualification=False,
        limitations=['Finite retune/capture lifecycle; post-warm-retune four-path waveform quality pending.',
                     'Assumed coarse bank/centering; no physical switch or phase-noise qualification.'])
    output=p/'evidence/fast-warm-chip.json'
    def save():output.write_text(json.dumps(report,indent=2)+'\n')
    save()
    try:
        for mode in (0,1):
            c=WarmTransceiverChip(watchdog_s=1e-3)
            assert command(c,'rf_coarse_start',2437000000)['accepted'];c.advance(c.time+35e-6)
            old_generation=calibrate(c)
            # Warm retune while quiet must invalidate even same-epoch calibration.
            c.execute_management('rf_coarse_start',2500000000,c.time)
            assert c.coarse.state=='centering' and not c.tx_cal.valid
            status=c.execute_management('rf_coarse_status',0,c.time)['value']
            assert status&255==9 and status&256
            assert not command(c,'tx_cal_commit',old_generation)['accepted']
            c.advance(c.time+35e-6)
            for target in (2500000000,2412000000):
                if c.rf_target_hz!=target:
                    assert command(c,'rf_coarse_start',target)['accepted'];c.advance(c.time+35e-6)
                assert c.coarse.qualified and c.rf_pll.locked
                calibrate(c)
                c.external_source([.2+.1j],c.time,1.,offset_hz=target-2400000000+250000)
                assert command(c,'configure_mode',mode)['accepted']
                assert not command(c,'rf_coarse_start',2437000000)['accepted']
                adc_begin=len(c.adc_words);host_begin=len(c.host_samples)
                c.capture(32,c.time+100e-9);c.advance(c.time+4e-6);c.host_decoder.finish()
                assert c.host_samples[host_begin:]==c.adc_words[adc_begin:] and len(c.host_samples)-host_begin==32
                assert command(c,'stop')['accepted']
                assert command(c,'ack_abort')['accepted'] and command(c,'ack_drain')['accepted']
                assert c.state=='reset' and not c.tx_cal.valid
                report['cases'].append(dict(mode=mode,target_hz=target,bank_code=c.rf_pll.bank_code,
                    epoch=c.epoch,captured=32));save()
            print(mode,'passed',flush=True)
        assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
        report.update(status='passed',elapsed_s=time.monotonic()-start)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));raise
    finally:save()
if __name__=='__main__':main()
