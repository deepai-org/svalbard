"""Managed integer RF pulse tuning with preserved charge and independent tones."""
import cmath,copy,json,math
from chip_model import P
from tunable_pulse_chip import TunablePulseChip
from managed_resources import command

def run(mode,target):
    c=TunablePulseChip(watchdog_s=100e-6)
    amp=.25+.1j;beat=250e3
    c.configure_rx('external_tone',1,5e6,5e6,amp,target-2.4e9+beat)
    token,apply,reply=c.submit('configure_rf_carrier',c.time,c.epoch,c.rx_generation,target)
    c.advance(apply-1e-12);predicted=copy.copy(c.rf_pll);predicted.advance(apply)
    c.advance(apply)
    assert c.rf_pll.output_phase_cycles==predicted.output_phase_cycles
    assert (c.rf_pll.filter.v,c.rf_pll.filter.w)==(predicted.filter.v,predicted.filter.w)
    assert c.rf_pll.feedback_target>c.rf_pll.phase and not c.rf_pll.locked
    assert c.read_reply(token,reply)['accepted']
    c.configure(mode,c.time);c.advance(c.time+20e-6)
    assert c.state=='active' and c.rf_pll.locked
    phase0=2*math.pi*(c.envelope_phase(c.rf_pll)-(target-2.4e9)*c.time)
    transfer=1/(1+1j*beat/5e6);errors=[]
    for i in range(64):
        c.advance(c.time+25e-9)
        expected=amp*transfer*cmath.exp(2j*math.pi*beat*c.time-1j*phase0)
        errors.append(abs(c.tx.received-expected)/abs(amp*transfer))
    assert max(errors)<.01,max(errors)
    c.capture(32,c.time+100e-9);c.advance(c.time+3e-6);c.host_decoder.finish()
    assert c.host_samples==c.adc_words and len(c.host_samples)==32
    return dict(mode=mode,target_hz=target,max_relative_error=max(errors),returned_samples=32)

def main():
    rows=[run(m,t) for m in (0,1) for t in (2320000000,2400000000,2480000000)]
    c=TunablePulseChip();before=(c.rf_pll.phase,c.rf_pll.divider,c.rf_target_hz)
    try:c.configure_rf_carrier(2412000000)
    except ValueError:pass
    else:raise AssertionError('Unimplemented fractional divider accepted')
    assert before==(c.rf_pll.phase,c.rf_pll.divider,c.rf_target_hz)
    (P/'evidence/connected-pulse-tuning.json').write_text(json.dumps(dict(status='passed',cases=rows,
        complete_architecture=False,physical_qualification=False,
        limitations=['Integer40MHz channels only; Wi-Fi channel spacing still requires fractional feedback.',
        'Ideal divider/PFD reset introduces no analog charge injection; real reprogramming transients remain unknown.',
        'Noiseless single-tone cases; not a wideband or physical RF qualification.']),indent=2)+'\n')
    print('Passed managed integer RF pulse tuning, state continuity and independent-tone conversion')
if __name__=='__main__':main()
