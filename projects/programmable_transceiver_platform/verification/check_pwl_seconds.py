#!/usr/bin/env python3
"""Exact rational fixture audit, plus terminal outcome when available."""
import hashlib,json,re
from fractions import Fraction
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-pwl-seconds';B=R/'scratch/transceiver-pfd-buffered-reference'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((W/'manifest.json').read_text());src=B/'pwl.spice';assert sha(src)==m['baseline_deck_sha256'] and sha(W/'seconds.spice')==m['deck_sha256_before']
original=src.read_text();d=(W/'seconds.spice').read_text();old=next(x for x in original.splitlines() if x.startswith('VREF '));new=next(x for x in d.splitlines() if x.startswith('VREF '))
a=old.split('PWL(',1)[1].removesuffix(')').split();b=new.split('PWL(',1)[1].removesuffix(')').split();assert len(a)==len(b)
for i in range(0,len(a),2):assert Fraction(a[i][:-1])/10**12==Fraction(b[i]) and Fraction(a[i+1])==Fraction(b[i+1])
assert d.replace(new,old).replace('/work/seconds.dat','/work/pwl.dat')==original
for path,h in m['source_sha256_before'].items():
 if path.startswith('/screen/'):assert sha(P/'analog'/path.removeprefix('/screen/'))==h
out=dict(status='pending_exact_timestamp_representation_diagnostic',timestamps_verified=len(a)//2,exact_rational_waveform_equivalence=True,manifest=m)
if (W/'result.json').exists():
 r=json.loads((W/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before']
 for ext,h in r['artifacts_sha256'].items():assert sha(W/('seconds'+ext))==h
 log=(W/'seconds.log').read_text();failure=re.search(r'Timestep too small; time = ([0-9.e+-]+)',log);out.update(run_record=r,failure_time_ns=float(failure.group(1))*1e9 if failure else None,completed=False)
 if (W/'seconds.dat').exists():
  with (W/'seconds.dat').open() as f:assert f.readline().lower().split()==['time','v(refraw)','v(ref)','v(fb)','v(up)','v(dn)','v(ctrl)','i(vsense)']
  v=np.loadtxt(W/'seconds.dat',skiprows=1);assert v.shape[1]==8 and np.isfinite(v).all() and np.all(np.diff(v[:,0])>=0)
  out.update(actual_stop_ns=float(v[-1,0]*1e9),completed=bool(r['returncode']==0 and not r['timed_out'] and 'aborted' not in log.lower() and v[-1,0]>=800e-9),equal_printed_time_intervals=int(np.sum(np.diff(v[:,0])==0)),control_range_v=[float(v[:,6].min()),float(v[:,6].max())],max_raw_reference_feedback_difference_v=float(np.max(abs(v[:,1]-v[:,3]))))
 out['status']='terminal_exact_timestamp_representation_diagnostic'
out['limitations']=['Exact rational source values can still produce different floating-point breakpoint values in the simulator.', 'This is reduced forced feedback, not autonomous loop qualification.', 'Success or failure alone does not prove simulator defect, physical instability or common cause of all earlier aborts.']
(P/'evidence/pwl-seconds-screen.json').write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out.get('completed'))
