"""Recorded-replay reproduction gate before interpreting common-mode removal."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
nodes=['v(p)','v(n)','v(oip)','v(oin)','v(oqp)','v(oqn)']
def load(path):
    with path.open() as f:h=f.readline().lower().split()
    a=np.loadtxt(path,skiprows=1,usecols=[0]+[h.index(n) for n in nodes])
    assert np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
    assert abs(a[-1,0]-1001e-9)<1e-15
    return a

def rises(t,y):
    k=np.flatnonzero((y[:-1]<1.65)&(y[1:]>=1.65))
    return t[k]+(1.65-y[k])*np.diff(t)[k]/np.diff(y)[k]

def edge_alignment(reference, observed):
    if not len(reference) or not len(observed):
        return dict(parent_edges=len(reference),replay_edges=len(observed),
            maximum_nearest_edge_error_ps=None,passes=False)
    distances=abs(reference[:,None]-observed[None,:])
    nearest=max(float(np.max(np.min(distances,axis=1))),
                float(np.max(np.min(distances,axis=0))))
    return dict(parent_edges=len(reference),replay_edges=len(observed),
        maximum_nearest_edge_error_ps=nearest*1e12,
        passes=bool(nearest<=5e-12 and abs(len(reference)-len(observed))<=1))

def controls():
    # A pulse with an unchanged rising edge can still have wrong width.
    t=np.array([0.,1.,2.,3.,4.,5.])*1e-9
    reference=np.array([0.,0.,3.3,3.3,0.,0.])
    distorted=np.array([0.,0.,3.3,0.,0.,0.])
    assert edge_alignment(rises(t,reference),rises(t,distorted))['passes']
    assert not edge_alignment(rises(t,3.3-reference),rises(t,3.3-distorted))['passes']
    assert not edge_alignment(np.array([]),np.array([]))['passes']
    assert not edge_alignment(np.array([0.,1e-9]),np.array([0.]))['passes']
    assert edge_alignment(np.array([0.,1e-9]),np.array([1e-12,1.001e-9]))['passes']

controls()

prepared={mode:R/f'scratch/transceiver-lo-common-mode-{mode}-prepared' for mode in ('recorded','fixed')}
assert (prepared['recorded']/'replay.spice').read_bytes()==(prepared['fixed']/'replay.spice').read_bytes()
for b in prepared.values():
    m=json.loads((b/'manifest.json').read_text())
    for name,h in m['artifacts_sha256'].items():assert sha(b/name)==h
limits=dict(window_ns=[800,1000],output_rms_error_v=.02,output_peak_error_v=.1,maximum_matched_edge_error_ps=5,maximum_edge_count_difference=1,edge_polarities=['rising','falling'])
work={mode:R/f'scratch/transceiver-lo-common-mode-{mode}' for mode in prepared}
if not all((w/'result.json').exists() for w in work.values()):
    print('Matched deck/provenance preparation checks pass; terminal results pending.')
else:
    data={};hashes={}
    for mode,w in work.items():
        r=json.loads((w/'result.json').read_text());assert r['returncode']==0 and not r['timed_out']
        assert r['sources_before']==r['sources_after']
        for ext,h in r['artifacts_sha256'].items():assert sha(w/('replay'+ext))==h
        assert sha(w/'replay.spice')==sha(prepared[mode]/'replay.spice')
        data[mode]=load(w/'replay.dat');hashes[mode]=sha(w/'replay.dat')
    parent=R/'scratch/transceiver-lo-rf-only/latest.dat';e=json.loads((P/'evidence/lo-rf-only.json').read_text());assert sha(parent)==e['waveform_sha256']
    original=load(parent);recorded=data['recorded'];lo,hi=800e-9,1000e-9
    grid=np.unique(np.r_[lo,hi,original[(original[:,0]>lo)&(original[:,0]<hi),0],recorded[(recorded[:,0]>lo)&(recorded[:,0]<hi),0]])
    metrics={};passed=True
    for i,node in enumerate(nodes,1):
        ref=np.interp(grid,original[:,0],original[:,i]);obs=np.interp(grid,recorded[:,0],recorded[:,i]);err=obs-ref
        metric=dict(rms_error_v=float(np.sqrt(np.trapezoid(err**2,grid)/(hi-lo))),maximum_error_v=float(max(abs(err))))
        if node.startswith('v(o'):
            rising=edge_alignment(rises(grid,ref),rises(grid,obs))
            falling=edge_alignment(rises(grid,3.3-ref),rises(grid,3.3-obs))
            metric.update(rising_edges=rising,falling_edges=falling)
            passed &= metric['rms_error_v']<=.02 and metric['maximum_error_v']<=.1 and rising['passes'] and falling['passes']
        metrics[node]=metric
    out=dict(completed=True,reproduction_pass=bool(passed),limits=limits,metrics=metrics,waveform_hashes=hashes,parent_waveform_sha256=e['waveform_sha256'],checker_sha256=sha(Path(__file__)),
        limitations=['Diagnostic reproduction tolerances, not mixer operating specifications.','Fixed-CM mechanism interpretation requires reproduction_pass; physical autonomous validation remains separate.'])
    (P/'evidence/lo-common-mode-reproduction.json').write_text(json.dumps(out,indent=2,allow_nan=False)+'\n');print(json.dumps(out,indent=2,allow_nan=False))
