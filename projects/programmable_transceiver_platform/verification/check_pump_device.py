#!/usr/bin/env python3
"""Preserve signed MOS probes; channel current is not full terminal current."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-pump-device';B=R/'scratch/transceiver-pump-clamped'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((W/'manifest.json').read_text());out=dict(completed=False,status='running_or_unrecorded',limitations=['Signed simulator MOS quantities retained without assuming a reverse-operation headroom convention.','Model id is not a complete displacement-inclusive terminal-current attribution.','One nominal clamped-output case; no autonomous-loop qualification.'])
if (W/'result.json').exists():
 r=json.loads((W/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before']
 for ext,h in r['artifacts_sha256'].items():assert sha(W/('early'+ext))==h
 assert sha(B/'early.spice')==m['baseline_deck_sha256']
 d=(W/'early.spice').read_text();extra=' '+' '.join(m['probes']);assert d.count(extra)==2
 assert d.replace(extra,'')==(B/'early.spice').read_text()
 a=np.loadtxt(W/'early.dat',skiprows=1);b=np.loadtxt(B/'early.dat',skiprows=1)
 with (W/'early.dat').open() as f:h=f.readline().lower().split()
 with (B/'early.dat').open() as f:oldh=f.readline().lower().split()
 assert h==oldh+[p.lower() for p in m['probes']] and a.shape[1]==33 and np.isfinite(a).all()
 assert np.array_equal(a[:,:13],b)
 completed=r['returncode']==0 and not r['timed_out'] and a[-1,0]+1e-21>=800e-9 and 'aborted' not in (W/'early.log').read_text().lower()
 out.update(status='terminal',completed=completed,provenance=r,original_vectors_identical=True)
 if completed:
  w=a[(a[:,0]>=200e-9)&(a[:,0]<=790e-9)]
  out['probe_ranges']={n:dict(minimum=float(w[:,h.index(n)].min()),maximum=float(w[:,h.index(n)].max())) for n in m['probes']}
(P/'evidence/pump-device.json').write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out['completed'])
