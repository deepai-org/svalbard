#!/usr/bin/env python3
"""Verify declared integration and report DC interface metrics, never RF qualification."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-tx-dac-commutator-dc';B=R/'scratch/transceiver-dac-segmented-dc'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((W/'manifest.json').read_text());assert sha(B/'segmented.spice')==m['baseline_deck_sha256']
out=dict(status='pending',cases=[],limitations=['Static matched typical only, ideal bias/LO/common-mode and resistors.', 'No reconstruction, LO drive loading, RF output matching, quadrature or RF spectral/noise qualification.', 'Loads are scenarios, not validated physical package bounds.'])
if (W/'result.json').exists():
 r=json.loads((W/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before']
 assert [c['name'] for c in r['cases']]==m['planned_cases']
 for c in r['cases']:
  name=c['name'];load=c['load_ohm'];state=c['lo_state'];d=(W/(name+'.spice')).read_text()
  add='.include /wifi/rf_switch_mixer/mixer.spice\n.include /screen/tx/commutator.spice\n'
  add+=f'VLO LO 0 {3.3*state}\nVLOB LOB 0 {3.3*(1-state)}\nVCM CM 0 1.89\nRLP CM RFP {load}\nRLN CM RFN {load}\nXM OP ON RFP RFN LO LOB 0 pt_tx_commutator\n'
  assert d.count(add)==1
  restored=d.replace(add,'').replace(f'/work/{name}.dat','/work/segmented.dat').replace(' v(RFP) v(RFN) i(VCM) i(VTERM)\n.endc','\n.endc')
  assert restored==(B/'segmented.spice').read_text()
  assert sha(W/(name+'.spice'))==c['deck_sha256_before']
  for ext,h in c['artifacts_sha256'].items():assert sha(W/(name+ext))==h
  log=(W/(name+'.log')).read_text();assert c['returncode']==0 and not c['timed_out'] and 'aborted' not in log.lower()
  path=W/(name+'.dat');header=path.open().readline().lower().split();a=np.loadtxt(path,skiprows=1)
  assert a.shape==(256,len(header)) and np.isfinite(a).all() and np.array_equal(a[:,0],np.arange(256))
  def v(key):return a[:,header.index(key)]
  bb=v('v(op)')-v('v(on)');rf=v('v(rfp)')-v('v(rfn)');oriented=rf*(1 if state else -1)
  step=np.diff(oriented); endpoint=oriented[[0,-1]];fit=endpoint[0]+np.arange(256)*(endpoint[1]-endpoint[0])/255
  out['cases'].append(dict(name=name,completed=True,declared_change_verified=True,rf_endpoint_v=rf[[0,-1]].tolist(),bb_endpoint_v=bb[[0,-1]].tolist(),bb_common_mode_range_v=[float(((v('v(op)')+v('v(on)'))/2).min()),float(((v('v(op)')+v('v(on)'))/2).max())],monotonic=bool(np.all(step>0) or np.all(step<0)),max_endpoint_fit_error_v=float(abs(oriented-fit).max()),rf_to_bb_endpoint_ratio=float(rf[-1]/bb[-1]),elapsed_seconds=c['elapsed_seconds']))
 out['status']='completed_static_interface_diagnostic';out['provenance']=r
(P/'evidence/tx-dac-commutator-dc.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='provenance'},indent=2))
