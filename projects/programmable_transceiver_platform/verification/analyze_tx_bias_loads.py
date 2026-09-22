#!/usr/bin/env python3
"""Measured requirements for still-ideal TX bias drivers; not driver qualification."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';rows=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for variant,folder in [('nmos','transceiver-tx-dac-commutator-dc'),('tg','transceiver-tx-tg-dc')]:
 W=R/'scratch'/folder;r=json.loads((W/'result.json').read_text())
 for c in r['cases']:
  name=c['name'];assert c['returncode']==0
  for ext,h in c['artifacts_sha256'].items():assert sha(W/(name+ext))==h
  with (W/(name+'.dat')).open() as f:h=f.readline().lower().split()
  a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert a.shape==(256,len(h)) and np.isfinite(a).all() and np.array_equal(a[:,0],np.arange(256))
  rails={}
  for label,key in [('termination_2p15v','i(vterm)'),('rf_common_mode_1p89v','i(vcm)')]:
   delivered=-a[:,h.index(key)]
   rails[label]=dict(min_delivered_a=float(delivered.min()),max_delivered_a=float(delivered.max()),source_required=bool(np.any(delivered>1e-9)),sink_required=bool(np.any(delivered< -1e-9)),minimum_at_code=int(a[np.argmin(delivered),0]),maximum_at_code=int(a[np.argmax(delivered),0]))
  load=50 if name.startswith('r50_') else 200
  deck=(W/(name+'.spice')).read_text().splitlines()
  assert f'RLP CM RFP {load}' in deck and f'RLN CM RFN {load}' in deck
  branch={}
  for label,node,bias,resistance in [('term_p','v(op)',2.15,100),('term_n','v(on)',2.15,100),('rf_p','v(rfp)',1.89,load),('rf_n','v(rfn)',1.89,load)]:
   current=(bias-a[:,h.index(node)])/resistance
   branch[label]=dict(min_delivered_a=float(current.min()),max_delivered_a=float(current.max()))
  rows.append(dict(variant=variant,case=name,rail_currents=rails,individual_resistor_currents=branch,artifacts_sha256=c['artifacts_sha256']))
out=dict(status='static_TX_bias_load_requirements',cases=rows,limitations=['Signed current from ideal supplies in matched static sweeps; actual voltage/current reference drivers remain missing.', 'Aggregate rail current is not per-output current or RF transient peak demand.', 'Selected loads/codes do not bound mismatch, parasitics, operating modes or package behavior.'])
(P/'evidence/tx-bias-load-requirements.json').write_text(json.dumps(out,indent=2)+'\n')
for row in rows:print(row['variant'],row['case'],row['rail_currents'])
