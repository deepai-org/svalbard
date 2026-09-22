"""Held-out load/sensor test of earlier observation; standalone only."""
import json,hashlib,itertools
from pathlib import Path
import numpy as np
from scipy.linalg import expm
from receiver_detect_load_screen import matrices,classify

TIMES=(100e-9,200e-9)

def measure(p,x0,errors):
    C,G,A=matrices(**p);eq=np.array([.2,0.])
    return [float((eq+expm(A*t)@(x0-eq))[0]-x0[0]+e)/.2 for t,e in zip(TIMES,errors)]

def main():
    rng=np.random.default_rng(843);rows=[]
    # New interior points rather than tuning regions against these observations.
    # Thresholds are retained from the previous candidate; only second time changes.
    for index in range(256):
        present=index%2==0
        p=dict(cp=rng.uniform(1,10)*1e-12,cr=rng.uniform(1,10)*1e-12,
            cc=rng.uniform(10,100)*1e-9,rs=rng.uniform(100,1000),
            rt=rng.uniform(40,100) if present else 10**rng.uniform(5,8))
        x0=rng.uniform(-.005,.005,2)
        errors=rng.uniform(-.005,.005,2)
        v=measure(p,x0,errors);out=classify(v);expected='present' if present else 'absent'
        assert out in (expected,'indeterminate'),(p,v,out)
        rows.append(dict(parameters=p,initial_v=x0.tolist(),measurement_error_v=errors.tolist(),normalized_samples=v,result=out,expected=expected))
    # Repeat original load corners with worst signed 5mV differential measurement
    # error and initial-node errors, retaining any indeterminate boundary cases.
    corners=[]
    for cp,cc,cr,rs,rt,sgn in itertools.product((1e-12,10e-12),(10e-9,100e-9),(1e-12,10e-12),(100.,1000.),(40.,100.,1e5,1e8),(-1,1)):
        p=dict(cp=cp,cc=cc,cr=cr,rs=rs,rt=rt)
        x0=np.array([sgn*.005,-sgn*.005]);v=measure(p,x0,(sgn*.005,sgn*.005))
        expected='present' if rt<=100 else 'absent';out=classify(v)
        assert out in (expected,'indeterminate')
        corners.append(dict(parameters=p,sign=sgn,result=out,expected=expected,normalized_samples=v))
    bad=dict(cp=5e-12,cc=100e-12,cr=3e-12,rs=470.,rt=75.)
    badv=measure(bad,np.zeros(2),(0,0))
    assert classify(badv)!='present'
    counts={k:sum(r['result']==k for r in rows+corners) for k in ('present','absent','indeterminate')}
    report=dict(status='passed',connected=False,physical_qualification=False,times_s=TIMES,
        seed=843,counts=counts,heldout_cases=rows,corner_cases=corners,
        outside_envelope=dict(parameters=bad,normalized_samples=badv,result=classify(badv)),
        dependency_sha256=hashlib.sha256(Path(__file__).with_name('receiver_detect_load_screen.py').read_bytes()).hexdigest(),
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        limitations=['Finite load points, not proof over a continuous domain. Initial voltage and measurement errors are assumptions.',
        'Shortening the second observation is selected using prior corner evidence; interior random cases are new holdouts.',
        '5mV error bounds represent total baseline-subtracted measurement error, not each separate sensor reading.',
        'Small coupling capacitor false negatives remain. No connected controller, release settling or two-leg resource ownership yet.'])
    (Path(__file__).resolve().parents[2]/'evidence/receiver-detect-timing-screen.json').write_text(json.dumps(report,indent=2)+'\n')
    print('384 cases:',counts,'outside-envelope:',classify(badv))

if __name__=='__main__':main()
