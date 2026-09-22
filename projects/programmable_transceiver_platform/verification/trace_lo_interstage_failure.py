"""Streaming full-run timing trace; no autonomous-clock qualification."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
W=R/'scratch/transceiver-lo-interstage-autonomous'
result=json.loads((W/'result.json').read_text());assert result['returncode']==0 and not result['timed_out']
names=['v(p)','v(n)','v(oip)','v(oin)','v(oqp)','v(oqn)','v(ctrl)','v(fb)','v(ref)']
bins=[];previous=None;digest=hashlib.sha256();rows=0
with (W/'latest.dat').open('rb') as f:
    line=f.readline();digest.update(line);header=line.decode().lower().split();cols=[header.index(n) for n in names]
    for line in f:
        digest.update(line);fields=line.split();t=float(fields[0]);v=[float(fields[k]) for k in cols]
        assert all(np.isfinite(x) for x in v)
        b=int(t/100e-9)
        while len(bins)<=b:
            bins.append(dict(start_ns=len(bins)*100,rows=0,minimum=[float('inf')]*len(names),maximum=[-float('inf')]*len(names),rises=[0]*len(names)))
        bucket=bins[b];bucket['rows']+=1
        for k,x in enumerate(v):
            bucket['minimum'][k]=min(bucket['minimum'][k],x);bucket['maximum'][k]=max(bucket['maximum'][k],x)
            if previous is not None and previous[k]<1.65<=x:bucket['rises'][k]+=1
        previous=v;rows+=1
assert digest.hexdigest()==result['artifacts_sha256']['.dat']
out=dict(waveform_sha256=digest.hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),names=names,bins=bins,rows=rows,
    limitations=['100ns bins with fixed 1.65V crossings; low-swing oscillations may not cross this threshold.',
                 'Transient seeded startup only; no phase noise or cold-start qualification.'])
(P/'evidence/lo-interstage-failure-trace.json').write_text(json.dumps(out,indent=2)+'\n')
for b in bins:
    if b['start_ns']<1000 or b['start_ns']%1000==0:
        print(b['start_ns'],b['rises'], 'CTRL',b['minimum'][6],b['maximum'][6])
