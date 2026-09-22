"""Numerical refinement diagnostic, independent of transistor qualification."""
import hashlib,json,time
from pathlib import Path
from fast_screen import loopback
P=Path(__file__).resolve().parents[1];start=time.monotonic();rows=[]
for fs,bits in [(20e6,8),(40e6,12)]:
    for amplitude in [.05,.4,.8]:
        cases=[loopback(amplitude,0,0,3,fs,bits,oversample=k) for k in [1,8,16,32,64]]
        rows.append(dict(sample_rate_hz=fs,bits=bits,amplitude_v=amplitude,cases=cases,
            evm_delta_32_to_64=abs(cases[-1]['residual_evm']-cases[-2]['residual_evm'])))
report=dict(completed=True,status='refinement_diagnostic_no_acceptance_threshold',
    model_sha256=hashlib.sha256((P/'system_model/fast_screen.py').read_bytes()).hexdigest(),
    runtime_seconds=time.monotonic()-start,rows=rows,
    limitations=['ADC samples fixed at end of each DAC hold, regardless of refinement.',
    'Each RC update is exact for held input, but cascaded/nonlinear intermediate signals are discretized.',
    'Quantizer crossings can change discretely; scalar EVM convergence is not waveform identity.',
    'No transistor or spectral-mask qualification; gains/bandwidth remain assumed.'])
(P/'evidence/fast-envelope-convergence.json').write_text(json.dumps(report,indent=2)+'\n')
for r in rows:print(r['sample_rate_hz'],r['amplitude_v'],[round(c['residual_evm'],5) for c in r['cases']],r['evm_delta_32_to_64'])
