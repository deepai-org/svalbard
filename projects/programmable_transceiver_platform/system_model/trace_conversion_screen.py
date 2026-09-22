"""Bounded-time measured-disturbance sampling, not RF-driven receiver EVM."""
import hashlib
import json
from pathlib import Path
import numpy as np
from fast_screen import convert

P = Path(__file__).resolve().parents[1]

def sample(t, values, query):
    if len(query) == 0 or query.min() < t[0] or query.max() > t[-1]:
        raise ValueError('Sampling outside recorded trace is prohibited')
    return np.interp(query, t, values.real) + 1j * np.interp(query, t, values.imag)

def score(ideal, disturbance):
    y = ideal + disturbance
    out = convert(y.real, 1) + 1j * convert(y.imag, 1)
    error = out - ideal
    return dict(uncorrected_error_ratio=float(np.linalg.norm(error)/np.linalg.norm(ideal)),
                dc_removed_error_ratio=float(np.linalg.norm(error-error.mean())/np.linalg.norm(ideal)),
                clipping_fraction=float(np.mean((abs(y.real)>=.5)|(abs(y.imag)>=.5))))

def main():
    meta_path = P/'evidence/lo-disturbance-trace.json'
    trace_path = P/'evidence/lo-disturbance-trace.npz'
    meta = json.loads(meta_path.read_text())
    assert hashlib.sha256(trace_path.read_bytes()).hexdigest() == meta['trace_sha256']
    with np.load(trace_path) as data:
        t = data['time_s']; values = data['i_v'] + 1j*data['q_v']
    assert len(t) == meta['samples'] and np.all(np.diff(t)>0)
    assert np.isfinite(values).all()
    assert np.allclose(sample(np.array([0.,1.]), np.array([0j,2+4j]), np.array([.25])), [.5+1j])
    try:
        sample(t, values, np.array([t[-1]+1e-9]))
    except ValueError:
        pass
    else:
        raise AssertionError('Out-of-range sampling accepted')
    freq = 19.53125e6
    basis = np.column_stack([np.ones(len(t)),np.cos(2*np.pi*freq*t),np.sin(2*np.pi*freq*t)])
    coef = np.linalg.lstsq(basis,values,rcond=None)[0]
    rows=[]
    for fs in [20e6,40e6]:
        for phase in np.arange(32)/32:
            # Same sample count at every phase; no extension or wrapping.
            count = int(np.floor((t[-1]-t[0])*fs))
            query = t[0]+(np.arange(count)+phase)/fs
            full = sample(t,values,query)
            fundamental = coef[0]+coef[1]*np.cos(2*np.pi*freq*query)+coef[2]*np.sin(2*np.pi*freq*query)
            for peak in [.008,.25]:
                ideal=peak*np.exp(2j*np.pi*3e6*(query-t[0]))
                rows.append(dict(fs=fs,sampling_phase_cycles=float(phase),samples=count,
                                 signal_peak_v=peak,full_trace=score(ideal,full),
                                 dc_and_fundamental=score(ideal,fundamental),
                                 quantization_only=score(ideal,np.zeros(count,dtype=complex))))
    paths=[meta_path,trace_path,Path(__file__),P/'system_model/fast_screen.py']
    report=dict(status='finite_trace_conversion_sensitivity',cases=rows,
                sources_sha256={str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
                limitations=['Only 10 or 20 samples per phase; no statistical or modem EVM claim.',
                             'Ideal 8-bit 1V ADC, no aperture/reference dynamics.',
                             'Zero-RF replay disturbance plus hypothetical signal assumes unverified superposition.',
                             'Fundamental fit preserves measured phase; it is a comparison, not cancellation.',
                             'Phase sweep is finite and not a guaranteed worst-case bound.',
                             'Trace interpolation is not anti-alias filtering; no extrapolation or tiling.'])
    (P/'evidence/fast-trace-conversion.json').write_text(json.dumps(report,indent=2)+'\n')
    for fs in [20e6,40e6]:
        for peak in [.008,.25]:
            group=[r for r in rows if r['fs']==fs and r['signal_peak_v']==peak]
            print(fs,peak,{model:[min(r[model]['dc_removed_error_ratio'] for r in group),max(r[model]['dc_removed_error_ratio'] for r in group)] for model in ['full_trace','dc_and_fundamental','quantization_only']})

if __name__=='__main__':
    main()
