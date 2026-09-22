"""Scoped first-frame observations from a terminal failed connected receiver run."""
import argparse,hashlib,json
ap=argparse.ArgumentParser();ap.add_argument("--second-acquisition",action="store_true");args=ap.parse_args()
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-rx-adc-event-offsets/early'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((W/'result.json').read_text());assert r['returncode']!=0 and r['sources_before']==r['sources_after']
for ext,h in r['artifacts_sha256'].items():assert sha(W/('connected'+ext))==h
with (W/'connected.dat').open() as f:h=f.readline().lower().split()
a=np.loadtxt(W/'connected.dat',skiprows=1);t=a[:,0]
assert a.shape[1]==len(h) and np.isfinite(a).all() and np.all(np.diff(t)>0) and t[-1]>520e-9
v=lambda n:a[:,h.index(n)]
def window(y,lo,hi):
 lo*=1e-9;hi*=1e-9;assert t[0]<=lo<hi<=t[-1]
 mask=(t>lo)&(t<hi);tt=np.r_[lo,t[mask],hi];yy=np.r_[np.interp(lo,t,y),y[mask],np.interp(hi,t,y)]
 return dict(min_v=float(yy.min()),max_v=float(yy.max()),mean_v=float(np.trapezoid(yy,tt)/(hi-lo)))
rows=[]
hold=520 if args.second_acquisition else 470
for label,prefix,fp,fn in [('I','','fip','fin'),('Q','q_','fqp','fqn')]:
 source=window(v('v('+fp+')')-v('v('+fn+')'),hold,hold+.1)
 driver=window(v(f'v(xadc.{prefix}ip)')-v(f'v(xadc.{prefix}in)'),hold,hold+.1)
 held=window(v(f'v(xadc.{prefix}hp)')-v(f'v(xadc.{prefix}hn)'),hold+.2,hold+.35)
 if args.second_acquisition:
  rows.append(dict(channel=label,hold_ns=hold,source_over_turnoff=source,driver_over_turnoff=driver,held_before_first_comparison=held,
   held_minus_source_envelope_v=[held['min_v']-source['max_v'],held['max_v']-source['min_v']]))
  continue
 mask=(t>=509e-9)&(t<=509.5e-9);assert mask.any()
 code=np.zeros(mask.sum(),dtype=int);bits=[]
 for bit in range(8):
  yy=v(f'v(xadc.{prefix}d{bit})')[mask];code+=(yy>1.65).astype(int)*(1<<bit)
  bits.append(dict(bit=bit,min_v=float(yy.min()),max_v=float(yy.max())))
 rows.append(dict(channel=label,source_over_turnoff=source,driver_over_turnoff=driver,held_before_first_comparison=held,
 held_minus_source_envelope_v=[held['min_v']-source['max_v'],held['max_v']-source['min_v']],
 late_code_window_ns=[509,509.5],threshold_v=1.65,observed_codes=sorted(map(int,np.unique(code))),bits=bits,
 done_window=window(v(f'v(xadc.{prefix}done)'),509,509.5)))
out=dict(status='second_acquisition_from_failed_run' if args.second_acquisition else 'first_frame_observations_from_failed_run',completed=False,cases=rows,artifacts_sha256=r['artifacts_sha256'],
 limitations=['No acceptance threshold or ENOB claim; source is approximately half a nominal differential ADC step and near Nyquist aliasing condition.',
 'Turnoff interval is a source envelope, not a calibrated effective aperture; held plate difference may include switch and CDAC initial-state effects.',
 'Thresholded code and DONE observations do not establish correct analog conversion or repeatability.',
 'Second acquisition uses the repeated 10ns schedule, but one small-signal transition does not bound settling across inputs or histories.' if args.second_acquisition else 'Only first frame observed here; longer startup acquisition is not the repeated 10ns acquisition budget.'])
(P/'evidence'/('rx-adc-second-acquisition.json' if args.second_acquisition else 'rx-adc-first-frame.json')).write_text(json.dumps(out,indent=2)+'\n')
for x in rows:print(x['channel'],x['source_over_turnoff'],x['held_before_first_comparison'],x.get('observed_codes'),x.get('done_window'))
