"""Measure native-grid cycle state inside long output gaps; diagnostic only."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
ap = argparse.ArgumentParser()
ap.add_argument('--contiguous', action='store_true', help='Store waveform columns contiguously; separate comparison report')
ap.add_argument('--second-stage', action='store_true', help='Analyze completed stronger second-stage candidate with contiguous columns')
ap.add_argument('--half', action='store_true', help='Analyze completed halved second-stage candidate')
ap.add_argument('--feedback', choices=['30k','300k'])
args = ap.parse_args()
assert sum([args.half,args.second_stage,bool(args.feedback)]) <= 1
R = Path(__file__).resolve().parents[3]
P = R / 'projects/programmable_transceiver_platform'
W = R / 'scratch/transceiver-lo-receiver-replay'
E = P / 'evidence/lo-receiver-replay.json'
if args.second_stage or args.half or args.feedback:
    variant = 'lo-feedback-'+args.feedback if args.feedback else 'lo-second-stage-half' if args.half else 'lo-second-stage'
    W = R / ('scratch/transceiver-' + variant)
    E = P / ('evidence/' + variant + '.json')
def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()
def rises(t, y, threshold):
    k = np.flatnonzero((y[:-1] < threshold) & (y[1:] >= threshold))
    return t[k] + (threshold-y[k]) * np.diff(t)[k] / np.diff(y)[k]
def measure(t, y, lo, hi, threshold):
    k0, k1 = np.searchsorted(t, [lo, hi], side='right')
    tt = np.r_[lo, t[k0:k1], hi]
    yy = np.r_[np.interp(lo,t,y), y[k0:k1], np.interp(hi,t,y)]
    dt = np.diff(tt); left=yy[:-1]; right=yy[1:]
    above = np.where((left>=threshold)&(right>=threshold), 1., 0.)
    cross = (left<threshold)!=(right<threshold)
    fraction = np.zeros_like(dt)
    fraction[cross] = (threshold-left[cross])/(right[cross]-left[cross])
    above[cross] = np.where(left[cross]>=threshold, fraction[cross], 1-fraction[cross])
    return [float(yy.min()), float(yy.max()), float(np.trapezoid(yy,tt)/(hi-lo)), float(np.sum(dt*above)/(hi-lo))]
assert np.allclose(measure(np.array([0.,1.,2.]),np.array([0.,2.,0.]),0.,2.,1.),[0.,2.,1.,.5])
e=json.loads(E.read_text()); assert e['completed']
if args.second_stage or args.half or args.feedback:
    result = W/'result.json'
    assert sha(result)==e['result_sha256']
    artifacts=json.loads(result.read_text())['artifacts_sha256']
else:
    artifacts=e['artifacts_sha256']
assert sha(W/'replay.dat')==artifacts['.dat']
with (W/'replay.dat').open() as f: header=f.readline().lower().split()
a=np.loadtxt(W/'replay.dat',skiprows=1)
if args.contiguous or args.second_stage or args.half or args.feedback: a=np.asfortranarray(a)
t=a[:,0]
assert np.isfinite(a).all() and np.all(np.diff(t)>0)
def node(n): return a[:,header.index(n)]
cycles=rises(t,node('v(p)')-node('v(n)'),0.)
cycles=cycles[(cycles>=512e-9)&(cycles<=1024e-9)]
out={'completed':True,'upstream_sha256':sha(E),'fields':['minimum_v','maximum_v','mean_v','fraction_above_marker'],'legs':{},'diagnostic_use_approved':False}
for leg in ('ip','in','qp','qn'):
    edges=rises(t,node('v(o'+leg+')'),1.65)
    gaps=[(lo,hi) for lo,hi in zip(edges[:-1],edges[1:]) if hi-lo>800e-12]
    groups={'inside_long_gap':[], 'outside_long_gap':[]}
    names=['v(b'+leg+')','v(xb'+leg+'.mid)','v(pre'+leg+')','v(o'+leg+')']
    ys=[node(n) for n in names]
    for lo,hi in zip(cycles[:-1],cycles[1:]):
        inside=any(lo>=g0 and hi<=g1 for g0,g1 in gaps)
        overlap=any(lo<g1 and hi>g0 for g0,g1 in gaps)
        if overlap and not inside: continue
        groups['inside_long_gap' if inside else 'outside_long_gap'].append([measure(t,y,lo,hi,1.65 if i==3 else 1.530318) for i,y in enumerate(ys)])
    out['legs'][leg]={}
    for label, rows in groups.items():
        values=np.array(rows)
        out['legs'][leg][label]={'cycles':len(rows),'nodes':{n:{'min':values[:,i,:].min(axis=0).tolist(),'max':values[:,i,:].max(axis=0).tolist(),'mean':values[:,i,:].mean(axis=0).tolist()} for i,n in enumerate(names)} if rows else {}}
out['limitations']=['Post-observation diagnostic grouping, not causal proof or acceptance limits.', 'Only complete ring cycles inside gaps or outside all gaps; boundary cycles excluded.', 'MID/PRE lack parent observations; replay scope approval remains separate.', 'Markers are not transistor conduction thresholds; duty is piecewise-linear duration.']
(P/'evidence'/('lo-feedback-'+args.feedback+'-gap-state.json' if args.feedback else 'lo-second-stage-half-gap-state.json' if args.half else 'lo-second-stage-gap-state.json' if args.second_stage else 'lo-gap-state-contiguous.json' if args.contiguous else 'lo-gap-state.json')).write_text(json.dumps(out,indent=2)+'\n')
print({leg:{g:d['cycles'] for g,d in groups.items()} for leg,groups in out['legs'].items()})
