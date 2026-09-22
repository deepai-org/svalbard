"""Edge-driven loop-filter exploration, retaining original qualification limits."""
import json, math, hashlib
from pathlib import Path
import numpy as np
from fractional_rf_chip import ShapedRFClock
from oscillator_noise import FrequencyNoise
from driver_clock_forcing import DriverPulledSpectrum
from chip_model import P


def measure(bandwidth, fraction, target=2437000000, noise_rms=20000., clock_class=ShapedRFClock):
    # Initial free oscillator and selected coarse-bank offset from mode-1 setup.
    pll=clock_class(reference_hz=40e6,divider=60,free_hz=2.4e9*.92+7*25e6,
        bandwidth_hz=bandwidth,fast_fraction=fraction,phase_cycles=.2)
    pll.retarget(0,target)
    noise=FrequencyNoise.seeded(noise_rms,seed=839)
    pll.set_noise(0,DriverPulledSpectrum(noise.tones,1e6*(3.25799896954-3.3)))
    first=None;losses=0;tail=[];fault=None
    for i in range(1,2401):
        try:
            pll.advance(i/40e6);was=pll.locked;locked=pll.observe_lock()
        except ValueError as error:
            fault=str(error);break
        if locked and first is None:first=pll.time
        if was and not locked:losses+=1
        if i>=1601:
            tail.append((pll.output_phase_cycles-target*pll.time,
                pll.frequency_hz-target,locked))
    phases=np.asarray([v[0]*2*math.pi for v in tail])
    return dict(target_hz=target,noise_rms_hz=noise_rms,bandwidth_hz=bandwidth,fast_fraction=fraction,
        first_lock_s=first,lock_losses=losses,fault=fault,
        sustained_tail_lock=len(tail)==800 and all(v[2] for v in tail),
        tail_phase_std_rad=float(np.std(phases)) if len(phases) else None,
        tail_peak_frequency_error_hz=max((abs(v[1]) for v in tail),default=None),
        resistance_ohm=pll.filter.r,fast_capacitance_f=pll.filter.cf,
        slow_capacitance_f=pll.filter.cs)

if __name__=='__main__':
    report=dict(status='running',cases=[],limitations=[
        'Isolated finite edge-driven PLL screen; no RF network, transport, or closed rail feedback.',
        'Held quiet driver pull and declared noise retained; startup history differs from integrated coarse acquisition.',
        '40–60us phase standard deviation is not held-out TX quality or physical jitter qualification.',
        'No lock thresholds relaxed; candidates require full coupled validation.'],
        source_sha256={str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in Path(__file__).parent.glob('*.py')})
    output=P/'evidence/pll-filter-tradeoff-screen.json'
    for bw in (300e3,450e3,600e3):
        for fraction in (.3,.5,.7):
            row=measure(bw,fraction);report['cases'].append(row)
            output.write_text(json.dumps(report,indent=2)+'\n');print(row,flush=True)
    report['status']='characterized';output.write_text(json.dumps(report,indent=2)+'\n')
