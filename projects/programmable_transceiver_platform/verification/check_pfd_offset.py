#!/usr/bin/env python3
"""Independent signed-offset deck and waveform audit; preserve partial coverage."""
import hashlib,json,re
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-pfd-offset';B=R/'scratch/transceiver-pfd-buffered-reference/pwl.spice'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((W/'manifest.json').read_text());assert sha(B)==m['source_sha256_before']['/baseline/pwl.spice']
for path,digest in m['source_sha256_before'].items():
 if path.startswith('/screen/'):assert sha(P/'analog'/path.removeprefix('/screen/'))==digest
complete=(W/'result.json').exists();record=W/('result.json' if complete else 'progress.json')
raw=json.loads(record.read_text()) if record.exists() else {'cases':[]};rows=[]
for c in raw['cases']:
 name=c['name']; offset=c['offset_ps']; assert offset in [-10,10]
 for ext,digest in c['artifacts_sha256'].items():assert sha(W/(name+ext))==digest
 deck=(W/(name+'.spice')).read_text()
 old='VFB FB 0 PULSE(0 3.3 100n 100p 100p 25.5n 51.2n)'
 new=f'VFB FB 0 PULSE(0 3.3 {100000+offset}p 100p 100p 25.5n 51.2n)'
 assert deck.count(new)==1 and deck.replace(new,old).replace(f'/work/{name}.dat','/work/pwl.dat')==B.read_text()
 log=(W/(name+'.log')).read_text();failure=re.search(r'Timestep too small; time = ([0-9.e+-]+)',log)
 row=dict(name=name,offset_ps=offset,returncode=c['returncode'],timed_out=c['timed_out'],completed=False,failure_time_ns=float(failure.group(1))*1e9 if failure else None)
 wave=W/(name+'.dat')
 if wave.exists():
  with wave.open() as f:assert f.readline().lower().split()==['time','v(refraw)','v(ref)','v(fb)','v(up)','v(dn)','v(ctrl)','i(vsense)']
  a=np.loadtxt(wave,skiprows=1);assert a.shape[1]==8 and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
  row.update(actual_stop_ns=float(a[-1,0]*1e9),completed=bool(c['returncode']==0 and not c['timed_out'] and 'aborted' not in log.lower() and a[-1,0]>=800e-9),control_range_v=[float(a[:,6].min()),float(a[:,6].max())])
 rows.append(row)
if complete:
 assert raw['source_sha256_before']==raw['source_sha256_after']==m['source_sha256_before']
 assert {c['offset_ps'] for c in rows}=={-10,10}
result=dict(status='complete_offset_diagnostic' if complete else 'partial_offset_diagnostic',cases=rows,manifest=m,limitations=['Signed offsets alter physical phase as well as source breakpoint coincidence.', 'Forced clocks: no autonomous lock, noise, startup or silicon qualification.', 'Completion does not establish a solver defect or a sufficient remedy for the full loop.'])
(P/'evidence/pfd-offset-screen.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result['cases'],indent=2))
