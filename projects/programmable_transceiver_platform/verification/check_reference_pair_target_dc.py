#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-reference-pair-target-dc-v2'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((W/'result.json').read_text());assert r['sources_before']==r['sources_after'];rows=[]
assert {c['name'] for c in r['cases']}=={'VH','VL'}
for c in r['cases']:
 n=c['name'];assert c['returncode']==0
 for ext,h in c['artifacts_sha256'].items():assert sha(W/(n+ext))==h
 log=(W/(n+'.log')).read_text().lower();assert not any(x in log for x in ['error','warning','aborted'])
 with (W/(n+'.dat')).open() as f:h=f.readline().lower().split()
 a=np.loadtxt(W/(n+'.dat'),skiprows=1);assert a.shape==(41,8) and np.isfinite(a).all() and h[1:]==['v(high)','v(low)','v(oh)','v(ol)','v(bn)','v(bp)','i(vdd)']
 assert np.allclose(a[:,0],np.linspace(c['target_v']-.02,c['target_v']+.02,41),atol=1e-12,rtol=0)
 x=a[:,0];y=a[:,h.index('v(oh)' if n=='VH' else 'v(ol)')];slope,intercept=np.polyfit(x,y,1)
 rows.append(dict(rail=n,nominal_output_v=float(y[20]),nominal_error_v=float(y[20]-c['target_v']),local_target_slope=float(slope),max_fit_residual_v=float(abs(y-(slope*x+intercept)).max()),supply_power_w=float(-3.3*a[20,h.index('i(vdd)')])) )
out=dict(completed=True,cases=rows,provenance=r,limitations=['Zero external DC load and ideal bias/target supplies; dynamic reference error not addressed.','Near-unity target response does not measure open-loop gain or isolate transistor mismatch.','No target precompensation adopted; process variation and switched load remain unqualified.'])
(P/'evidence/reference-pair-target-dc.json').write_text(json.dumps(out,indent=2)+'\n');print(rows)
