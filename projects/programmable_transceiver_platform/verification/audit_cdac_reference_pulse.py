#!/usr/bin/env python3
"""Locate current pulses relative to saved physical MSB gates and logical commands."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-adc-reference-current'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
scope=P/'evidence/adc-reference-reproduction-scope.json';s=json.loads(scope.read_text());assert s['scoped_current_diagnostic_valid']
e=P/'evidence/adc-reference-current-replay.json';assert sha(e)==s['replay_evidence_sha256'];r=json.loads(e.read_text())
for ext,h in r['provenance']['artifacts_sha256'].items():assert sha(W/('frames'+ext))==h
with (W/'frames.dat').open() as f:h=f.readline().lower().split()
a=np.loadtxt(W/'frames.dat',skiprows=1);t=a[:,0];assert np.isfinite(a).all() and np.all(np.diff(t)>0)
def v(n):return a[:,h.index(n)]
demand=v('i(vrefh_del)')-v('i(vrefh_res)');rows=[]
for lo,hi in [(60,109.9),(110,159.9),(160,209.9),(122.5,125.35)]:
 ix=np.flatnonzero((t>=lo*1e-9)&(t<=hi*1e-9));k=ix[int(np.argmax(demand[ix]))]
 physical={n:float(v(n)[k]) for n in ['v(b7)','v(b7b)','v(xd.xp7.bot)','v(xd.xn7.bot)','v(vh)','v(vl)']}
 commands={f'sd{i}':float(v(f'v(sd{i})')[k]) for i in range(8)}
 rows.append(dict(window_ns=[lo,hi],peak_time_ns=float(t[k]*1e9),high_adc_demand_a=float(demand[k]),saved_physical_nodes_v=physical,upstream_track_mask_commands_v=commands))
paths=['analog/adc/code_driver_small.spice','analog/adc/cdac8_scaled.spice','analog/adc/cdac8_mim.spice']
out=dict(status='scoped_reference_pulse_topology_audit',cases=rows,scope_evidence_sha256=sha(scope),source_sha256={p:sha(P/p) for p in paths},limitations=['B7/BB7 are the only saved physical bit-control pair; SD0..7 are upstream mask commands, not switch gates.','Rail-level MSB gates at a peak do not exonerate other bits or prior overlap.','No branch-current or transistor-conduction attribution from these voltage observations alone.'])
(P/'evidence/cdac-reference-pulse-audit.json').write_text(json.dumps(out,indent=2)+'\n')
for r in rows:print(r['peak_time_ns'],r['high_adc_demand_a'],r['saved_physical_nodes_v']['v(b7)'],r['saved_physical_nodes_v']['v(b7b)'])
