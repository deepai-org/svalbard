"""Matched late-window diagnostics; deterministic timing is not random jitter."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';ap=argparse.ArgumentParser();ap.add_argument('--candidate',action='store_true');args=ap.parse_args()
name='lo-interstage-autonomous' if args.candidate else 'lo-autonomous-baseline-window';E=P/'evidence'/(name+'.json');e=json.loads(E.read_text());assert e['completed']
p=R/('scratch/transceiver-lo-interstage-autonomous/late-window.npz' if args.candidate else 'scratch/transceiver-latest-rf-loop-selective/interstage-baseline-window.npz');sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();assert sha(p)==e['extraction_sha256']
z=np.load(p);a=z['samples'];h=z['names'].tolist();t=a[:,0];lo,hi=7424e-9,7936e-9;tt=np.r_[lo,t[(t>lo)&(t<hi)],hi]
def v(n):return np.interp(tt,t,a[:,h.index(n)])
def edges(y):
 k=np.flatnonzero((y[:-1]<1.65)&(y[1:]>=1.65));return tt[k]+(1.65-y[k])*np.diff(tt)[k]/np.diff(y)[k]
out=dict(completed=True,source_evidence_sha256=sha(E),window_ns=[7424,7936],nodes={},baseband={},currents={},limitations=['Seeded deterministic zero-input waveform; period modulation is not intrinsic jitter or phase noise.','Crossing counts and voltage ranges do not establish cold-start, lock robustness or mixer acceptance.'])
for n in ['v(oip)','v(oin)','v(oqp)','v(oqn)','v(fb)','v(ref)']:
 y=v(n);u=edges(y);dt=np.diff(u);out['nodes'][n]=dict(rises=len(u),min_v=float(y.min()),max_v=float(y.max()),max_period_ps=float(dt.max()*1e12) if len(dt) else None,min_period_ps=float(dt.min()*1e12) if len(dt) else None,intervals_over_800ps=int(np.sum(dt>800e-12)) if n.startswith('v(o') else None)
for leg in ['i','q']:
 y=v('v(f'+leg+'p)')-v('v(f'+leg+'n)');mean=np.trapezoid(y,tt)/(hi-lo);c=2*np.trapezoid((y-mean)*np.exp(-2j*np.pi*19.53125e6*(tt-lo)),tt)/(hi-lo)
 out['baseband'][leg]=dict(mean_v=float(mean),peak_to_peak_v=float(np.ptp(y)),reference_fundamental_peak_v=float(abs(c)))
for n in ['i(vbuf)','i(vpll)']:out['currents'][n]=float(np.trapezoid(v(n),tt)/(hi-lo))
out['control_range_v']=[float(v('v(ctrl)').min()),float(v('v(ctrl)').max())]
(P/'evidence'/(name+'-metrics.json')).write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
