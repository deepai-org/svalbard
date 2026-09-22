"""Matched refinement comparison; pair agreement is distinct from convergence."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(name):
    w=R/f'scratch/transceiver-{name}';r=json.loads((w/'result.json').read_text())
    assert r['returncode']==0 and not r['timed_out'] and r['sources_before']==r['sources_after']
    for ext,h in r['artifacts_sha256'].items():assert sha(w/('baseline'+ext))==h
    with (w/'baseline.dat').open() as f:header=f.readline().lower().split()
    a=np.loadtxt(w/'baseline.dat',skiprows=1);assert np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
    assert abs(a[-1,0]-209.9e-9)<1e-15
    return header,a,r

def compare(first,second):
    h,a,_=first;k,b,_=second
    grid=np.unique(np.r_[70e-9,209e-9,a[(a[:,0]>70e-9)&(a[:,0]<209e-9),0],b[(b[:,0]>70e-9)&(b[:,0]<209e-9),0]])
    def at(header,array,node,t):return np.interp(t,array[:,0],array[:,header.index('v('+node+')')])
    errors={node:float(max(abs(at(h,a,node,grid)-at(k,b,node,grid)))) for node in ('hp','hn','vh','vl')}
    times=np.array([hold+2.4+5*j for hold in (70,120,170) for j in range(8)])*1e-9
    q=at(h,a,'qp',times)-at(h,a,'qn',times);other=at(k,b,'qp',times)-at(k,b,'qn',times)
    match=bool(np.all(abs(q)>2.97) and np.all(abs(other)>2.97) and np.array_equal(np.sign(q),np.sign(other)))
    return dict(analog_errors_v=errors,all_decisions_match=match,within_10uv_and_decisions=bool(max(errors.values())<=1e-5 and match))

parents={'baseline':'sar-bottom-plates','instrumented':'sar-reference-balance'}
for label,parent in parents.items():
    b=R/f'scratch/transceiver-sar-balance-refined-{label}-prepared';old=R/f'scratch/transceiver-{parent}-prepared'
    m=json.loads((b/'manifest.json').read_text())
    assert sha(old/'manifest.json')==m['parent_preparation_sha256']
    assert sha(b/'baseline.spice')==m['artifacts_sha256']['baseline.spice']
    assert (b/'baseline.spice').read_text().replace('tran 5p 209.9n 0 2.5p','tran 5p 209.9n 0 5p')==(old/'baseline.spice').read_text()
if not all((R/f'scratch/transceiver-sar-balance-refined-{label}/result.json').exists() for label in parents):
    print('Matched timestep-only edits verified; terminal results pending.')
else:
    coarse={label:load(name) for label,name in parents.items()};fine={label:load('sar-balance-refined-'+label) for label in parents}
    for label in parents:
        assert fine[label][2]['sources_before']==coarse[label][2]['sources_before']
        w=R/f'scratch/transceiver-sar-balance-refined-{label}';b=w.with_name(w.name+'-prepared')
        assert sha(w/'baseline.spice')==sha(b/'baseline.spice')
    comparisons=dict(refined_pair=compare(fine['baseline'],fine['instrumented']),
        coarse_pair=compare(coarse['baseline'],coarse['instrumented']),
        baseline_refinement=compare(coarse['baseline'],fine['baseline']),
        instrumented_refinement=compare(coarse['instrumented'],fine['instrumented']))
    out=dict(completed=True,comparisons=comparisons,
        waveform_hashes={stage+'_'+label:data[2]['artifacts_sha256']['.dat'] for stage,items in [('coarse',coarse),('fine',fine)] for label,data in items.items()},
        checker_sha256=sha(Path(__file__)),limitations=['One refinement does not establish asymptotic convergence.',
        'Refined-pair agreement alone does not authorize use of coarse failed current probes.',
        'No current balance or physical circuit qualification is implied.'])
    (P/'evidence/sar-balance-refinement.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
