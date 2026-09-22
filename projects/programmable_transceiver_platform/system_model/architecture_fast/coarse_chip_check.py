"""Managed coarse startup gates calibration and mode activation on common chip."""
import hashlib,json,time
from pathlib import Path
from coarse_chip import CoarseTransceiverChip
from shared_tx_traffic import scenario
from managed_resources import command

def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    p=scenario.architecture.P;start=time.monotonic()
    files=list(scenario.architecture.D.glob('*.py'))+list(Path(__file__).parent.glob('*.py'))+[p/'verification/stream_codec.py']
    hashes={str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    report=dict(status='running',source_sha256=hashes,cases=[],physical_qualification=False,
        limitations=['Startup-only coarse bank with assumed monotonicity/settling.',
                     'Capture/readiness test, not full four-path quality on this composition.',
                     'Warm bank recentering and post-start cancellation coverage remain open.'])
    output=p/'evidence/fast-coarse-chip.json'
    def save():output.write_text(json.dumps(report,indent=2)+'\n')
    save()
    try:
        for mode in (0,1):
            c=CoarseTransceiverChip(rf_free_offset=.96*.995-1,watchdog_s=1e-3)
            assert not command(c,'configure_mode',mode)['accepted']
            assert not command(c,'tx_cal_start')['accepted']
            assert command(c,'rf_coarse_start',2500000000)['accepted']
            c.advance(c.time+35e-6)
            assert c.coarse.qualified and c.rf_pll.locked
            assert abs(c.rf_pll.control())<.8
            for target in (0,1):
                assert command(c,'cal_start',48|(target<<16))['accepted'];c.advance(c.time+40e-6)
            reply=command(c,'tx_cal_start');assert reply['accepted'];c.advance(c.time+25e-6)
            assert command(c,'tx_cal_commit',reply['value'])['accepted']
            c.external_source([.2+.1j],c.time,1.,offset_hz=100250000)
            assert command(c,'configure_mode',mode)['accepted']
            c.capture(32,c.time+100e-9);c.advance(c.time+4e-6);c.host_decoder.finish()
            assert len(c.host_samples)==32 and c.host_samples==c.adc_words
            report['cases'].append(dict(mode=mode,bank_code=c.rf_pll.bank_code,
                fine_control_v=c.rf_pll.control(),samples=32,measurements=c.coarse.history));save()
            print(mode,'passed',flush=True)
        assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
        report.update(status='passed',elapsed_s=time.monotonic()-start)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));raise
    finally:save()

if __name__=='__main__':main()
