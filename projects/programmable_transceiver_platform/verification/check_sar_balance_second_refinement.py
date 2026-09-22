"""Second refinement: reproduce probes, compare margins and integrate charge."""
import contextlib
import io
import json
from pathlib import Path
import runpy
import numpy as np

HERE=Path(__file__).resolve().parent
R=HERE.parents[2]
P=R/'projects/programmable_transceiver_platform'

def integrate(t,y,lo,hi):
    """Integral of piecewise-linear samples, including exact window endpoints."""
    assert np.all(np.diff(t)>0) and t[0]<=lo<hi<=t[-1]
    grid=np.r_[lo,t[(t>lo)&(t<hi)],hi]
    values=np.interp(grid,t,y)
    return float(np.sum(np.diff(grid)*(values[:-1]+values[1:])/2))

def charge_metrics(t,y,lo,hi):
    """Net and absolute charge of the same piecewise-linear current.

    Split at zero crossings before integrating abs(I); otherwise trapezoids
    across a sign change overestimate total charge movement.
    """
    net=integrate(t,y,lo,hi)
    grid=np.r_[lo,t[(t>lo)&(t<hi)],hi]
    values=np.interp(grid,t,y)
    crossings=[]
    for index in np.flatnonzero(values[:-1]*values[1:]<0):
        crossings.append(grid[index]+(grid[index+1]-grid[index])*
                         (-values[index])/(values[index+1]-values[index]))
    split=np.unique(np.r_[grid,crossings])
    current=np.interp(split,grid,values)
    total=integrate(split,abs(current),lo,hi)
    assert total+1e-25>=abs(net)
    return dict(signed_charge_c=net,absolute_charge_c=total,
                positive_charge_c=(total+net)/2,
                negative_charge_magnitude_c=(total-net)/2,
                net_to_absolute_ratio=abs(net)/total if total else None)

def controls():
    t=np.array([0.,.2,.7,1.])
    assert abs(integrate(t,2*t+3,.1,.9)-3.2)<1e-14
    assert abs(integrate(t,-2*t-3,.1,.9)+3.2)<1e-14
    assert abs(integrate(t,np.ones(4)*4e-3,.1,.9)-.0032)<1e-16
    # A single sign-changing segment has zero net but nonzero activity.
    cancellation=charge_metrics(np.array([0.,1.]),np.array([-1.,1.]),0.,1.)
    assert cancellation['signed_charge_c']==0
    assert cancellation['absolute_charge_c']==.5
    assert cancellation['positive_charge_c']==.25
    assert cancellation['negative_charge_magnitude_c']==.25
    # Subdividing the same linear waveform cannot change the answer.
    split=charge_metrics(t,2*t-1,0.,1.)
    assert abs(split['absolute_charge_c']-.5)<1e-14
    assert charge_metrics(t,np.zeros(4),0.,1.)['net_to_absolute_ratio'] is None
    try:integrate(t,t,-.1,.9)
    except AssertionError:pass
    else:raise AssertionError('Out-of-record integration was accepted')


