"""Terminal provenance gate and bounded-memory late-window extraction."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';B=R/'scratch/transceiver-lo-interstage-autonomous-prepared';W=R/'scratch/transceiver-lo-interstage-autonomous';D=R/'scratch/transceiver-latest-rf-loop-selective'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
m=json.loads((B/'manifest.json').read_text());assert sha(B/'latest.spice')==m['artifacts_sha256']['latest.spice'];assert sha(D/'latest.spice')==m['parent_deck_sha256']
cell=(P/'analog/lo_buffer.spice').read_text();changed=cell.replace('XP2 OUT MID','XCISO MID LOCAL pt_ref_reservoir_4\nRLOCAL LOCAL OUT 10k\nXP2 OUT LOCAL').replace('XN2 OUT MID','XN2 OUT LOCAL').rstrip()
assert (B/'latest.spice').read_text().replace(changed,'.include /screen/lo_buffer.spice')==(D/'latest.spice').read_text()
names=['time','v(p)','v(n)','v(oip)','v(oin)','v(oqp)','v(oqn)','v(fip)','v(fin)','v(fqp)','v(fqn)','v(ctrl)','v(fb)','v(ref)','i(vbuf)','i(vpll)']
out=dict(completed=False,status='pending',adopted=False,preparation_sha256=sha(B/'manifest.json'),window_ns=[7424,7936],limitations=m['limitations']+['This gate verifies artifacts and extracts late vectors; it does not qualify lock or RF performance.'])
if (W/'result.json').exists():
 r=json.loads((W/'result.json').read_text());assert r['sources_before']==r['sources_after']
 assert sha(W/'latest.spice')==sha(B/'latest.spice')
 for ext,d in r['artifacts_sha256'].items():assert sha(W/('latest'+ext))==d
 errors=[l for l in (W/'latest.log').read_text().splitlines() if any(k in l.lower() for k in ('warning','error','aborted','timestep too small'))]
 out.update(status='terminal',returncode=r['returncode'],timed_out=r['timed_out'],errors=errors,result_sha256=sha(W/'result.json'))
 if r['returncode']==0 and not r['timed_out'] and not errors:
  assert {'.spice','.dat','.log'}<=set(r['artifacts_sha256'])
  rows=[];previous=-float('inf');count=0;before=None;after=None
  with (W/'latest.dat').open() as f:
   h=f.readline().lower().split();cols=[h.index(n) for n in names]
   for line in f:
    fields=line.split();assert len(fields)==len(h);tt=float(fields[0]);assert np.isfinite(tt) and tt>previous;previous=tt;count+=1
    if tt<7424e-9:before=[float(fields[k]) for k in cols]
    elif tt<=7936e-9:rows.append([float(fields[k]) for k in cols])
    elif after is None:after=[float(fields[k]) for k in cols]
  assert previous>=8001e-9-1e-20 and before is not None and after is not None and rows
  a=np.array([before]+rows+[after]);assert np.isfinite(a).all()
  np.savez(W/'late-window.npz',samples=a,names=np.array(names))
  out.update(completed=True,status='terminal_artifacts_verified_metrics_pending',waveform_sha256=r['artifacts_sha256']['.dat'],rows=count,stop_ns=previous*1e9,extracted_rows=len(a),extraction_sha256=sha(W/'late-window.npz'))
(P/'evidence/lo-interstage-autonomous.json').write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out['completed'])
