#!/usr/bin/env python3
"""Validate reconstructed source currents against directly saved SPICE currents."""
import hashlib,json
from pathlib import Path
import numpy as np
from tx_load_power import delivered_currents
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-tx-dac-commutator-dc'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((W/'result.json').read_text());rows=[]
for name in ('r50_lo0','r50_lo1'):
 c=next(c for c in r['cases'] if c['name']==name)
 for ext,h in c['artifacts_sha256'].items():assert sha(W/(name+ext))==h
 d=(W/(name+'.spice')).read_text().splitlines()
 for line in ['VTERM TERM 0 2.15','RP TERM OP 100','RN TERM ON 100','VCM CM 0 1.89','RLP CM RFP 50','RLN CM RFN 50']:assert line in d
 with (W/(name+'.dat')).open() as f:h=f.readline().lower().split()
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert a.shape==(256,len(h)) and np.isfinite(a).all()
 def v(k):return a[:,h.index(k)]
 term,cm=delivered_currents(v('v(op)'),v('v(on)'),v('v(rfp)'),v('v(rfn)'))
 et=float(abs(term+v('i(vterm)')).max());ec=float(abs(cm+v('i(vcm)')).max());assert max(et,ec)<1e-12
 rows.append(dict(name=name,term_current_max_error_a=et,load_bias_current_max_error_a=ec,artifact_sha256=c['artifacts_sha256']))
(P/'evidence/tx-load-power-contract.json').write_text(json.dumps(dict(status='source_current_reconstruction_verified',cases=rows,scope='Two static256-code50ohm cases verify resistor current sign/scale only; no whole-chip power claim.'),indent=2)+'\n');print(rows)
