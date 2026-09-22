#!/usr/bin/env python3
"""Compare late ordinal phase windows; no lock or noise threshold asserted."""
import argparse,hashlib,json
ap=argparse.ArgumentParser();ap.add_argument("--selective",action="store_true");args=ap.parse_args()
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';E=P/'evidence/latest-rf-loop.json'
if args.selective:E=P/'evidence/latest-rf-loop-selective.json'
root=R/('scratch/transceiver-latest-rf-loop-selective' if args.selective else 'scratch/transceiver-latest-rf-loop')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
d=json.loads(E.read_text());assert d['completed'] and d['actual_stop_ns']>=3201
for ext,h in d['provenance']['artifacts_sha256'].items():assert sha(root/('latest'+ext))==h
phase=d['phase'];t=np.array(phase['reference_times_ns']);y=np.array(phase['ordinal_feedback_minus_reference_ns']);assert len(t)==len(y) and np.all(np.diff(t)>0)
rows=[]
for n in [5,10,21]:
 rt=t[-n:];py=y[-n:];fb=rt+py
 rows.append(dict(paired_edges=n,window_ns=[float(rt[0]),float(rt[-1])],phase_start_ns=float(py[0]),phase_end_ns=float(py[-1]),phase_drift_ns=float(py[-1]-py[0]),reference_frequency_hz=float((n-1)*1e9/(rt[-1]-rt[0])),feedback_frequency_hz=float((n-1)*1e9/(fb[-1]-fb[0])),successive_phase_changes_ns=np.diff(py).tolist()))
out=dict(status='verified_completed_run_phase_tail',evidence_sha256=sha(E),windows=rows,limitations=['Window-dependent deterministic drift; no stationarity, lock or intrinsic jitter qualification.','Ordinal alignment retains startup-dependent offset.'])
(P/'evidence'/('latest-loop-selective-phase-tail.json' if args.selective else 'latest-loop-phase-tail.json')).write_text(json.dumps(out,indent=2)+'\n')
for x in rows:print(x['paired_edges'],x['phase_drift_ns'],x['feedback_frequency_hz'])
