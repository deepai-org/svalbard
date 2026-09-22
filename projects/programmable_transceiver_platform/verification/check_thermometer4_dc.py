#!/usr/bin/env python3
"""Independent numerical truth-table audit of 15 transistor threshold outputs."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-dac-thermometer-dc'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((W/'result.json').read_text());m=json.loads((W/'manifest.json').read_text())
assert r['returncode']==0 and r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before']
for ext,h in r['artifacts_sha256'].items():assert sha(W/('decoder'+ext))==h
assert sha(W/'decoder.spice')==m['deck_sha256_before']
assert sha(P/'analog/dac/thermometer4.spice')==r['source_sha256_before']['/screen/dac/thermometer4.spice']
with (W/'decoder.dat').open() as f:header=f.readline().lower().split()
assert header[1:]==[f'v(d{i})' for i in range(4)]+[f'v(t{k})' for k in range(1,16)]+['i(vdd)']
a=np.loadtxt(W/'decoder.dat',skiprows=1);assert a.shape==(16,21) and np.isfinite(a).all()
assert np.allclose(a[:,0],np.arange(16),atol=1e-12)
commands=3.3*((np.arange(16)[:,None]>>np.arange(4))&1);assert np.max(abs(a[:,1:5]-commands))<1e-9
expected=np.arange(16)[:,None]>=np.arange(1,16)
err=abs(a[:,5:20]-3.3*expected);assert np.max(err)<.01
out=dict(status='nominal_DC_truth_table_verified',input_codes=16,threshold_checks=240,max_rail_error_v=float(err.max()),max_static_supply_current_a=float(np.max(-a[:,20])),manifest=m,artifacts=r['artifacts_sha256'],limitations=['20fF ideal output loads do not qualify dynamic fanout.', 'No transition hazards, input skew, timing, mismatch or corners tested.', 'No retiming; decoder has unequal logic depths and shared terms.', 'Not yet integrated with current cells; no DAC glitch improvement established.'])
(P/'evidence/dac-thermometer4-dc.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k not in ('manifest','artifacts')},indent=2))
