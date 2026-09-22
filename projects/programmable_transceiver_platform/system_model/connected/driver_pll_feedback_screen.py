"""Causal driver rail changes PLL phase; compare coupling-step refinement."""
import json
from chip_model import P
from rf_driver_transient import CoupledDriver
from pulse_clock_service import PulseClockService
from oscillator_noise import FrequencyNoise
from driver_pll_feedback import advance_feedback

def run(step,sensitivity):
    d=CoupledDriver();d.network.configure(True,False)
    pll=PulseClockService(40e6,60,2.4e9)
    pll.set_noise(0,FrequencyNoise(((3e6,2000.,.2),)))
    pll.set_supply(0,-.01,10e-9,1e6)
    rail_amplitude=pll.rail_amplitude_hz
    steps=advance_feedback(d,pll,50e-9,[(.3+0j,0j)],sensitivity,step)
    assert d.time==pll.time==50e-9 and pll.rail_amplitude_hz==rail_amplitude
    assert pll.frequency_noise.tones==((3e6,2000.,.2),)
    return d,pll,steps

def main():
    rows=[];runs=[run(step,1e6) for step in (2e-9,1e-9,.5e-9,.25e-9)]
    ref,clock,_=runs[-1]
    for step,(d,p,count) in zip((2e-9,1e-9,.5e-9,.25e-9),runs):
        rows.append(dict(step_s=step,steps=count,rail_v=d.rail_v,phase_cycles=p.output_phase_cycles,
            phase_error_cycles=abs(p.output_phase_cycles-clock.output_phase_cycles),
            pad_error_v=float(abs(d.network.voltage[1]-ref.network.voltage[1]))))
    assert rows[1]['phase_error_cycles']<rows[0]['phase_error_cycles']
    assert rows[2]['phase_error_cycles']<rows[1]['phase_error_cycles']
    assert rows[2]['phase_error_cycles']<1e-4
    _,uncoupled,_=run(.25e-9,0.)
    delta=clock.output_phase_cycles-uncoupled.output_phase_cycles
    assert abs(delta)>1e-4
    report=dict(status='passed',cases=rows,phase_change_vs_uncoupled_cycles=delta,
        limitations=['50ns local feedback convergence; no acquired-lock, waveform-quality or whole-chip claim.',
            'Driver pull held per coupling interval; convergence must be rechecked for full operating envelopes.',
            'Assumed coupling and local rail; shared reference/other domains remain unconnected.'])
    (P/'evidence/connected-driver-pll-feedback.json').write_text(json.dumps(report,indent=2)+'\n');print(report)

if __name__=='__main__':main()
