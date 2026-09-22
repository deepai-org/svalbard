"""Relate observed weak cycles to saved upstream state; correlation not causality."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
source=P/'evidence/lo-rf-cycle-comparison.json';r=json.loads(source.read_text());w=R/'scratch/transceiver-lo-rf-only/latest.dat'
assert hashlib.sha256(w.read_bytes()).hexdigest()==r['waveform_hashes']['rf_only']
with w.open() as f:h=f.readline().lower().split()
names=['time','v(ip)','v(in)','v(qp)','v(qn)','v(bip)','v(bin)','v(bqp)','v(bqn)','v(ctrl)','v(ref)']
a=np.loadtxt(w,skiprows=1,usecols=[h.index(n) for n in names]);t=a[:,0]
ref=a[:,names.index('v(ref)')];k=np.flatnonzero((ref[:-1]<1.65)&(ref[1:]>=1.65));edges=t[k]+(1.65-ref[k])*np.diff(t)[k]/np.diff(ref)[k]
reports=[]
for leg in ['ip','in','qp','qn']:
    cycles=r['results']['rf_only']['v(o'+leg+')']['cycles'];rows=[]
    for c in cycles:
        start=c['start_ns']*1e-9;end=start+c['period_ps']*1e-12
        selected=(t>=start)&(t<=end);assert selected.any()
        j=np.searchsorted(edges,start,side='right')-1;assert j>=0
        features={}
        for name in ['v('+leg+')','v(b'+leg+')','v(ctrl)']:
            values=a[selected,names.index(name)]
            features[name+'_mean']=float(np.mean(values));features[name+'_swing']=float(np.ptp(values))
        rows.append(dict(start_ns=c['start_ns'],since_reference_ns=float((start-edges[j])*1e9),
            weak=c['peak_v']<2.64 or c['trough_v']>.66,
            margin_v=min(c['peak_v']-2.64,.66-c['trough_v']),features=features))
    groups={}
    for weak in (False,True):
        group=[x for x in rows if x['weak']==weak]
        if group:groups[str(weak)]=dict(count=len(group),reference_phase_ns_range=[min(x['since_reference_ns'] for x in group),max(x['since_reference_ns'] for x in group)],
            feature_means={key:float(np.mean([x['features'][key] for x in group])) for key in group[0]['features']})
    phase_bins=[]
    for lo in np.arange(0,51.2,6.4):
        group=[x for x in rows if lo<=x['since_reference_ns']<lo+6.4]
        phase_bins.append(dict(start_ns=float(lo),cycles=len(group),weak=sum(x['weak'] for x in group)))
    reports.append(dict(leg=leg,groups=groups,reference_phase_bins=phase_bins,cycles=rows))
out=dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),results=reports,
    limitations=['Cycle-bounded means/ranges are diagnostics, not carrier-envelope separation.',
      'Observed correlation with reference timing does not identify its coupling path.',
      'Internal MID/LOCAL and PRE output nodes are not saved in this waveform.'])
(P/'evidence/lo-weak-cycle-trace.json').write_text(json.dumps(out,indent=2)+'\n')
for r in reports:print(r['leg'],r['groups'],r['reference_phase_bins'])
