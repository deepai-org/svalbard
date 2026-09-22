"""Add driver pull without overwriting host-rail forcing or intrinsic spectrum."""
import copy,json,math
from chip_model import P
from oscillator_noise import FrequencyNoise
from driver_clock_forcing import DriverPulledSpectrum
from pulse_clock_service import PulseClockService

def main():
    noise=FrequencyNoise(((1e6,2000.,.3),(7e6,500.,-.2)))
    pulled=DriverPulledSpectrum(noise.tones,-200000.)
    assert pulled.bound_hz==202500
    for t in (0.,1e-9,17e-9):
        assert abs(pulled.frequency(t)-noise.frequency(t)+200000)<1e-10
    assert abs(pulled.phase_integral(0,1e-6)-noise.phase_integral(0,1e-6)+.2)<1e-14
    c=PulseClockService(40e6,60,2.4e9);c.set_noise(0,noise)
    c.set_supply(0,-.03,10e-9,1e6)
    before=(c.phase,c.filter.v,c.filter.w,c.rail_amplitude_hz,c.rail_tau)
    ref=copy.copy(c);c.set_noise(0,pulled)
    assert before==(c.phase,c.filter.v,c.filter.w,c.rail_amplitude_hz,c.rail_tau)
    _,p0=ref.predict(1e-9);_,p1=c.predict(1e-9)
    assert abs((p1-p0)-(-200000*1e-9))<1e-12
    assert c.rail_frequency(1e-9)==ref.rail_frequency(1e-9)
    report=dict(status='passed',held_driver_pull_hz=-200000.,predicted_phase_difference_cycles=p1-p0,
        host_rail_pull_hz=c.rail_frequency(1e-9),
        limitations=['Forcing interface and phase continuity only; causal driver-rail/PLL co-simulation remains to implement.',
            'The offset must be refreshed at declared boundaries with step-convergence tests; no physical sensitivity claim.'])
    (P/'evidence/connected-driver-clock-forcing.json').write_text(json.dumps(report,indent=2)+'\n');print(report)

if __name__=='__main__':main()