def main():
    controls()
    with contextlib.redirect_stdout(io.StringIO()):
        previous=runpy.run_path(str(HERE/'check_sar_balance_refinement.py'))
    assert 'fine' in previous
    sha=previous['sha']
    manifests={}
    for label in ('baseline','instrumented'):
        prepared=R/f'scratch/transceiver-sar-balance-second-{label}-prepared'
        parent=R/f'scratch/transceiver-sar-balance-refined-{label}-prepared'
        run=R/f'scratch/transceiver-sar-balance-refined-{label}'
        m=json.loads((prepared/'manifest.json').read_text())
        assert sha(parent/'manifest.json')==m['parent_preparation_sha256']
        assert sha(run/'result.json')==m['parent_result_sha256']
        assert sha(P/'evidence/sar-balance-refinement.json')==m['parent_comparison_sha256']
        assert sha(prepared/'baseline.spice')==m['artifacts_sha256']['baseline.spice']
        assert (prepared/'baseline.spice').read_text().replace('tran 5p 209.9n 0 1.25p','tran 5p 209.9n 0 2.5p')==(parent/'baseline.spice').read_text()
        manifests[label]=sha(prepared/'manifest.json')
    if not all((R/f'scratch/transceiver-sar-balance-second-{label}/result.json').exists() for label in manifests):
        print('Integration controls and exact preparation checks pass; terminal results pending.')
        return
    current={label:previous['load']('sar-balance-second-'+label) for label in manifests}
    for label,data in current.items():
        assert data[2]['sources_before']==previous['fine'][label][2]['sources_before']
        prepared=R/f'scratch/transceiver-sar-balance-second-{label}-prepared'
        run=R/f'scratch/transceiver-sar-balance-second-{label}'
        assert sha(run/'baseline.spice')==sha(prepared/'baseline.spice')
    def sample(data,node,t):
        header,a,_=data
        return np.interp(t,a[:,0],a[:,header.index(node)])
    times=np.array([hold+.5+5*j for hold in (70,120,170) for j in range(8)])*1e-9
    margins={}
    for label in manifests:
        residues={}
        for stage,data in [('5ps',previous['coarse'][label]),('2.5ps',previous['fine'][label]),('1.25ps',current[label])]:
            residues[stage]=sample(data,'v(hp)',times)-sample(data,'v(hn)',times)
        margins[label]=dict(times_ns=(times*1e9).tolist(),residues_v={k:v.tolist() for k,v in residues.items()},
            previous_maximum_change_v=float(max(abs(residues['2.5ps']-residues['5ps']))),
            latest_maximum_change_v=float(max(abs(residues['1.25ps']-residues['2.5ps']))),
            latest_minimum_absolute_margin_v=float(min(abs(residues['1.25ps']))),
            latest_signs_match=bool(np.array_equal(np.sign(residues['1.25ps']),np.sign(residues['2.5ps']))))
    charges=[]
    for hold in (70,120,170):
        for j in range(8):
            lo,hi=(hold+5*j+np.array([2.5,3.6]))*1e-9
            rails={}
            for rail in ('h','l'):
                stages={}
                for stage,data in [('5ps',previous['coarse']['instrumented']),('2.5ps',previous['fine']['instrumented']),('1.25ps',current['instrumented'])]:
                    header,a,_=data
                    y=a[:,header.index('i(vsense'+rail+')')]
                    stages[stage]=charge_metrics(a[:,0],y,lo,hi)
                rails[rail]=dict(stages=stages,
                    previous_change_c=stages['2.5ps']['signed_charge_c']-stages['5ps']['signed_charge_c'],
                    latest_change_c=stages['1.25ps']['signed_charge_c']-stages['2.5ps']['signed_charge_c'],
                    latest_absolute_charge_change_c=stages['1.25ps']['absolute_charge_c']-stages['2.5ps']['absolute_charge_c'])
            charges.append(dict(hold_ns=hold,bit=7-j,start_ns=lo*1e9,end_ns=hi*1e9,rails=rails))
    comparisons={'second_pair':previous['compare'](current['baseline'],current['instrumented'])}
    comparisons.update({label+'_refinement':previous['compare'](previous['fine'][label],current[label]) for label in manifests})
    report=dict(completed=True,numerical_convergence_established=False,comparisons=comparisons,
        preclock_margins=margins,switching_charge=charges,
        preparation_hashes=manifests,checker_sha256=sha(Path(__file__)),
        parent_report_sha256=sha(P/'evidence/sar-balance-refinement.json'),
        waveform_hashes={label:data[2]['artifacts_sha256']['.dat'] for label,data in current.items()},
        limitations=['Net and absolute charge expose cancellation; these windows do not cover the full conversion.',
            '5ps current probe failed reproduction and is retained only as a numerical comparison.',
            'No physical charge-error budget is established; no charge tolerance pass is inferred.',
            'Two refinements do not prove asymptotic convergence or physical accuracy.'])
    (P/'evidence/sar-balance-second-refinement.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(comparisons=comparisons,preclock_margins=margins),indent=2))

if __name__=='__main__':main()
