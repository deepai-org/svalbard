"""Exact first-order NRZ channel response at sample events; no recovered clock."""
import hashlib
import itertools
import json
import time
from pathlib import Path
import numpy as np

P=Path(__file__).resolve().parents[1]

def sample_channel(symbols, times, ui, bandwidth):
    """ZOH symbols at k*UI, y(0)=0. Closed-form RC evolution, no time grid."""
    assert np.all(times>=0) and np.all(times<len(symbols)*ui)
    tau=1/(2*np.pi*bandwidth); decay=np.exp(-ui/tau)
    starts=np.empty(len(symbols)); state=0.
    for k,value in enumerate(symbols):
        starts[k]=state
        state=value+(state-value)*decay
    k=np.floor(times/ui).astype(int)
    return symbols[k]+(starts[k]-symbols[k])*np.exp(-(times-k*ui)/tau)

def run(rate, bandwidth_ratio, offset_ui, ppm, jitter_ui):
    rng=np.random.default_rng(521); n=8192; ui=1/rate
    symbols=2*rng.integers(0,2,n)-1
    k=np.arange(32,n-32)
    times=(k+.5+offset_ui+k*ppm*1e-6+rng.normal(0,jitter_ui,len(k)))*ui
    values=sample_channel(symbols,times,ui,rate*bandwidth_ratio)
    margin=values*symbols[k]
    return dict(rate_bps=rate,bandwidth_hz=rate*bandwidth_ratio,
        offset_ui=offset_ui,period_error_ppm=ppm,jitter_rms_ui=jitter_ui,
        observed_bit_errors=int(np.sum(margin<=0)),bits=len(k),
        minimum_signed_margin=float(margin.min()),
        clock='externally prescribed; CDR absent')

def main():
    start=time.monotonic()
    ui=1e-9; bw=1e9;t=np.array([.1,.5,1.5,2.5])*ui
    actual=sample_channel(np.ones(4),t,ui,bw)
    assert np.allclose(actual,1-np.exp(-2*np.pi*bw*t),atol=1e-14,rtol=0)
    assert np.allclose(sample_channel(-np.ones(4),t,ui,bw),-actual)
    assert run(2.5e9,1,0,0,0)['observed_bit_errors']==0
    cases=[run(*v) for v in itertools.product([1.25e9,2.5e9],[.15,.35,1],[-.25,0,.25],[-100,0,100],[0,.03])]
    report=dict(status='sensitivity_only_not_link_qualification',
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        runtime_seconds=time.monotonic()-start,cases=cases,
        limitations=['No CDR, acquisition, equalizer, encoding, termination or transistor model.',
        'One-pole channel and independent Gaussian jitter are hypothetical.',
        'Zero errors in a short deterministic-seed record is not a BER bound.',
        'Frequency error accumulates without recovery; this is intentional.',
        'No simultaneous supply coupling to RF or host transport yet.'])
    (P/'evidence/fast-wired-screen.json').write_text(json.dumps(report,indent=2)+'\n')
    print(len(cases),'cases',round(report['runtime_seconds'],3),'seconds',sum(c['observed_bit_errors']>0 for c in cases),'with errors')
if __name__=='__main__':main()
