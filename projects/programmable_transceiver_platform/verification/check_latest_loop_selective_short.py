#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-latest-rf-loop-selective-short';B=R/'scratch/transceiver-latest-rf-loop'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
arrays=[]
for root in (W,B):
 r=json.loads((root/'result.json').read_text());assert r['returncode']==0 and not r['timed_out'] and r['source_sha256_before']==r['source_sha256_after']
 for ext,h in r['artifacts_sha256'].items():assert sha(root/('latest'+ext))==h
 with (root/'latest.dat').open() as f:header=f.readline().lower().split()
 a=np.loadtxt(root/'latest.dat',skiprows=1,max_rows=6000);assert a.shape[1]==len(header) and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
 arrays.append((header,a))
(h,a),(bh,b)=arrays;assert h==bh and a[-1,0]+1e-21>=10e-9 and 'aborted' not in (W/'latest.log').read_text().lower()
# Exclude forced stop endpoint when comparing common native timesteps.
ix=np.searchsorted(b[:,0],a[:-1,0]);same=np.array_equal(a[:-1,0],b[ix,0])
err={n:float(abs(a[:-1,i]-np.interp(a[:-1,0],b[:,0],b[:,i])).max()) for i,n in enumerate(h[1:],1)}
out=dict(completed=True,comparison_rows=len(ix),same_time_grid=same,all_common_samples_identical=bool(same and np.array_equal(a[:-1],b[ix])),max_errors=err,artifacts_sha256=json.loads((W/'result.json').read_text())['artifacts_sha256'],limitations=['10ns reproduction only; no guarantee of long-run memory limit or autonomous quality.','Time-grid identity failed; diagnostic comparison interpolates baseline without shifting time; no reproduction pass declared.'])
(P/'evidence/latest-loop-selective-short.json').write_text(json.dumps(out,indent=2)+'\n');print(out['all_common_samples_identical'],max(err.values()))
