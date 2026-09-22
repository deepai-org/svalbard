"""Selected warm tuning-range boundaries on the common sampled-clock chip."""
import hashlib,json,time
from pathlib import Path
from chip import TransceiverChip
from shared_tx_traffic import scenario
from managed_resources import command
TARGETS=(2300000000,2301000000,2350000000,2400000000,2412000000,2437000000,2462000000,2499000000,2500000000)

def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    p=scenario.architecture.P;start=time.monotonic()
    files=list(scenario.architecture.D.glob('*.py'))+list(Path(__file__).parent.glob('*.py'))+[p/'verification/stream_codec.py']
    hashes={str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    report=dict(status='running',source_sha256=hashes,cases=[],physical_qualification=False,
        limitations=['Selected tuning points/orderings, not every frequency or process corner.',
                     'Average fractional feedback; no integer-divider spurs.',
                     'Lock/readiness check, not RF waveform quality over the tuning range.'])
    output=p/'evidence/fast-tuning-envelope.json'
    def save():output.write_text(json.dumps(report,indent=2)+'\n')
    save()
    try:
        for noisy,targets in ((False,TARGETS),(True,tuple(reversed(TARGETS)))):
            c=TransceiverChip(rf_noise_rms_hz=20000 if noisy else 0,noise_seed=839,watchdog_s=1e-3)
            c.advance(10e-6)
            reply=command(c,'tx_cal_start');assert reply['accepted'];c.advance(c.time+25e-6)
            assert command(c,'tx_cal_commit',reply['value'])['accepted']
            for target in targets:
                phase=c.rf_pll.output_phase_cycles;integral=c.rf_pll.integral
                c.configure_rf_carrier(target)
                jump=abs(c.rf_pll.output_phase_cycles-phase)
                assert jump<1e-9 and c.rf_pll.integral==integral
                assert not c.rf_pll.locked and not c.tx_cal.valid
                begin=c.time;first=None
                while c.time<begin+20e-6:
                    c.advance(min(c.next_rf_reference,begin+20e-6))
                    if c.rf_pll.locked and first is None:first=c.time
                row=dict(noisy=noisy,target_hz=target,locked=c.rf_pll.locked,
                    first_lock_delay_s=None if first is None else first-begin,
                    frequency_hz=c.rf_pll.frequency_hz,phase_jump_cycles=jump,
                    control=c.rf_pll.control())
                report['cases'].append(row);save();print(target,noisy,row['locked'],flush=True)
                assert row['locked'],row
            for invalid in (2299999999,2500000001,float('nan')):
                state=(c.rf_target_hz,c.rf_pll.divider,c.rf_pll.integral,c.rf_pll.output_phase_cycles)
                try:c.configure_rf_carrier(invalid)
                except ValueError:pass
                else:raise AssertionError('Invalid carrier admitted')
                assert state==(c.rf_target_hz,c.rf_pll.divider,c.rf_pll.integral,c.rf_pll.output_phase_cycles)
        assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
        report.update(status='passed',elapsed_s=time.monotonic()-start)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));raise
    finally:save()

if __name__=='__main__':main()
