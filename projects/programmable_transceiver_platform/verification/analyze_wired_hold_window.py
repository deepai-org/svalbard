#!/usr/bin/env python3
"""Piecewise-linear signed hold windows; freeze prior bit identities, no refit."""
import hashlib
import json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
PROJECT=ROOT/'projects/programmable_transceiver_platform'
record_path=PROJECT/'evidence/wired-boost-off-screen.json'
record=json.loads(record_path.read_text())
wave=ROOT/'scratch/transceiver-wired-boost-off/changing.dat'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(wave)==record['source_sha256']['waveform']
pattern_path=ROOT/'scratch/transceiver-wired-pulse-data-gf180/result.json'
bits=json.loads(pattern_path.read_text())['stimulus_bits']
x=np.loadtxt(wave,skiprows=1); t=x[:,0]
THRESHOLD=.5
# Find the connected above-threshold interval containing a declared 400 ps
# anchor, on the actual adaptive-time samples with linear threshold crossings.
def window(u,v,anchor=400e-12):
    assert u[0]==0 and u[-1]==800e-12 and np.all(np.diff(u)>0)
    if np.interp(anchor,u,v)<THRESHOLD:
        return None
    knots=[0.0,800e-12]
    for a,b,va,vb in zip(u[:-1],u[1:],v[:-1],v[1:]):
        if (va<THRESHOLD)!=(vb<THRESHOLD):
            knots.append(float(a+(THRESHOLD-va)*(b-a)/(vb-va)))
    knots=sorted(knots)
    for a,b in zip(knots,knots[1:]):
        if a<=anchor<=b and np.interp((a+b)/2,u,v)>=THRESHOLD:
            return (a,b)
    raise AssertionError('Missing valid connected interval')
# Analytic check includes two boundaries; selecting only the first crossing
# would incorrectly certify a waveform that subsequently loses the bit.
u=np.array([0,200,400,600,800])*1e-12
assert np.allclose(np.array(window(u,np.array([-1,1,1,1,-1])))*1e12,[150,650],rtol=0,atol=1e-9)
assert window(u,np.array([1,1,-1,1,1])) is None
rows=[]
for branch,col in [('even',7),('odd',8)]:
    data=record['boost_off']['branches'][branch]
    ids=record['boost_off']['best']['branches'][branch]['bit_indices']
    for observed_time,bit in zip(data['times_s'],ids):
        fall=observed_time-100e-12
        mask=(t>fall)&(t<fall+800e-12)
        offsets=np.r_[0,t[mask]-fall,800e-12]
        values=(2*bits[bit]-1)*np.interp(fall+offsets,t,x[:,col])
        span=window(offsets,values)
        assert span is not None
        # Exact minimum of the piecewise-linear waveform over the proposed
        # conservative interval, not just a grid of favorable sample points.
        conservative=np.r_[200e-12,offsets[(offsets>200e-12)&(offsets<650e-12)],650e-12]
        signed=np.interp(conservative,offsets,values)
        rows.append(dict(branch=branch,bit_index=bit,capture_fall_s=fall,
            valid_start_ps=span[0]*1e12,valid_end_ps=span[1]*1e12,
            clipped_at_800ps=span[1]==800e-12,
            minimum_signed_200_to_650ps_v=float(signed.min()),
            signed_at_100ps_v=float(np.interp(100e-12,offsets,values)),
            signed_at_400ps_v=float(np.interp(400e-12,offsets,values))))
lo=max(r['valid_start_ps'] for r in rows); hi=min(r['valid_end_ps'] for r in rows)
result=dict(status='observed_hold_window_not_implemented_retiming',sample_count=len(rows),
    threshold_v=THRESHOLD,common_connected_window_ps=[lo,hi],
    minimum_signed_200_to_650ps_v=min(r['minimum_signed_200_to_650ps_v'] for r in rows),
    minimum_signed_at_400ps_v=min(r['signed_at_400ps_v'] for r in rows),
    fixed_next_test=dict(sample_offset_after_capture_fall_ps=400,
        first_scored_even_bit=11,first_scored_odd_bit=12,bit_increment_per_branch=2,
        capture_fall_window_start_ns=6,
        note='Ordinal association frozen from prior experiment; do not re-fit delay on the next pattern. Six-ns scoring start is a diagnostic fixture, not qualified acquisition.'),
    samples=rows,source_sha256=dict(record=sha(record_path),waveform=sha(wave),pattern=sha(pattern_path),analyzer=sha(Path(__file__))),
    limitations=['Linear interpolation of saved adaptive samples; no substep accuracy claim.',
                 'Same short pattern, nominal process/temperature/supply, no new transient.',
                 '400 ps anchor selects a connected window; all original bit identities remain fixed.',
                 'No physical retiming clock, host timing contract, BER or startup qualification.'])
(PROJECT/'evidence/wired-hold-window-analysis.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('samples','source_sha256')},indent=2))
