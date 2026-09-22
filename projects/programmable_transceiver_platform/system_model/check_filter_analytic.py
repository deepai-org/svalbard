"""Check cascaded discrete RC updates against exact held-input state evolution."""
import hashlib,json
from pathlib import Path
import numpy as np
from fast_screen import lowpass
P=Path(__file__).resolve().parents[1]
def exact_cascade(x,fs,b1,b2):
    p=2*np.pi*b1;q=2*np.pi*b2;dt=1/fs
    a=np.exp(-p*dt);b=np.exp(-q*dt)
    cross=q*dt*b if p==q else q*(a-b)/(q-p)
    first=second=0j;out=[]
    for u in x:
        second=u+(second-u)*b+(first-u)*cross
        first=u+(first-u)*a
        out.append(second)
    return np.array(out)
rows=[]
for fs in [20e6,40e6]:
    for b1,b2 in [(12e6,20e6),(12e6,12e6)]:
        n=128;t=(np.arange(n)+1)/fs;p=2*np.pi*b1;q=2*np.pi*b2
        expected=1-(1+p*t)*np.exp(-p*t) if p==q else 1-(q*np.exp(-p*t)-p*np.exp(-q*t))/(q-p)
        assert np.allclose(exact_cascade(np.ones(n),fs,b1,b2),expected,atol=1e-14,rtol=0)
        rng=np.random.default_rng(529);x=rng.normal(size=n)+1j*rng.normal(size=n)
        reference=exact_cascade(x,fs,b1,b2);errors=[]
        for k in [1,8,16,32,64]:
            y=lowpass(lowpass(np.repeat(x,k),fs*k,b1),fs*k,b2)[k-1::k]
            errors.append(dict(oversample=k,max_absolute_error=float(abs(y-reference).max()),rms_error=float(np.sqrt(np.mean(abs(y-reference)**2)))))
        assert all(a['rms_error']>b['rms_error'] for a,b in zip(errors,errors[1:]))
        rows.append(dict(fs=fs,b1=b1,b2=b2,errors=errors))
report=dict(completed=True,rows=rows,
    sources_sha256={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in [Path(__file__),P/'system_model/fast_screen.py']},
    limitations=['Linear two-pole cascade only; no quantization or intermediate compression.',
    'Exact recurrence is a reference check, not calibrated analog transfer behavior.',
    'No tolerance establishes default16x sufficiency for all future uses.'])
(P/'evidence/fast-filter-analytic.json').write_text(json.dumps(report,indent=2)+'\n')
print('Four analytic step controls and four complex-input refinement cases passed')
