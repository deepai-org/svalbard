#!/usr/bin/env python3
"""Audit active reduction without claiming it represents the complete loop."""
import hashlib,json,re
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-pfd-only-breakpoint';B=R/'scratch/transceiver-pfd-buffered-reference'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((W/'manifest.json').read_text());src=B/'pwl.spice';assert sha(src)==m['baseline_deck_sha256'];assert sha(W/'pfd.spice')==m['deck_sha256_before']
allowed=['IP BPCP 0 20u\n','IN VDIV BNCP 20u\n','XCP UP DN PUMP BPCP BNCP VDIV 0 pt_charge_pump\n','VSENSE PUMP CTRL 0\n','XFILT CTRL 0 pt_loop_filter\n','.ic v(CTRL)=1.08 v(XFILT.Z)=1.08\n']
assert m['removed_lines']==allowed
original=src.read_text().split('.control')[0];expected=original
for line in allowed:assert expected.count(line)==1;expected=expected.replace(line,'')
d=(W/'pfd.spice').read_text();assert d.split('.control')[0]==expected and 'tran 2p 800n 0 2p uic' in d
for path,h in m['source_sha256_before'].items():
 if path.startswith('/screen/'):assert sha(P/'analog'/path.removeprefix('/screen/'))==h
out=dict(status='pending_PFD_only_diagnostic',manifest=m,declared_reduction_verified=True)
if (W/'result.json').exists():
 r=json.loads((W/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before']
 for ext,h in r['artifacts_sha256'].items():assert sha(W/('pfd'+ext))==h
 log=(W/'pfd.log').read_text();failure=re.search(r'Timestep too small; time = ([0-9.e+-]+)',log)
 out.update(status='terminal_PFD_only_diagnostic',run_record=r,completed=False,failure_time_ns=float(failure.group(1))*1e9 if failure else None)
 if (W/'pfd.dat').exists():
  with (W/'pfd.dat').open() as f:assert f.readline().lower().split()==['time','v(refraw)','v(ref)','v(fb)','v(up)','v(dn)']
  a=np.loadtxt(W/'pfd.dat',skiprows=1);assert a.shape[1]==6 and np.isfinite(a).all() and np.all(np.diff(a[:,0])>=0)
  out.update(actual_stop_ns=float(a[-1,0]*1e9),completed=bool(r['returncode']==0 and not r['timed_out'] and 'aborted' not in log.lower() and a[-1,0]>=800e-9),equal_printed_time_intervals=int(np.sum(np.diff(a[:,0])==0)))
  mask=(a[:,0]>=203e-9)&(a[:,0]<=305.4e-9)
  if mask.sum()>2:
   w=a[mask];out['observed_window_ns']=[203,305.4];out['outputs']={name:dict(range_v=[float(w[:,col].min()),float(w[:,col].max())],above_midrail_duration_ns=float(np.trapezoid((w[:,col]>1.65).astype(float),w[:,0])*1e9)) for name,col in [('up',4),('down',5)]}
out['limitations']=['Removing pump also removes its gate loading and filter/control interaction; completion would not isolate those contributions individually.', 'Forced clocks, one nominal scenario; no autonomous frequency acquisition, jitter or metastability qualification.', 'Output midrail durations are observations, not a PFD functional pass criterion.']
(P/'evidence/pfd-only-breakpoint-screen.json').write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out.get('completed'),out.get('failure_time_ns'))
