"""Pulse-quality comparison, strictly gated on recorded replay reproduction."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
import numpy as np
from compare_lo_rf_cycles import metrics,load,nodes

HERE=Path(__file__).resolve().parent
P=HERE.parent
R=P.parents[1]

def diagnostic(t,y):
    assert len(t)==len(y) and len(t)>1 and np.all(np.diff(t)>0)
    assert np.isfinite(t).all() and np.isfinite(y).all()
    lo,hi=800e-9,1000e-9
    assert t[0]<=lo and t[-1]>=hi
    crossing=np.flatnonzero((y[:-1]<1.65)&(y[1:]>=1.65))
    edges=t[crossing]+(1.65-y[crossing])*np.diff(t)[crossing]/np.diff(y)[crossing]
    edges=edges[(edges>=lo)&(edges<=hi)]
    # Complete-cycle metrics omit partial cycles at both window boundaries.
    # Keep boundary-inclusive gaps so a clock stopping mid-window is visible.
    coverage=dict(rising_edges_in_window=len(edges),
        maximum_boundary_inclusive_gap_ps=float(max(np.diff(np.r_[lo,edges,hi]))*1e12),
        leading_gap_ps=float((edges[0]-lo if len(edges) else hi-lo)*1e12),
        trailing_gap_ps=float((hi-edges[-1] if len(edges) else hi-lo)*1e12))
    try:
        result=metrics(t,y)
    except AssertionError:
        return dict(complete_cycle_analysis=False,
            reason='No complete cycles or nonunique falling crossing; inspect raw waveform.',
            minimum_v=float(min(y)),maximum_v=float(max(y)),edge_coverage=coverage)
    result['complete_cycle_analysis']=True
    result['edge_coverage']=coverage
    return result


def controls():
    t=np.arange(799,1001,.01)*1e-9
    phase=((t-799e-9)/1e-9)%1
    full=diagnostic(t,np.where(phase<.5,3.3,0.))
    weak=diagnostic(t,np.where(phase<.5,2.,1.))
    narrow=diagnostic(t,np.where(phase<.2,3.3,0.))
    assert full['complete_cycle_analysis'] and full['weak_peak_cycles']==0
    assert weak['weak_peak_cycles']==weak['complete_cycles']
    assert weak['high_trough_cycles']==weak['complete_cycles']
    assert narrow['duty_range'][1]<.23 and full['duty_range'][0]>.47
    stopped=diagnostic(t,np.ones(len(t))*1.5)
    assert not stopped['complete_cycle_analysis']
    assert stopped['edge_coverage']['rising_edges_in_window']==0
    partial=np.where(phase<.5,3.3,0.)
    partial[t>=900e-9]=0
    stalled=diagnostic(t,partial)
    assert stalled['complete_cycle_analysis']  # Earlier good cycles still exist.
    assert stalled['edge_coverage']['trailing_gap_ps']>99000
    assert full['edge_coverage']['maximum_boundary_inclusive_gap_ps']<1100


def main():
    controls()
    with contextlib.redirect_stdout(io.StringIO()):
        gate=runpy.run_path(str(HERE/'check_lo_common_mode_replay.py'))
    # Test the current checker execution, not a possibly stale report file.
    if 'out' not in gate:
        print('Pulse amplitude/duty/no-oscillation controls pass; terminal replay results pending.')
        return
    if not gate['out']['reproduction_pass']:
        print('Recorded replay failed reproduction; fixed-common-mode interpretation is blocked.')
        return
    results={}
    for mode in ('recorded','fixed'):
        path=R/f'scratch/transceiver-lo-common-mode-{mode}/replay.dat'
        data=load(path,gate['out']['waveform_hashes'][mode])
        results[mode]={node:diagnostic(data[:,0],data[:,i+1]) for i,node in enumerate(nodes)}
    report=dict(window_ns=[800,1000],results=results,
        reproduction_report_sha256=hashlib.sha256((P/'evidence/lo-common-mode-reproduction.json').read_bytes()).hexdigest(),
        waveform_hashes=gate['out']['waveform_hashes'],
        source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in
            (Path(__file__),HERE/'compare_lo_rf_cycles.py',HERE/'check_lo_common_mode_replay.py')},
        physical_qualification=False,
        limitations=['Common-mode intervention removes all variation, not just low-frequency drift.',
            'Recorded input replay is not autonomous oscillator feedback or startup.',
            'Amplitude thresholds are diagnostics, not validated mixer switching requirements.',
            'No random phase noise, yield or extracted loading qualification.'])
    (P/'evidence/lo-common-mode-cycle-comparison.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    for mode,rows in results.items():
        for node,result in rows.items():print(mode,node,{k:v for k,v in result.items() if k!='cycles'})

if __name__=='__main__':main()
