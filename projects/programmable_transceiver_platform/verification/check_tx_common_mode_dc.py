#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-tx-common-mode-dc';B=R/'scratch/transceiver-tx-dac-commutator-dc'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
 with p.open() as f:h=f.readline().lower().split()
 a=np.loadtxt(p,skiprows=1);assert a.shape==(256,len(h)) and np.isfinite(a).all() and np.array_equal(a[:,0],np.arange(256))
 return h,a
m=json.loads((W/'manifest.json').read_text());r=json.loads((W/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before'];assert sha(B/'r50_lo1.spice')==m['baseline_deck_sha256']
assert [(c['name'],c['term_v'],c['cm_v']) for c in r['cases']]==[('lower',1.85,1.59),('baseline',2.15,1.89),('upper',2.45,2.19)]
rows=[]
for c in r['cases']:
 name=c['name'];d=(W/(name+'.spice')).read_text()
 expected=(B/'r50_lo1.spice').read_text().replace('VTERM TERM 0 2.15',f"VTERM TERM 0 {c['term_v']}").replace('VCM CM 0 1.89',f"VCM CM 0 {c['cm_v']}").replace('/work/r50_lo1.dat',f'/work/{name}.dat')
 assert d==expected and sha(W/(name+'.spice'))==c['deck_sha256_before']
 for ext,h in c['artifacts_sha256'].items():assert sha(W/(name+ext))==h
 assert c['returncode']==0 and 'aborted' not in (W/(name+'.log')).read_text().lower()
 h,a=read(W/(name+'.dat'))
 if name=='baseline':
  hb,ab=read(B/'r50_lo1.dat');assert h==hb and np.array_equal(a,ab)
 def v(k):return a[:,h.index(k)]
 bb=v('v(op)')-v('v(on)');rf=v('v(rfp)')-v('v(rfn)');fit=rf[0]+np.arange(256)*(rf[-1]-rf[0])/255
 # Differential equivalent, not an individual FET's channel resistance.
 req=50*(bb/rf-1)
 rows.append(dict(name=name,rf_endpoint_magnitude_v=float(abs(rf[-1])),bb_endpoint_magnitude_v=float(abs(bb[-1])),endpoint_voltage_ratio=float(rf[-1]/bb[-1]),differential_equivalent_series_ohm_range=[float(req.min()),float(req.max())],on_gate_minus_higher_terminal_v_range=[float((3.3-np.maximum(v('v(op)'),v('v(rfp)'))).min()),float((3.3-np.maximum(v('v(op)'),v('v(rfp)'))).max())],monotonic=bool(np.all(np.diff(rf)<0)),max_endpoint_fit_error_v=float(abs(rf-fit).max())))
out=dict(status='completed_common_mode_diagnostic',baseline_bit_identical=True,cases=rows,provenance=r,limitations=['Equivalent series resistance includes whole static bridge behavior; no individual FET OP, body-effect attribution or noise inferred.', 'Gate minus terminal voltage is not overdrive: threshold and body bias not probed.', 'Moving both ideal biases changes DAC compliance as well as switch operating point; no isolated mechanism claimed.', 'No RF dynamic, mismatch, reconstruction or autonomous LO qualification.'])
(P/'evidence/tx-common-mode-dc.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(rows,indent=2))
