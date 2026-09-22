#!/usr/bin/env python3
"""Retain the independent-pattern result and check event cadence/hold interval."""
import hashlib
import json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'scratch/transceiver-wired-frozen-pattern'
PROJECT=ROOT/'projects/programmable_transceiver_platform'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((WORK/'result.json').read_text())
assert sha(WORK/'changing.spice')==r['source_sha256']['deck']
assert sha(WORK/'changing.dat')==r['source_sha256']['waveform']
assert sha(PROJECT/'evidence/wired-hold-window-analysis.json')==r['source_sha256']['plan']
x=np.loadtxt(WORK/'changing.dat',skiprows=1); t=x[:,0]
assert len(r['bits'])==80 and r['total_samples']==65
checks={}
for branch,col in [('even',7),('odd',8)]:
    samples=r['branches'][branch]['samples']
    times=[s['capture_fall_s'] for s in samples]
    periods=np.diff(times)*1e12
    minima=[]
    for sample in samples:
        a=sample['capture_fall_s']+200e-12; b=sample['capture_fall_s']+650e-12
        points=np.r_[a,t[(t>a)&(t<b)],b]
        v=(2*sample['expected']-1)*np.interp(points,t,x[:,col])
        minima.append(float(v.min()))
        # Independent recomputation at the frozen primary point.
        at=(2*sample['expected']-1)*np.interp(sample['capture_fall_s']+400e-12,t,x[:,col])
        assert abs(at-sample['signed_v'])<1e-9
    checks[branch]=dict(min_period_ps=float(periods.min()),max_period_ps=float(periods.max()),
        cadence_700_to_900ps=bool(np.all((periods>=700)&(periods<=900))),
        minimum_signed_200_to_650ps_v=min(minima),below_500mv_hold_windows=sum(v<.5 for v in minima))
r['cadence_and_hold_checks']=checks
r['screen_pass_with_cadence']=r['screen_pass'] and all(d['cadence_700_to_900ps'] for d in checks.values())
r['checker_sha256']=sha(Path(__file__))
r['reproduction']='make transceiver-wired-frozen-pattern; python3 projects/programmable_transceiver_platform/verification/check_wired_frozen_pattern.py'
(PROJECT/'evidence/wired-frozen-pattern-screen.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(dict(screen_pass=r['screen_pass'],cadence_and_hold=checks,current_a=r['current_a']),indent=2))
