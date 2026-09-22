"""Spectrum energy, loop transfer, subdivision invariance and noisy chip traffic."""
import cmath
import copy
import json
import math
from autonomous_pll import AutonomousPLL
from oscillator_noise import FrequencyNoise
from noisy_oscillator_lifecycle import NoisyOscillatorChip
from oscillator_supply_lifecycle import OscillatorSupplyChip
from sustained_lifecycle import run
from chip_model import P


def controls():
    source=FrequencyNoise.seeded(20000.)
    samples=[source.frequency(i/(4096*250e3)) for i in range(4096)]
    mean=sum(samples)/len(samples);rms=math.sqrt(sum(x*x for x in samples)/len(samples))
    assert abs(mean)<1e-8 and abs(rms-20000)<1e-8
    assert source==FrequencyNoise.seeded(20000.) and source!=FrequencyNoise.seeded(20000.,seed=831)
    p=AutonomousPLL(free_hz=2.4e9,phase_cycles=0.);p.set_noise(0,source);q=copy.copy(p)
    p.advance(2e-6)
    for i in range(1,201):q.advance(i*10e-9)
    assert abs(p.error-q.error)<1e-10 and abs(p.integral-q.integral)<1e-9
    before=(p.time,p.error,p.integral,p.frequency_noise)
    edge=p.edge_time(p.output_phase_cycles+1)
    assert before==(p.time,p.error,p.integral,p.frequency_noise)
    p.advance(edge);assert edge>before[0]
    # Independent steady-state linear-loop response to a sinusoidal VCO input.
    frequency=750e3;amplitude=1000.;phase=.37
    p=AutonomousPLL(free_hz=2.4e9,phase_cycles=0.)
    p.set_noise(0,FrequencyNoise(((frequency,amplitude,phase),)))
    wn=2*math.pi*1e6;w=2*math.pi*frequency;zeta=.707
    response=-(1j*w*amplitude/p.divider)/(wn*wn-w*w+2j*zeta*wn*w)
    errors=[]
    for index in range(100):
        time=5e-6+index*10e-9;p.advance(time)
        expected=(response*cmath.exp(1j*(w*time+phase))).real
        errors.append(abs(p.error-expected))
    assert max(errors)<1e-10
    # Numerical stress only: a high-offset line could alias all RK stages
    # without the explicit spectral step limit. Its integral over four periods
    # is zero in holdover, independently of the loop implementation.
    alias=AutonomousPLL(free_hz=2.4e9,phase_cycles=0.)
    alias.set_reference(False,0.);alias.set_noise(0.,FrequencyNoise(((4e9,1e6,0.),)))
    alias.advance(1e-9);alias_error=abs(alias.output_phase_cycles-2.4)
    assert alias_error<1e-10
    return dict(high_offset_integral_error_cycles=alias_error,rms_hz=rms,mean_hz=mean,subdivision_error_cycles=abs(q.error-before[1]),
                analytic_transfer_error_cycles=max(errors),lines=source.tones)


def capture(mode,seed):
    c=NoisyOscillatorChip(rf_noise_rms_hz=20000,wire_noise_rms_hz=10000,noise_seed=seed,
        rf_hz_per_v=1e6,wire_hz_per_v=-1e6,return_charge_per_transition=50e-15,watchdog_s=50e-6)
    c.configure_rx('external_tone',1,5e6,5e6,.3+.1j,0.)
    c.configure(mode,0);c.advance(5e-6)
    assert c.state=='active' and c.rf_pll.locked and c.wire_pll.locked
    c.capture(32,c.time+100e-9);c.advance(c.time+3e-6);c.host_decoder.finish()
    assert c.state=='active' and len(c.adc_words)==32 and c.host_samples==c.adc_words
    assert c.rf_continuity_error<1e-8
    return c


def main():
    checks=controls();rows=[];captures=[];failures=[]
    for mode in (0,1):
        a=capture(mode,830);repeat=capture(mode,830);b=capture(mode,831)
        assert a.adc_words==repeat.adc_words and a.analog_samples==repeat.analog_samples
        difference=max(abs(x-y) for x,y in zip(a.analog_samples,b.analog_samples))
        assert difference>1e-5
        captures.append(dict(mode=mode,repeat_identical=True,seed_analog_difference=difference,
                             changed_codes=sum(x!=y for x,y in zip(a.adc_words,b.adc_words))))
        def factory(**kw):
            return NoisyOscillatorChip(wire_reference_ppm=100,rf_noise_rms_hz=20000,wire_noise_rms_hz=10000,
                rf_hz_per_v=1e6,wire_hz_per_v=-1e6,return_charge_per_transition=50e-15,**kw)
        rows.append(run(mode,100,frames=8,chip_factory=factory,matched_reference=True,host_ppm=-100))
        c=NoisyOscillatorChip(rf_noise_rms_hz=20e6,watchdog_s=50e-6)
        c.configure(mode,0);c.advance(10e-6)
        assert c.wire_pll.locked and not c.rf_pll.locked and c.state=='acquiring' and not c.session.armed
        failures.append(dict(mode=mode,excessive_rf_noise_blocks_start=True))
    report=dict(status='passed',controls=checks,independent_input=captures,traffic=rows,negative_cases=failures,
        complete_architecture=False,physical_qualification=False,
        limitations=['Eight fixed spectral lines from250kHz to2MHz with random phases; finite periodic realization, not infinite-band or Gaussian white noise.',
                    'Frequency noise enters the VCO dynamics before loop suppression; its RMS/Hz-band parameters are assumed, not GF180 data.',
                    'Separate seeds model RF/wired VCO sources; shared reference noise and divider/charge-pump noise are still absent.',
                    'Fractional-divider edge patterns/spurs and full modulated RF quality remain open.'])
    (P/'evidence/connected-oscillator-noise.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed reproducible spectral VCO noise, analytic loop transfer, independent reception and four-path traffic')


if __name__=='__main__':main()
