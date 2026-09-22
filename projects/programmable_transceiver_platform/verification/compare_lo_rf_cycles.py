"""Matched-window complete-cycle LO diagnostics, with full waveform hashes."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
nodes=['v(oip)','v(oin)','v(oqp)','v(oqn)']
def load(path,expected):
    digest=hashlib.sha256();rows=[];past=False
    with path.open('rb') as f:
        line=f.readline();digest.update(line);h=line.decode().lower().split();cols=[h.index(n) for n in nodes]
        for line in f:
            digest.update(line)
            if past:continue
            fields=line.split();t=float(fields[0])
            if t>1001e-9:past=True;continue
            if t>=799e-9:rows.append([t]+[float(fields[k]) for k in cols])
    assert digest.hexdigest()==expected
    a=np.asarray(rows);assert np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
    return a

def metrics(t,y):
    rises=np.flatnonzero((y[:-1]<1.65)&(y[1:]>=1.65))
    rt=t[rises]+(1.65-y[rises])*(t[rises+1]-t[rises])/(y[rises+1]-y[rises])
    cycles=[]
    for k in range(len(rises)-1):
        start,end=rt[k:k+2]
        if start<800e-9 or end>1000e-9:continue
        middle=(t>start)&(t<end);ct=np.r_[start,t[middle],end];cy=np.r_[1.65,y[middle],1.65]
        falls=np.flatnonzero((cy[:-1]>=1.65)&(cy[1:]<1.65))
        assert len(falls)==1
        j=falls[0];fall=ct[j]+(1.65-cy[j])*(ct[j+1]-ct[j])/(cy[j+1]-cy[j])
        cycles.append(dict(start_ns=float(start*1e9),period_ps=float((end-start)*1e12),
            peak_v=float(cy.max()),trough_v=float(cy.min()),duty=float((fall-start)/(end-start))))
    assert cycles
    return dict(complete_cycles=len(cycles),minimum_peak_v=min(c['peak_v'] for c in cycles),
        maximum_trough_v=max(c['trough_v'] for c in cycles),
        weak_peak_cycles=sum(c['peak_v']<2.64 for c in cycles),high_trough_cycles=sum(c['trough_v']>.66 for c in cycles),
        period_ps_range=[min(c['period_ps'] for c in cycles),max(c['period_ps'] for c in cycles)],
        duty_range=[min(c['duty'] for c in cycles),max(c['duty'] for c in cycles)],
        intervals_over_800ps=sum(c['period_ps']>800 for c in cycles),cycles=cycles)
def main():
    # Independent square-wave timing/amplitude control in the same time window.
    t=np.arange(799,1001,.01)*1e-9;y=np.where(((t-799e-9)/1e-9)%1<.5,3.3,0.)
    c=metrics(t,y);assert c['weak_peak_cycles']==c['high_trough_cycles']==0
    assert c['period_ps_range'][0]>980 and c['period_ps_range'][1]<1020
    paths={'baseline':R/'scratch/transceiver-latest-rf-loop-selective/latest.dat','rf_only':R/'scratch/transceiver-lo-rf-only/latest.dat'}
    b=json.loads((P/'evidence/latest-rf-loop-selective.json').read_text());c=json.loads((P/'evidence/lo-rf-only.json').read_text())
    expected={'baseline':b['provenance']['artifacts_sha256']['.dat'],'rf_only':c['waveform_sha256']}
    results={}
    for name,path in paths.items():
        a=load(path,expected[name]);results[name]={node:metrics(a[:,0],a[:,i+1]) for i,node in enumerate(nodes)}
        for node,m in results[name].items():print(name,node,{k:v for k,v in m.items() if k!='cycles'},flush=True)
    out=dict(window_ns=[800,1000],waveform_hashes=expected,results=results,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        limitations=['Same startup interval, not necessarily phase-aligned cycles or settled lock.',
          'Rail thresholds diagnostic only; switching effectiveness needs actual mixer loading/response.',
          'No intrinsic jitter or phase-noise qualification.'])
    (P/'evidence/lo-rf-cycle-comparison.json').write_text(json.dumps(out,indent=2)+'\n')

if __name__=='__main__':main()
