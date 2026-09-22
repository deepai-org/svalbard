"""Early differential-crossing diagnostic, not a lock detector."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-lo-interstage-autonomous'
parent=P/'evidence/lo-interstage-failure-trace.json';e=json.loads(parent.read_text())
path=W/'latest.dat';before=path.stat();digest=hashlib.sha256();bins=[];previous=None
with path.open('rb') as f:
    line=f.readline();digest.update(line);h=line.decode().lower().split()
    cols=[h.index(n) for n in ('v(p)','v(n)','v(q7p)','v(q7n)','v(fb)')]
    for line in f:
        digest.update(line);s=line.split();t=float(s[0])
        if t>=1e-6:break
        v=[float(s[k]) for k in cols];signals=[v[0]-v[1],v[2]-v[3],v[4]-1.65]
        b=int(t/100e-9)
        while len(bins)<=b:bins.append(dict(start_ns=100*len(bins),rises=[0,0,0],minimum=[1e99]*3,maximum=[-1e99]*3))
        for k,x in enumerate(signals):
            bins[b]['minimum'][k]=min(bins[b]['minimum'][k],x);bins[b]['maximum'][k]=max(bins[b]['maximum'][k],x)
            if previous is not None and previous[k]<0<=x:bins[b]['rises'][k]+=1
        previous=signals
assert path.stat().st_size==before.st_size and path.stat().st_mtime_ns==before.st_mtime_ns
out=dict(parent_trace_sha256=hashlib.sha256(parent.read_bytes()).hexdigest(),parent_verified_waveform_sha256=e['waveform_sha256'],prefix_sha256=digest.hexdigest(),signals=['P-N','Q7P-Q7N','FB-1.65'],bins=bins,
    limitations=['Early prefix of previously verified complete waveform; fixed zero crossings can count low-amplitude chatter.',
      'No divide-ratio qualification from edge counts alone.'])
(P/'evidence/lo-differential-startup.json').write_text(json.dumps(out,indent=2)+'\n')
for b in bins:print(b['start_ns'],b['rises'])
