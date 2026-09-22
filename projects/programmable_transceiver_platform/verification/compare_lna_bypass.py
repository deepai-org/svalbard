#!/usr/bin/env python3
"""Check the bypass is the sole change and preserve DC versus RF distinction."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
paths=[P/'evidence'/n for n in ('lna-noise.json','lna-bypass.json')]
b,c=[json.loads(p.read_text()) for p in paths];assert b['completed'] and c['completed']
assert b['provenance']['source_sha256_before']==c['provenance']['source_sha256_before']
B=R/'scratch/transceiver-lna-noise';C=R/'scratch/transceiver-lna-bypass';rows=[]
for old,new,ob,oc in zip(b['cases'],c['cases'],b['provenance']['cases'],c['provenance']['cases']):
 n=old['name'];assert new['name']==ob['name']==oc['name']==n
 for work,case in ((B,ob),(C,oc)):
  for ext,h in case['artifacts_sha256'].items():assert sha(work/(n+ext))==h
 d=(C/(n+'.spice')).read_text();assert d.count('CSB LS 0 20p\n')==1
 assert d.replace('CSB LS 0 20p\n','')==(B/(n+'.spice')).read_text()
 assert np.array_equal(np.loadtxt(B/(n+'-op.dat'),skiprows=1),np.loadtxt(C/(n+'-op.dat'),skiprows=1))
 rows.append(dict(name=n,gain_ratio=new['source_gain_2p5g']/old['source_gain_2p5g'],noise_factor_change_db=new['stationary_noise_factor_db_2p5g']-old['stationary_noise_factor_db_2p5g'],input_noise_asd_ratio=new['input_asd_v_per_sqrt_hz_2p5g']/old['input_asd_v_per_sqrt_hz_2p5g']))
out=dict(completed=True,evidence_sha256={p.name:sha(p) for p in paths},declared_change='Ideal20pF bypass across82ohm source resistor',dc_reproduces_exactly=True,cases=rows,disposition='Candidate for physical capacitor substitution and actual mixer integration; retained connected baseline unchanged.',limitations=['No capacitor ESR/ESL or layout parasitics; no RF stability, compression or startup qualification.','Stationary source-referred noise factors under artificial loads are not complete receiver noise figures.'])
(P/'evidence/lna-bypass-comparison.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
