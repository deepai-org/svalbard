"""Independent-tone response and converter transport with both pulse clocks."""
import cmath,json,math
from chip_model import P
from pulse_chip import PulseChip
from managed_resources import command

def run(mode,noisy):
    c=PulseChip(watchdog_s=100e-6,rf_noise_rms_hz=20000 if noisy else 0,
        wire_noise_rms_hz=10000 if noisy else 0,rf_hz_per_v=1e6,wire_hz_per_v=1e6,
        return_charge_per_transition=50e-15)
    amplitude=.25+.1j;beat=250e3
    c.configure_rx('external_tone',1,5e6,5e6,amplitude,beat)
    c.configure(mode,0);c.advance(20e-6)
    assert c.state=='active' and c.rf_pll.locked and c.wire_pll.locked
    phase0=2*math.pi*c.envelope_phase(c.rf_pll);transfer=1/(1+1j*beat/5e6)
    errors=[]
    for i in range(128):
        c.advance(c.time+25e-9)
        expected=amplitude*transfer*cmath.exp(2j*math.pi*beat*c.time-1j*phase0)
        errors.append(abs(c.tx.received-expected)/abs(amplitude*transfer))
    relative=max(errors)
    assert relative<.1,relative
    c.capture(64,c.time+100e-9)
    words=[17,801,511,0]*4
    for word in words:c.accept_wire(word)
    c.schedule_wire(len(words),c.time+100e-9)
    c.advance(c.time+5e-6);c.host_decoder.finish()
    assert c.host_samples==c.adc_words and len(c.host_samples)==64 and c.wired_output==words
    assert c.oscillator_supply_events>0
    return dict(mode=mode,noisy=noisy,maximum_relative_analog_error=relative,
        rf_pulse_reference_edges=len(c.rf_pll.reference_history),rf_phase_continuity_error_rad=c.rf_continuity_error,
        converter_samples=len(c.host_samples),wired_words=len(words),rail_events=c.oscillator_supply_events)

def main():
    rows=[run(m,n) for m in (0,1) for n in (False,True)]
    (P/'evidence/connected-pulse-rf-chip.json').write_text(json.dumps(dict(status='passed',cases=rows,
        complete_architecture=False,physical_qualification=False,
        limitations=['Single independent tone at nominal2.4GHz; no wideband blocker/noise envelope qualification.',
        'Unknown initial LO phase read once; no fitting to received samples.10% provisional maximum-error budget.',
        'RF carrier retargeting explicitly unavailable; fractional feedback remains open.']),indent=2)+'\n')
    print('Passed independent RF tone and simultaneous converter/wired transport with both pulse loops')
if __name__=='__main__':main()
