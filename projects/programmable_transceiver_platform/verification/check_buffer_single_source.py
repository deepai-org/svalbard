#!/usr/bin/env python3
import hashlib,json,re,sys
FINITE="--finite-source" in sys.argv
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/('scratch/transceiver-buffer-finite-source' if FINITE else 'scratch/transceiver-buffer-single-source');B=R/'scratch/transceiver-buffer-only-breakpoint'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((W/'manifest.json').read_text());src=B/'buffer.spice';assert sha(src)==m['baseline_deck_sha256'];assert sha(W/'buffer.spice')==m['deck_sha256_before']
expected=src.read_text().split('.control')[0]
if FINITE:
 original_line=next(line for line in expected.splitlines(True) if line.startswith('VREF REFRAW 0 '))
 assert m['removed_lines']==[original_line]
 expected=expected.replace(original_line,original_line.replace('VREF REFRAW 0 ','VREF REFDRIVE 0 ')+'RREF REFDRIVE REFRAW 50\n')
else:
 remove=['VFB FB 0 PULSE(0 3.3 100n 100p 100p 25.5n 51.2n)\n'];assert m['removed_lines']==remove
 assert expected.count(remove[0])==1
 expected=expected.replace(remove[0],'VFB FB 0 0\n')
d=(W/'buffer.spice').read_text();assert d.split('.control')[0]==expected
assert d.split('.control')[1]==src.read_text().split('.control')[1]
out=dict(status='pending_buffer_single_source_diagnostic',manifest=m,declared_reduction_verified=True)
if (W/'buffer.log').exists():
 progress=re.findall(r'Reference value\s*:\s*([0-9.eE+-]+)',(W/'buffer.log').read_text())
 if progress:
  last=progress[-1];repeats=0
  for value in reversed(progress):
   if value!=last:break
   repeats+=1
  out['log_progress_diagnostic']=dict(last_printed_time_ns=float(last)*1e9,consecutive_identical_prints=repeats,interpretation='Rounded log progress only; not waveform completion, proof of a stuck solver, or live-process evidence.')
if (W/'result.json').exists():
 r=json.loads((W/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before']
 for ext,h in r['artifacts_sha256'].items():assert sha(W/('buffer'+ext))==h
 log=(W/'buffer.log').read_text();failure=re.search(r'Timestep too small; time = ([0-9.e+-]+)',log);out.update(status='terminal_buffer_single_source_diagnostic',run_record=r,completed=False,failure_time_ns=float(failure.group(1))*1e9 if failure else None)
 if (W/'buffer.dat').exists():
  with (W/'buffer.dat').open() as f:assert f.readline().lower().split()==['time','v(refraw)','v(ref)','v(fb)','i(vdiv)']
  a=np.loadtxt(W/'buffer.dat',skiprows=1);assert a.shape[1]==5 and np.isfinite(a).all() and np.all(np.diff(a[:,0])>=0)
  out.update(completed=bool(r['returncode']==0 and not r['timed_out'] and 'aborted' not in log.lower() and a[-1,0]+1e-21>=800e-9),actual_stop_ns=float(a[-1,0]*1e9),equal_printed_time_intervals=int(np.sum(np.diff(a[:,0])==0)))
out['limitations']=['Feedback source is electrically separate except ideal ground; changing its events is a numerical diagnostic, not a circuit repair.', 'No active oscillator, PFD, pump or autonomous loop; no physical timing/noise qualification.', 'Any observed numerical failure does not establish identical cause for all earlier failures.']
if FINITE:
 out['status']=out['status'].replace('single_source','finite_source')
 out['limitations'][0]='Reference source resistance50ohm is a diagnostic scenario; both original timed sources remain. No source impedance bound or physical clock implementation established.'
(P/('evidence/buffer-finite-source-screen.json' if FINITE else 'evidence/buffer-single-source-screen.json')).write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out.get('completed'),out.get('failure_time_ns'))
