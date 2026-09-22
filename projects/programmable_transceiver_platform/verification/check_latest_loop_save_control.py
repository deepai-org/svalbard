#!/usr/bin/env python3
"""Exact matched-horizon save-mode comparison."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';S=R/'scratch/transceiver-latest-rf-loop-selective-short';B=R/'scratch/transceiver-latest-rf-loop-selective-short-all-control'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
arrays=[];decks=[];records=[]
for root in (S,B):
 r=json.loads((root/'result.json').read_text());assert r['returncode']==0 and not r['timed_out'] and r['source_sha256_before']==r['source_sha256_after']
 for ext,h in r['artifacts_sha256'].items():assert sha(root/('latest'+ext))==h
 d=(root/'latest.spice').read_text();assert 'tran 2p 10n 0 2p uic' in d
 log=(root/'latest.log').read_text().lower();assert not any(x in log for x in ['error','aborted','warning'])
 with (root/'latest.dat').open() as f:h=f.readline().lower().split()
 a=np.loadtxt(root/'latest.dat',skiprows=1);assert a.shape[1]==len(h) and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0) and a[-1,0]+1e-21>=10e-9
 arrays.append((h,a));decks.append(d);records.append(r['artifacts_sha256'])
save=[next(l for l in d.splitlines() if l.startswith('save ')) for d in decks];assert 'all' not in save[0].split() and 'all' in save[1].split();assert decks[0].replace(save[0],save[1])==decks[1]
(h,a),(bh,b)=arrays;assert h==bh
out=dict(completed=True,only_save_directive_changed=True,same_time_grid=bool(np.array_equal(a[:,0],b[:,0])),all_exported_samples_identical=bool(np.array_equal(a,b)),rows=[len(a),len(b)],artifact_sets=records,limitations=['10ns only; not long-run convergence, memory bound, lock or noise qualification.'])
(P/'evidence/latest-loop-save-control.json').write_text(json.dumps(out,indent=2)+'\n');print(out['same_time_grid'],out['all_exported_samples_identical'])
