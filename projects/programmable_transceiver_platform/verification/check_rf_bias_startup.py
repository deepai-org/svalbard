#!/usr/bin/env python3
"""Validate cold-bias observations without treating sensitivity as yield bounds."""
import hashlib,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3];W=ROOT/'scratch/transceiver-rf-bias-startup';r=json.loads((W/'result.json').read_text())
for c in r['cases']:
 name=f"rc{c['resistance_scale']:g}"
 for s,h in c['artifacts_sha256'].items():assert hashlib.sha256((W/(name+s)).read_bytes()).hexdigest()==h
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert abs(a[0,1])<.001
 good=abs(a[:,1]-1.5)<=.015;bad=np.flatnonzero(~good);j=bad[-1]+1
 assert j<len(a) and good[j:].all() and a[j,0]==c['gate_1percent_settling_s']
 assert c['gate_1percent_settling_s']>40e-6
assert all(x['gate_1percent_settling_s']<y['gate_1percent_settling_s'] for x,y in zip(r['cases'],r['cases'][1:]))
r['checker_pass']=True
(ROOT/'projects/programmable_transceiver_platform/evidence/rf-bias-startup-screen.json').write_text(json.dumps(r,indent=2)+'\n')
print('Cold-bias data and persistent 1% settling verified for three scenarios.')
