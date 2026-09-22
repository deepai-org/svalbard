"""Management retuning, analog-state retention and lock-gated RF operation."""
import json
import math
from chip_model import P
from sampled_clock_lifecycle import SampledClockChip
from managed_resources import command


def run(mode,target):
    c=SampledClockChip(watchdog_s=100e-6)
    c.advance(3e-6)
    token,apply,reply=c.submit('configure_rf_carrier',c.time,c.epoch,c.rx_generation,target)
    c.advance(apply-1e-12)
    assert c.rf_target_hz==2.4e9
    # Bring the oscillator to the exact command time on a separate prediction.
    import copy
    expected=copy.copy(c.rf_pll);expected.advance(apply)
    c.advance(apply)
    phase_error=abs(c.rf_pll.output_phase_cycles-expected.output_phase_cycles)
    assert phase_error<1e-8
    assert c.rf_pll.integral==expected.integral
    assert c.rf_pll.frequency_hz==expected.frequency_hz
    assert not c.rf_pll.locked and c.rf_pll.good==0
    assert c.rf_target_hz==target
    assert c.read_reply(token,reply)['accepted']
    c.configure(mode,c.time);c.advance(c.time+8e-6)
    assert c.state=='active' and c.rf_pll.locked
    assert abs(c.rf_pll.frequency_hz-target)<target*1e-5
    # The envelope coordinate remains anchored at 2.4GHz across retunes.
    # This capture checks lifecycle/transport, not tuned input signal quality.
    c.capture(32,c.time+100e-9)
    c.advance(c.time+3e-6);c.host_decoder.finish()
    assert len(c.adc_words)==32 and c.host_samples==c.adc_words
    old=(c.rf_target_hz,c.rf_pll.divider)
    rejected=command(c,'configure_rf_carrier',2400000000)
    assert not rejected['accepted'] and old==(c.rf_target_hz,c.rf_pll.divider)
    return dict(mode=mode,target_hz=target,phase_continuity_error_cycles=phase_error,
                settled_hz=c.rf_pll.frequency_hz,adc_samples=32,armed_write_rejected=True)


def controls():
    c=SampledClockChip()
    before=c.rf_pll.__dict__.copy()
    for target in (0,2299999999,2500000001):
        try:c.configure_rf_carrier(target)
        except ValueError:pass
        else:raise AssertionError('Invalid target accepted')
        assert c.rf_pll.__dict__==before
    return dict(invalid_targets_atomic=True)


def main():
    rows=[run(m,f) for m in (0,1) for f in (2320000000,2412000000,2480000000)]
    report=dict(status='passed',cases=rows,controls=controls(),complete_architecture=False,
        physical_qualification=False,limitations=[
        'Fractional feedback ratios are ideal averages; fractional-N edge modulation, spurs and noise remain unmodeled.',
        '2.3–2.5GHz is a command envelope, not a measured VCO tuning range or full acquisition guarantee.',
        'Retuning requires reset/disarmed state and preserves the fixed2.4GHz RF envelope coordinate.',
        'Capture verifies lifecycle and transport only; independent tuned RF signal quality remains to be screened.'])
    (P/'evidence/connected-rf-tuning.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed six managed RF tuning cases, phase retention, lock gating and invalid-write controls')

if __name__=='__main__':main()
