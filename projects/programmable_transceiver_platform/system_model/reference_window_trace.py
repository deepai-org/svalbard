"""Native-time two-rail decision windows; measured fixtures, not a converter model."""
import hashlib,json
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parents[1];R=P.parents[1]
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()
def window(t,y,lo,hi):
    assert t[0]<=lo<hi<=t[-1]
    inside=(t>lo)&(t<hi)
    tt=np.r_[lo,t[inside],hi]
    yy=np.r_[np.interp(lo,t,y),y[inside],np.interp(hi,t,y)]
    return tt,yy
# Nonuniform sampling and clipped boundaries: integral mean of y=2t+1 is 3.
test_t,test_y=window(np.array([0.,.1,1.4,2.]),np.array([1.,1.2,3.8,5.]),.25,1.75)
assert abs(np.trapezoid(test_y,test_t)/(test_t[-1]-test_t[0])-3)<1e-14
source=P/'evidence/adc-sar8-reference-reservoir-screen.json'
audit=json.loads(source.read_text());assert not audit['pending_or_incomplete_cases']
rows=[];traces={};hashes={}
for case in audit['cases']:
    path=R/'scratch/transceiver-adc-sar8-reference-reservoir'/(case['name']+'.dat')
    hashes[case['name']]=sha(path);assert hashes[case['name']]==case['artifacts_sha256']['.dat']
    with path.open() as f:header=f.readline().lower().split()
    a=np.loadtxt(path,skiprows=1,usecols=[header.index(x) for x in ['time','v(vh)','v(vl)']])
    t=a[:,0];assert np.isfinite(a).all() and np.all(np.diff(t)>0)
    for frame in case['frames']:
        for bit in range(7,-1,-1):
            lo=(frame['hold_ns']+.2+5*(7-bit))*1e-9;hi=lo+.15e-9
            tt,vh=window(t,a[:,1],lo,hi);_,vl=window(t,a[:,2],lo,hi)
            signals={'high':vh,'low':vl,'span':vh-vl,'common_mode':(vh+vl)/2}
            metrics={n:dict(time_mean_v=float(np.trapezoid(v,tt)/(hi-lo)),min_v=float(v.min()),max_v=float(v.max()),motion_v=float(np.ptp(v))) for n,v in signals.items()}
            key=f"{case['name']}_{frame['hold_ns']}_{bit}"
            traces[key]=np.column_stack([tt,vh,vl])
            rows.append(dict(case=case['name'],hold_ns=frame['hold_ns'],bit=bit,window_ns=[lo*1e9,hi*1e9],trace_key=key,metrics=metrics))
artifact=P/'evidence/reference-window-traces.npz';np.savez_compressed(artifact,**traces)
report=dict(status='measured_two_rail_windows_only',windows=rows,source_sha256=sha(source),waveform_sha256=hashes,script_sha256=sha(Path(__file__)),trace_sha256=sha(artifact),limitations=['Nominal single-converter reservoir fixture; not simultaneous I/Q loading.', 'Pre-evaluation windows match existing bench; not physical comparator aperture qualification.', 'Time weighting avoids adaptive-grid sample-count bias; boundary interpolation remains numerical.', 'Measured trajectories do not predict changed input codes, rail loads, or reference topology.'])
(P/'evidence/reference-window-traces.json').write_text(json.dumps(report,indent=2)+'\n')
print(len(rows),'windows; maximum motion mV:',{n:max(r['metrics'][n]['motion_v'] for r in rows)*1000 for n in signals})
