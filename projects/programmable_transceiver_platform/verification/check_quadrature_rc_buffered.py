#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-quadrature-rc-buffered'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((W/'manifest.json').read_text());r=json.loads((W/'result.json').read_text());assert m['buffered'] and not m['asymmetric']
assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before'] and len(r['cases'])==1
c=r['cases'][0];assert c['returncode']==0 and c['load_f']==c['q_load_f']==25e-15
for ext,h in c['artifacts_sha256'].items():assert sha(W/(c['name']+ext))==h
assert c['deck_sha256_before']==c['artifacts_sha256']['.spice']
baseline=R/'scratch/transceiver-quadrature-rc'
prior=json.loads((baseline/'result.json').read_text())
old=next(x for x in prior['cases'] if x['name']=='load25')
assert sha(baseline/'load25.spice')==old['artifacts_sha256']['.spice']
addition='.include /screen/lo_buffer.spice\nVBUF VDD 0 3.3\n'
for node in ('IP','IN','QP','QN'):
 addition+=f'XC{node} {node} B{node} pt_ref_reservoir_4\nRFB{node} B{node} XB{node}.MID 100k\nXB{node} B{node} O{node} VDD 0 pt_lo_buffer\nCL{node} O{node} 0 50f\n'
expected=(baseline/'load25.spice').read_text().split('.control')[0].replace('CIP IP CM',addition+'CIP IP CM')
assert (W/'load25.spice').read_text().split('.control')[0]==expected
with (W/'load25.dat').open() as f:assert f.readline().lower().split()==['frequency','ir','ii','qr','qi','bir','bii','bqr','bqi']
a=np.loadtxt(W/'load25.dat',skiprows=1);assert a.shape==(41,9) and np.isfinite(a).all() and np.allclose(a[:,0],np.linspace(2e9,3e9,41),rtol=1e-12,atol=0)
with (W/'load25-bias.dat').open() as f:assert f.readline().lower().split()[1:]==['v(bip)','v(bin)','v(bqp)','v(bqn)','i(vbuf)']
b=np.loadtxt(W/'load25-bias.dat',skiprows=1);assert b.shape==(6,) and np.isfinite(b).all()
metrics={}
for name,col in [('rc_nodes',1),('buffer_outputs',5)]:
 i=a[:,col]+1j*a[:,col+1];q=a[:,col+2]+1j*a[:,col+3];phase=np.angle(q/i,deg=True);gain=abs(q/i);k=20
 metrics[name]=dict(i_gain=float(abs(i[k])),q_gain=float(abs(q[k])),q_over_i=float(gain[k]),q_lead_degrees=float(phase[k]),phase_range_deg=[float(phase.min()),float(phase.max())])
out=dict(completed=True,provenance=r,bias_input_v=list(map(float,b[1:5])),buffer_supply_current_a=float(-b[5]),at_2p5ghz=metrics,limitations=['Small-signal AC about DC self-bias; not large-signal clock edges, limiting, startup or mixer drive.','Ideal source/common-mode/supply,100k feedback resistors and50fF output loads; PDK MIM coupling and actual16 buffer FETs.','Matched branches only; process/mismatch/noise and oscillator integration remain open.'])
(P/'evidence/quadrature-rc-buffered.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='provenance'},indent=2))
