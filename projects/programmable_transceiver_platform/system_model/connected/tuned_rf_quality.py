"""Independent RF tone checks for the managed, tunable shared synthesizer."""
import cmath
import json
import math
from chip_model import P
from sampled_clock_lifecycle import SampledClockChip
from managed_resources import command


def run(mode,target,detuning=0.):
    c=SampledClockChip(watchdog_s=100e-6)
    amplitude=.25+.1j;beat=250e3
    c.configure_rx('external_tone',1,5e6,5e6,amplitude,target-2.4e9+beat)
    assert command(c,'configure_rf_carrier',int(target+detuning))['accepted']
    c.configure(mode,c.time);c.advance(c.time+12e-6)
    assert c.state=='active' and c.rf_pll.locked
    # Independent steady-state single-pole response. Only the unknown absolute
    # oscillator phase is read once, before observation; no sample fitting.
    residual=beat-detuning
    phase0=2*math.pi*(c.envelope_phase(c.rf_pll)-(target+detuning-2.4e9)*c.time)
    transfer=1/(1+1j*residual/5e6)
    errors=[];observed=[]
    for i in range(128):
        c.advance(c.time+25e-9)
        expected=amplitude*transfer*cmath.exp(2j*math.pi*residual*c.time-1j*phase0)
        errors.append(abs(c.tx.received-expected));observed.append(abs(c.tx.received))
    relative=max(errors)/abs(amplitude*transfer)
    assert relative<1e-5,relative
    # Exercise the real converter and return transport after the analog check.
    c.capture(64,c.time+100e-9);c.advance(c.time+5e-6);c.host_decoder.finish()
    assert len(c.host_samples)==64 and c.host_samples==c.adc_words
    return dict(mode=mode,source_carrier_hz=target,lo_target_hz=target+detuning,
                baseband_hz=residual,expected_amplitude=abs(amplitude*transfer),
                measured_amplitude=sum(observed)/len(observed),
                maximum_relative_analog_error=relative,returned_samples=64)


def main():
    rows=[run(m,t) for m in (0,1) for t in (2320000000,2412000000,2480000000)]
    controls=[run(m,2412000000,20e6) for m in (0,1)]
    for row in controls:
        baseline=next(r for r in rows if r['mode']==row['mode'] and r['source_carrier_hz']==2412000000)
        assert row['measured_amplitude']<.3*baseline['measured_amplitude']
    report=dict(status='passed',cases=rows,detuned_controls=controls,
        complete_architecture=False,physical_qualification=False,
        limitations=['Single independent tone and a single-pole baseband filter, without analog noise or blockers.',
        'Absolute LO phase is initialized from oscillator state before observation; no received-sample fit.',
        'Fractional divider remains an ideal average. This is not wideband EVM, image rejection or physical RF qualification.'])
    (P/'evidence/connected-tuned-rf-quality.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed six tuned independent-tone cases and two detuning controls with converter transport')

if __name__=='__main__':main()
