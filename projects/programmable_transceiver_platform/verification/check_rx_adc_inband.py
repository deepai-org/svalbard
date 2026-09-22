"""Check declared frequency-only change and complete connected waveform."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-rx-adc-inband/inband';B=R/'scratch/transceiver-rx-adc-separated-events-v2/separated';V=R/'scratch/transceiver-rx-adc-inband-prepared'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((V/'manifest.json').read_text());c=m['cases'][0];assert sha(B/'connected.spice')==m['parent_deck_sha256'] and sha(V/'inband.spice')==c['deck_sha256']
s=(W/'connected.spice').read_text();assert s.replace('/work/inband/connected.dat','/work/separated/connected.dat').replace(c['changed_line'],c['original_line'])==(B/'connected.spice').read_text()
row=dict(case='inband',status='pending',completed=False)
if (W/'result.json').exists():
 r=json.loads((W/'result.json').read_text());assert r['sources_before']==r['sources_after']
 for ext,h in r['artifacts_sha256'].items():assert sha(W/('connected'+ext))==h
 errors=[x.strip() for x in (W/'connected.log').read_text().splitlines() if any(k in x.lower() for k in ('error','warning','aborted','timestep too small'))]
 row.update(status='terminal',returncode=r['returncode'],timed_out=r['timed_out'],errors=errors,artifacts_sha256=r['artifacts_sha256'])
 if (W/'connected.dat').exists():
  with (W/'connected.dat').open() as stream:h=stream.readline().lower().split()
  expected=next(x for x in s.splitlines() if x.startswith('wrdata ')).lower().split()[2:];assert h==['time']+expected
  a=np.loadtxt(W/'connected.dat',skiprows=1);assert a.shape[1]==len(h) and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
  row.update(actual_stop_ns=float(a[-1,0]*1e9),rows=len(a),completed=bool(r['returncode']==0 and not r['timed_out'] and not errors and a[-1,0]+1e-21>=610e-9))
out=dict(completed=row['completed'],cases=[row],preparation_sha256=sha(V/'manifest.json'),limitations=m['limitations'])
(P/'evidence/rx-adc-inband.json').write_text(json.dumps(out,indent=2)+'\n');print(row['status'],row['completed'])
