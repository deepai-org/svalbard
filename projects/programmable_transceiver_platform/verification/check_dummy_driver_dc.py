#!/usr/bin/env python3
"""Verify coverage and report tracking, without inventing a qualification limit."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-dummy-driver-dc'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((W/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after']
for path,h in r['source_sha256_before'].items():
 if path.startswith('/screen/'):assert sha(P/'analog'/path.removeprefix('/screen/'))==h
expected={(t,s,v) for t in ('scaled','complement') for s in (.0625,.25) for v in (.9,1.08,1.3)}
assert {(c['topology'],c['scale'],c['target_v']) for c in r['cases']}==expected and len(r['cases'])==12
rows=[]
for c in r['cases']:
 n=c['name'];assert c['returncode']==0
 for e,h in c['artifacts_sha256'].items():assert sha(W/(n+e))==h
 assert set(c['artifacts_sha256'])=={'.spice','.dat','.log'}
 assert 'aborted' not in (W/(n+'.log')).read_text().lower()
 with (W/(n+'.dat')).open() as f:header=f.readline().lower().split()
 a=np.loadtxt(W/(n+'.dat'),skiprows=1);assert a.shape==(61,len(header)) and np.isfinite(a).all()
 np.testing.assert_allclose(a[:,0],np.linspace(-150e-6,150e-6,61),atol=1e-15,rtol=0)
 v=a[:,header.index('v(out)')];supply=a[:,header.index('i(vdd)')];z=30
 # +/-15uA DC covers slightly more than observed reservoir driver peaks;
 # it is only a sizing screen, not proof for a pulsed load.
 small=abs(a[:,0])<=15.001e-6
 row=dict(name=n,zero_load_error_v=float(v[z]-c['target_v']),zero_load_supply_power_w=float(-3.3*supply[z]),full_sweep_output_range_v=[float(v.min()),float(v.max())],small_load_max_tracking_error_v=float(max(abs(v[small]-c['target_v']))),small_load_max_incremental_resistance_ohm=float(max(abs(np.diff(v[small])/np.diff(a[small,0])))))
 rows.append(row)
out=dict(completed=True,cases=rows,provenance=r,limitations=r['limitations'])
(P/'evidence/dummy-driver-dc.json').write_text(json.dumps(out,indent=2)+'\n')
for row in rows:print(row)
