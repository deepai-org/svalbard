#!/usr/bin/env python3
"""Verify connected decoder truth and measured segmented DAC DC transfer."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-dac-segmented-dc';B=R/'scratch/transceiver-dac-loaded-dc'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((W/'result.json').read_text());m=json.loads((W/'manifest.json').read_text());assert r['returncode']==0 and r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before']
for ext,digest in r['artifacts_sha256'].items():assert sha(W/('segmented'+ext))==digest
assert sha(W/'segmented.spice')==m['deck_sha256_before']
for path,h in m['source_sha256_before'].items():
 if path.startswith('/screen/'):assert sha(P/'analog'/path.removeprefix('/screen/'))==h
with (W/'segmented.dat').open() as f:assert f.readline().lower().split()==['v-sweep','v(op)','v(on)','v(bn)','i(vdrv)']+[f'v(d{i})' for i in range(8)]+[f'v(xd.t{k})' for k in range(1,16)]
a=np.loadtxt(W/'segmented.dat',skiprows=1);assert a.shape==(256,28) and np.isfinite(a).all()
code=np.arange(256);assert np.allclose(a[:,0],code,atol=1e-12)
assert np.max(abs(a[:,5:13]-3.3*((code[:,None]>>np.arange(8))&1)))<1e-9
assert np.max(abs(a[:,13:]-3.3*((code[:,None]//16)>=np.arange(1,16))))<.01
v=a[:,2]-a[:,1];lsb=(v[-1]-v[0])/255;assert lsb>0
base=json.loads((B/'result.json').read_text());case=next(c for c in base['cases'] if c['name']=='v2.15_r100')
assert sha(B/'v2.15_r100.dat')==case['artifacts_sha256']['.dat']
b=np.loadtxt(B/'v2.15_r100.dat',skiprows=1);assert np.allclose(b[:,0],code)
out=dict(status='connected_segmented_DC_measured',monotonic=bool(np.all(np.diff(v)>0)),endpoints_v=[float(v[0]),float(v[-1])],lsb_v=float(lsb),max_abs_inl_lsb=float(np.max(abs((v-v[0])/lsb-code))),max_abs_dnl_lsb=float(np.max(abs(np.diff(v)/lsb-1))),max_difference_from_binary_v=float(np.max(abs(v-(b[:,2]-b[:,1])))),loaded_decoder_checks=3840,manifest=m,artifacts=r['artifacts_sha256'],limitations=['Nominal matched devices; ideal bias current, resistive termination and command sources.', 'Full code DC only; no glitch, noise, mismatch, SFDR or RF integration qualification.', 'Combinational decoder has unequal path delays and no retiming.'])
assert out['monotonic']
(P/'evidence/dac-segmented8-dc.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k not in ('manifest','artifacts')},indent=2))
