#!/usr/bin/env python3
import hashlib,json,re
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-buffer-only-breakpoint';B=R/'scratch/transceiver-pfd-only-breakpoint'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((W/'manifest.json').read_text());src=B/'pfd.spice';assert sha(src)==m['baseline_deck_sha256'];assert sha(W/'buffer.spice')==m['deck_sha256_before']
expected=src.read_text().split('.control')[0]
remove=['XPFD REF FB RN UP DN VDIV 0 pt_pfd\n','CU UP 0 50f\n','CD DN 0 50f\n'];assert m['removed_lines']==remove
for line in remove:assert expected.count(line)==1;expected=expected.replace(line,'')
expected+='CBUF REF 0 50f\nCFB FB 0 50f\n';d=(W/'buffer.spice').read_text();assert d.split('.control')[0]==expected and 'tran 2p 800n 0 2p uic' in d
out=dict(status='pending_buffer_only_diagnostic',manifest=m,declared_reduction_verified=True)
if (W/'result.json').exists():
 r=json.loads((W/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before']
 for ext,h in r['artifacts_sha256'].items():assert sha(W/('buffer'+ext))==h
 log=(W/'buffer.log').read_text();failure=re.search(r'Timestep too small; time = ([0-9.e+-]+)',log);out.update(status='terminal_buffer_only_diagnostic',run_record=r,completed=False,failure_time_ns=float(failure.group(1))*1e9 if failure else None)
 if (W/'buffer.dat').exists():
  with (W/'buffer.dat').open() as f:assert f.readline().lower().split()==['time','v(refraw)','v(ref)','v(fb)','i(vdiv)']
  a=np.loadtxt(W/'buffer.dat',skiprows=1);assert a.shape[1]==5 and np.isfinite(a).all() and np.all(np.diff(a[:,0])>=0)
  out.update(completed=bool(r['returncode']==0 and not r['timed_out'] and 'aborted' not in log.lower() and a[-1,0]>=800e-9),actual_stop_ns=float(a[-1,0]*1e9),equal_printed_time_intervals=int(np.sum(np.diff(a[:,0])==0)))
out['limitations']=['State machine and its actual input loading removed; fixed50fF loads are diagnostic substitutes.', 'No active oscillator, PFD, pump or autonomous loop; no physical timing/noise qualification.', 'Any observed numerical failure does not establish identical cause for all earlier failures.']
(P/'evidence/buffer-only-breakpoint-screen.json').write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out.get('completed'),out.get('failure_time_ns'))
