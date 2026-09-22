#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3];W=ROOT/'scratch/transceiver-closed-loop';r=json.loads((W/'result.json').read_text())
for s,h in r['artifacts_sha256'].items():assert hashlib.sha256((W/('closed'+s)).read_bytes()).hexdigest()==h
d=(W/'closed.spice').read_text();assert 'VC CTRL 0' not in d and 'VSENSE PUMP CTRL 0' in d and 'XFILT CTRL 0 pt_loop_filter' in d
for stage in range(1,8):assert f'XD{stage} ' in d
assert 'XPFD REF FB RN UP DN' in d and 'XCP UP DN PUMP' in d
r['actual_feedback_connectivity_checked']=True
r['local_tuning_interval_exceeded']=any(w['control_range_v'][0]<1.06 or w['control_range_v'][1]>1.10 for w in r['windows'])
r['bias_guard_pass']=all(w['gate_range_v'][0]>1.4 and w['gate_range_v'][1]<1.6 for w in r['windows'])
a=np.loadtxt(W/'closed.dat',skiprows=1);w=a[a[:,0]>=100e-9]
r['pump_filter_control_range_v']=[float(w[:,14].min()),float(w[:,14].max())]
r['pll_lock_established']=False
(ROOT/'projects/programmable_transceiver_platform/evidence/closed-loop-screen.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
assert r['bias_guard_pass'],'Invalid LNA bias; do not interpret RF performance'
