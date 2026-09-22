"""Full common controller with a pulse-driven wired TX clock."""
import json
from chip_model import P
from programmable_chip import ProgrammableChip
from pulse_clock_service import PulseClockService
from managed_resources import command

class PulseWiredChip(ProgrammableChip):
    WIRE_PLL_CLASS=PulseClockService

def run(mode):
    c=PulseWiredChip(watchdog_s=100e-6,wire_hz_per_v=1e6,wire_noise_rms_hz=10000)
    c.configure(mode,0);c.advance(20e-6)
    assert c.state=='active' and c.wire_pll.locked
    words=[17,801,0,1023,511,7]*3
    for word in words:c.accept_wire(word)
    c.schedule_wire(len(words),c.time+100e-9)
    c.advance(c.time+1e-6)
    assert c.wired_output==words and c.wire_pll.reference_history
    phase=c.wire_pll.output_phase_cycles
    c.set_reference(False,c.time);epoch=c.epoch
    c.acknowledge_host_abort(epoch,c.time);c.acknowledge_drain(epoch,c.time)
    c.advance(c.time+1e-6)
    assert c.wire_pll.output_phase_cycles>phase and not c.wire_pll.locked
    assert command(c,'detect_rearm')['accepted']
    c.set_reference(True,c.time);c.configure(1-mode,c.time);c.advance(c.time+30e-6)
    assert c.state=='active' and c.wire_pll.locked
    c.accept_wire(123);c.schedule_wire(1,c.time+100e-9);c.advance(c.time+1e-6)
    assert c.wired_output[-1]==123
    return dict(initial_mode=mode,words=len(words),recovered_mode=1-mode,
        pulse_references=len(c.wire_pll.reference_history),frequency_hz=c.wire_pll.frequency_hz)

def main():
    rows=[run(m) for m in (0,1)]
    (P/'evidence/connected-pulse-wired-chip.json').write_text(json.dumps(dict(status='passed',cases=rows,
        complete_architecture=False,physical_qualification=False,
        limitations=['Wired pulse-loop substitution only; RF oscillator remains sampled.',
        'Finite nominal-load traffic with assumed VCO noise and supply sensitivity.',
        'Fractional divider and artificial phase-step fixture deliberately unsupported.']),indent=2)+'\n')
    print('Passed common-chip pulse wired timing, word transport and opposite-mode recovery')
if __name__=='__main__':main()
