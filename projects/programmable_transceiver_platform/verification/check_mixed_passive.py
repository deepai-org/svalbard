#!/usr/bin/env python3
"""Check whether two simultaneous clock representations fail with passive loads."""
import hashlib,json,re
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-mixed-passive';B=R/'scratch/transceiver-pfd-pump-breakpoint'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((W/'manifest.json').read_text());r=json.loads((W/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before'];rows=[]
for c in r['cases']:
 name=c['name'];source=B/f'{name}_skew0.spice';assert sha(source)==m['source_sha256_before'][f'/baseline/{name}_skew0.spice']
 for ext,h in c['artifacts_sha256'].items():assert sha(W/(name+ext))==h
 assert sha(W/(name+'.spice'))==c['deck_sha256_before']
 d=(W/(name+'.spice')).read_text();original=source.read_text().splitlines()
 for prefix in ('VREF ','VFB '):assert next(x for x in d.splitlines() if x.startswith(prefix))==next(x for x in original if x.startswith(prefix))
 circuit=d.split('.control')[0].splitlines();assert [x for x in circuit if x and not x.startswith(('*','.','VREF ','VFB '))]==['RR REF RO 100','CR RO 0 1p','RF FB FO 100','CF FO 0 1p']
 assert '.options method=gear maxord=2' in d and 'tran 2p 800n 0 2p uic' in d
 with (W/(name+'.dat')).open() as f:assert f.readline().lower().split()==['time','v(ref)','v(fb)','v(ro)','v(fo)']
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert a.shape[1]==5 and np.isfinite(a).all() and np.all(np.diff(a[:,0])>=0)
 log=(W/(name+'.log')).read_text();failure=re.search(r'Timestep too small; time = ([0-9.e+-]+)',log)
 rows.append(dict(equal_printed_time_intervals=int(np.sum(np.diff(a[:,0])==0)),minimum_positive_printed_step_s=float(np.min(np.diff(a[:,0])[np.diff(a[:,0])>0])),name=name,returncode=c['returncode'],completed=bool(c['returncode']==0 and 'aborted' not in log.lower() and a[-1,0]>=800e-9),actual_stop_ns=float(a[-1,0]*1e9),failure_ns=float(failure.group(1))*1e9 if failure else None,max_input_difference_v=float(np.max(abs(a[:,1]-a[:,2]))),max_output_difference_v=float(np.max(abs(a[:,3]-a[:,4])))))
assert {c['name'] for c in rows}=={'pulse','pwl'}
out=dict(status='combined_passive_clock_diagnostic',cases=rows,provenance=r,limitations=['No active device, feedback, bias or RF loading; any result applies only to this numerical fixture.', 'A reproduced passive failure would not prove every full-loop abort has the same cause.', 'No physical timing or jitter qualification.'])
(P/'evidence/mixed-passive-clock-screen.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(rows,indent=2))
