#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3];W=ROOT/'scratch/transceiver-divider-chain';r=json.loads((W/'result.json').read_text())
for s,h in r['artifacts_sha256'].items():assert hashlib.sha256((W/('chain'+s)).read_bytes()).hexdigest()==h
f=r['nodes'][0]['frequency_hz'];checks={}
a=np.loadtxt(W/'chain.dat',skiprows=1);w=a[(a[:,0]>=100e-9)&(a[:,0]<=320e-9)]
for col,node in enumerate(r['nodes'][1:],2):
 divisor=128 if col==9 else 2**(col-1);level=1.65 if col==9 else 0;v=w[:,col];t=w[:,0];ix=np.where((v[:-1]<level)&(v[1:]>=level))[0];e=t[ix]+(t[ix+1]-t[ix])*(level-v[ix])/(v[ix+1]-v[ix]);periods=np.diff(e)
 checks[node['node']]=bool(len(periods)>=2 and np.all(abs(periods-divisor/f)<.02*divisor/f))
checks['gate_bias']=r['gate_range_v'][0]>1.4 and r['gate_range_v'][1]<1.6
checks['feedback_swing']=r['nodes'][-1]['min_v']<.5 and r['nodes'][-1]['max_v']>2.8
r['boundary_checks']=checks;r['all_checks_pass']=all(checks.values())
r['source_sha256']={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['ip/blocks/analog/wireline_serdes/pll/divider.spice','projects/programmable_transceiver_platform/analog/lo_buffer.spice','projects/programmable_transceiver_platform/analog/pll/pfd.spice','projects/programmable_transceiver_platform/analog/rf_rx_candidate.spice']}
(ROOT/'projects/programmable_transceiver_platform/evidence/divider-chain-screen.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
assert r['all_checks_pass'],'Stage cadence, bias or output swing fails; evidence retained.'
