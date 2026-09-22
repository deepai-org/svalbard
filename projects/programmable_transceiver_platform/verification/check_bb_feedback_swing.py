#!/usr/bin/env python3
"""Measured transfer compression, without a post-hoc qualification threshold."""
import argparse,hashlib,json
ap=argparse.ArgumentParser();ap.add_argument("--large-input",action="store_true");args=ap.parse_args()
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-bb-feedback-swing';B=R/'scratch/transceiver-bb-feedback-gain'
if args.large_input:
 W=R/'scratch/transceiver-bb-large-input-swing';B=R/'scratch/transceiver-bb-large-input-gain'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((W/'result.json').read_text());assert r['sources_before']==r['sources_after'];rows=[]
assert len(r['cases'])==(1 if args.large_input else 4)
for c in r['cases']:
 n=c['name'];assert c['returncode']==0 and sha(B/(n+'.spice'))==c['parent_sha256']
 for ext,h in c['artifacts_sha256'].items():assert sha(W/(n+ext))==h
 log=(W/(n+'.log')).read_text().lower();assert not any(x in log for x in ['error','warning','aborted'])
 with (W/(n+'.dat')).open() as f:h=f.readline().lower().split()
 a=np.loadtxt(W/(n+'.dat'),skiprows=1);assert h[1:]==[x.lower() for x in c['probes']] and a.shape==(161,len(h)) and np.isfinite(a).all()
 x=a[:,0];assert np.allclose(x,np.linspace(-.4,.4,161),rtol=0,atol=1e-12)
 def v(n):return a[:,h.index(n)]
 y=v('v(op)')-v('v(on)');z=int(abs(x).argmin());gain=float((y[z+1]-y[z-1])/(x[z+1]-x[z-1]))
 points=[]
 for target in (-.4,-.2,-.1,-.05,.05,.1,.2,.4):
  i=int(abs(x-target).argmin());margins=[float(v(f'@m.xdut.{s}.{d}.m0[vds]')[i]-v(f'@m.xdut.{s}.{d}.m0[vdsat]')[i]) for s in ('xa','xb') for d in ('xip','xin','xtail')]
  points.append(dict(source_differential_v=float(x[i]),output_differential_v=float(y[i]),secant_gain_over_central_gain=float((y[i]-y[z])/(x[i]*gain)),output_common_mode_v=float((v('v(op)')[i]+v('v(on)')[i])/2),worst_reported_headroom_v=min(margins)))
 rows.append(dict(name=n,central_gain=gain,points=points,monotonic=bool(np.all(np.diff(y)>0)),zero_output_common_mode_v=float((v('v(op)')[z]+v('v(on)')[z])/2)))
out=dict(completed=True,provenance=r,cases=rows,limitations=['Quasistatic DC sweep only, not distortion, settling, hysteresis, or dynamic stability.','Central gain uses +/-5mV finite difference, not an infinitesimal derivative.','Headroom uses previously checked stationary PMOS convention; dynamic reverse operation not qualified.','No acceptance threshold, whole-chain gain multiplication or candidate promotion.'])
(P/'evidence'/('bb-large-input-swing.json' if args.large_input else 'bb-feedback-swing.json')).write_text(json.dumps(out,indent=2)+'\n')
for row in rows:print(row['name'],row['central_gain'],[(p['source_differential_v'],round(p['output_differential_v'],5),round(p['secant_gain_over_central_gain'],5)) for p in row['points'] if p['source_differential_v']>0])
