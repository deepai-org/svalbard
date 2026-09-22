#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-restorer-bias-dc'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((W/'manifest.json').read_text());r=json.loads((W/'result.json').read_text());assert m['source_sha256_before']==r['source_sha256_before']==r['source_sha256_after'];assert sha(W/'bias.spice')==m['deck_sha256_before'];assert r['returncode']==0
for ext,h in r['artifacts_sha256'].items():assert sha(W/('bias'+ext))==h
d=(W/'bias.spice').read_text().splitlines()
expected=['VDD VDD 0 3.3','VSRC SRC 0 1.7','CC SRC IN 200f','RFB IN XBUF.MID 100k','XBUF IN OUT VDD 0 pt_lo_buffer S=1','CLOAD OUT 0 50f','IERR 0 IN 0']
assert [l for l in d if l and l[0] in 'VRCXI']==expected
assert 'dc IERR -3u 3u 0.1u' in d
with (W/'bias.dat').open() as f:h=f.readline().lower().split()
assert h[1:]==['v(in)','v(xbuf.mid)','v(out)','i(vdd)']
a=np.loadtxt(W/'bias.dat',skiprows=1);assert a.shape==(61,5) and np.isfinite(a).all() and np.allclose(a[:,0],np.linspace(-3e-6,3e-6,61),rtol=0,atol=1e-18)
assert 'aborted' not in (W/'bias.log').read_text().lower()
# DC capacitor draws no current: verify sign and feedback balance including leakage.
residual=a[:,0]-(a[:,1]-a[:,2])/100e3
assert abs(residual).max()<1e-9
out=dict(status='completed_static_self_bias_diagnostic',zero_injection_input_v=float(a[30,1]),input_range_v=[float(a[:,1].min()),float(a[:,1].max())],input_shift_from_zero_v=[float(a[0,1]-a[30,1]),float(a[-1,1]-a[30,1])],first_stage_output_range_v=[float(a[:,2].min()),float(a[:,2].max())],max_feedback_kcl_residual_a=float(abs(residual).max()),supply_current_range_a=[float((-a[:,4]).min()),float((-a[:,4]).max())],provenance=r,limitations=['DC equilibria only, not dynamic bias stability/startup or RF gain.', 'Injected current scenarios are not validated leakage/mismatch bounds.', 'Capacitor isolates static source common mode; no source RF swing or charge pumping modeled.', 'Fixed typical geometry/supply; no threshold/mismatch/process tracking claim.'])
(P/'evidence/restorer-bias-dc.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='provenance'},indent=2))
