"""Overload-memory law and full connected conversion/return recovery."""
import json,math
from adc_recovery import ADCRecovery
from sampled_clock_lifecycle import SampledClockChip
from chip_model import P,decode_iq


def controls():
    r=ADCRecovery(100e-9,.1)
    assert r.sample(2-2j,0)==2-2j
    z=r.sample(0j,100e-9)
    assert abs(z-(.1-.1j)/math.e)<1e-15
    old=(r.time,r.residual,r.overloads)
    try:r.sample(complex(math.nan,0),200e-9)
    except ValueError:pass
    else:raise AssertionError('Nonfinite input accepted')
    assert old==(r.time,r.residual,r.overloads)


def run(mode,sign,tau):
    c=SampledClockChip(watchdog_s=100e-6,adc_recovery_tau_s=tau,adc_recovery_gain=.1)
    c.external_source([sign*(3-3j),.2+.1j],0,10e-6)
    c.configure(mode,0);c.advance(8e-6)
    c.capture(256,c.time+100e-9,gain=1)
    c.advance(24e-6);c.host_decoder.finish()
    assert c.host_samples==c.adc_words and len(c.host_samples)==256
    assert c.adc_diagnostics['clipped_samples']>0 and c.adc_recovery.overloads>0
    values=[decode_iq(w,c.bits) for w in c.adc_words]
    # Both signs recover to the same small signal without resetting analog memory.
    assert abs(values[-1]-(.2+.1j))<.012
    assert abs(c.adc_recovery.residual)<1e-5
    return dict(mode=mode,sign=sign,tau_s=tau,clipped=c.adc_diagnostics['clipped_samples'],
                final_error=abs(values[-1]-(.2+.1j)),final_residual=abs(c.adc_recovery.residual),samples=256)


def main():
    controls();rows=[run(m,s,200e-9) for m in (0,1) for s in (-1,1)]
    report=dict(status='passed',cases=rows,complete_architecture=False,physical_qualification=False,
        limitations=['200ns decay and0.1 per-sample excess coupling are assumed uncertainty parameters.',
        'This models sampled comparator/input memory only; overload between samples, physical common-mode and device recovery remain unknown.',
        'Default zero-memory behavior remains available; residual state persists across digital resets and decays on the next conversion.'])
    (P/'evidence/connected-adc-recovery.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed analytic decay and four connected signed overload/recovery cases')

if __name__=='__main__':main()
