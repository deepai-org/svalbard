#!/usr/bin/env python3
"""Check reduced-load completion before comparing reference trajectories."""
import argparse,hashlib,json,re
ap=argparse.ArgumentParser();ap.add_argument("--startup",action="store_true");args=ap.parse_args()
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-reference-load-replay';B=R/'scratch/transceiver-adc-reference-current'
if args.startup:W=R/'scratch/transceiver-reference-load-startup-full'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((W/'manifest.json').read_text());r=json.loads((W/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before']
for ext,h in r['artifacts_sha256'].items():assert sha(W/('load'+ext))==h
assert sha(W/'load.spice')==m['deck_sha256_before']==m['preparation']['deck_sha256']
for ext,digest in m['preparation']['baseline_artifacts_sha256'].items():assert sha(B/('frames'+ext))==digest
log=(W/'load.log').read_text();failure=re.search(r'Timestep too small; time = ([0-9.e+-]+)',log)
with (W/'load.dat').open() as f:h=f.readline().lower().split()
assert h==['time']+next(l for l in (W/'load.spice').read_text().splitlines() if l.startswith('wrdata ')).lower().split()[2:]
a=np.loadtxt(W/'load.dat',skiprows=1);assert np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
complete=r['returncode']==0 and not r['timed_out'] and a[-1,0]+1e-21>=209.9e-9 and 'aborted' not in log.lower()
out=dict(status='completed' if complete else 'incomplete_reduced_load_replay',completed=bool(complete),actual_stop_s=float(a[-1,0]),failure_time_s=float(failure[1]) if failure else None,provenance=r,startup_approximation=m['preparation'].get('startup_approximation_max_current_change_a'),limitations=['Frozen measured demand removes ADC voltage dependence.','No rail reproduction claim without requested horizon.'])
if complete:
 with (B/'frames.dat').open() as f:bh=f.readline().lower().split()
 ba=np.loadtxt(B/'frames.dat',skiprows=1);errors={}
 for node in ['v(vh)','v(vl)']:
  ref=np.interp(a[:,0],ba[:,0],ba[:,bh.index(node)]);errors[node]=float(abs(a[:,h.index(node)]-ref).max())
 out['rail_max_difference_v']=errors;out['diagnostic_reproduction_pass']=max(errors.values())<=m['diagnostic_rail_difference_limit_v']
(P/('evidence/reference-load-startup-full.json' if args.startup else 'evidence/reference-load-replay.json')).write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out['actual_stop_s'])
