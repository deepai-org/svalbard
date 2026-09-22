"""Finite spectral noise phase integration and pulse-loop forecast isolation."""
import copy,json
from scipy.integrate import quad
from chip_model import P
from oscillator_noise import FrequencyNoise
from compliant_edge_pll import CompliantEdgePLL
from pump_serializer_screen import snapshot

def run(rate,seed):
    noise=FrequencyNoise.seeded(20000,seed=seed)
    p=CompliantEdgePLL(rate_hz=rate,reference_hz=10e6);p.advance(20e-6)
    p.set_reference(False,p.time);baseline=copy.copy(p)
    initial=snapshot(p);p.set_noise(p.time,noise);assert snapshot(p)==initial
    subdivided=copy.copy(p);start=p.time;end=start+731e-9
    expected=quad(noise.frequency,start,end,epsabs=1e-13)[0]
    assert abs(noise.phase_integral(start,end)-expected)<1e-13
    p.advance(end);baseline.advance(end)
    for i in range(1,138):subdivided.advance(start+(end-start)*i/137)
    error=abs(p.phase-baseline.phase-expected)
    assert error<1e-8 and abs(p.phase-subdivided.phase)<1e-7
    p.set_reference(True,end);p.advance(end+20e-6)
    assert p.fault is None
    live=snapshot(p);target=p.phase+35.5;t=p.edge_time(target)
    assert snapshot(p)==live
    trial=copy.copy(p);trial.advance(t)
    assert abs(trial.phase-target)<2e-8
    return dict(rate_hz=rate,seed=seed,phase_error_cycles=error,locked=p.locked,
        noise_bound_hz=noise.bound_hz,forecast_error_cycles=abs(trial.phase-target))

def main():
    rows=[run(r,s) for r in (1.25e9,2.5e9) for s in (1,2)]
    (P/'evidence/connected-pump-noise.json').write_text(json.dumps(dict(status='passed',cases=rows,
        complete_architecture=False,physical_qualification=False,
        limitations=['Finite periodic spectral realization, not calibrated GF180 phase noise or infinite-band noise.',
        'Lock is observed but not required under the injected noise; application tolerance is not qualified.',
        'Noise currently perturbs VCO frequency only; pump/reference noise remain absent.']),indent=2)+'\n')
    print('Passed pulse-loop spectral phase integration and independent forecasts')
if __name__=='__main__':main()
