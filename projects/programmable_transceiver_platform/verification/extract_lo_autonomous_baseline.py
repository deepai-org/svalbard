"""Hash-verified matched late-window baseline for autonomous LO intervention."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-latest-rf-loop-selective';E=P/'evidence/latest-rf-loop-selective.json';e=json.loads(E.read_text());assert e['completed']
names=['time','v(p)','v(n)','v(oip)','v(oin)','v(oqp)','v(oqn)','v(fip)','v(fin)','v(fqp)','v(fqn)','v(ctrl)','v(fb)','v(ref)','i(vbuf)','i(vpll)']
digest=hashlib.sha256();rows=[];before=None;after=None;previous=-float('inf')
with (W/'latest.dat').open('rb') as f:
 line=f.readline();digest.update(line);h=line.decode().lower().split();cols=[h.index(n) for n in names]
 for line in f:
  digest.update(line);fields=line.split();assert len(fields)==len(h);t=float(fields[0]);assert np.isfinite(t) and t>previous;previous=t
  if t<7424e-9:before=[float(fields[k]) for k in cols]
  elif t<=7936e-9:rows.append([float(fields[k]) for k in cols])
  elif after is None:after=[float(fields[k]) for k in cols]
assert digest.hexdigest()==e['provenance']['artifacts_sha256']['.dat'] and previous>=8001e-9-1e-20
assert before is not None and after is not None and rows
a=np.array([before]+rows+[after]);assert np.isfinite(a).all();out=W/'interstage-baseline-window.npz';np.savez(out,samples=a,names=np.array(names))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
report=dict(completed=True,source_evidence_sha256=sha(E),waveform_sha256=digest.hexdigest(),extraction_sha256=sha(out),window_ns=[7424,7936],rows=len(a),limitations=['Finite checks apply to extracted vectors; other waveform values are not validated here.','Original prescribed-state zero-RF receiver only; extraction is not performance qualification.'])
(P/'evidence/lo-autonomous-baseline-window.json').write_text(json.dumps(report,indent=2)+'\n');print('Extracted',len(a),'rows')
