"""Observation replay and physical DC current balance through feedback sections."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';B=R/'scratch/transceiver-bb-programmed-feedback';W=R/'scratch/transceiver-bb-programmed-feedback-probe'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
records=[json.loads((x/'result.json').read_text()) for x in (B,W)];rows=[]
for feedback in (20000,40000):
 n=f'cm1.177_fb{feedback}';ops=[];decks=[]
 for root,r in zip((B,W),records):
  assert r['source_sha256_before']==r['source_sha256_after'];c=next(c for c in r['cases'] if c['name']==n);assert c['returncode']==0
  for ext,h in c['artifacts_sha256'].items():assert sha(root/(n+ext))==h
  with (root/(n+'-op.dat')).open() as f:header=f.readline().lower().split()
  op=np.loadtxt(root/(n+'-op.dat'),skiprows=1);assert len(header)==len(op) and np.isfinite(op).all();ops.append(dict(zip(header,op)));decks.append((root/(n+'.spice')).read_text())
 assert decks[1].replace(' v(XDUT.FBP) v(XDUT.FBN)','')==decks[0]
 assert (W/(n+'.dat')).read_bytes()==(B/(n+'.dat')).read_bytes()
 assert all(ops[1][k]==v for k,v in ops[0].items())
 v=ops[1];legs=[]
 for out,mid,gate in [('on','fbp','gp'),('op','fbn','gn')]:
  vo=v[f'v({out})'];vm=v[f'v(xdut.{mid})'];vg=v[f'v(xdut.{gate})']
  first=(vo-vm)/20000;second=(vm-vg)/20000;switch=first-second
  legs.append(dict(leg=mid,out_v=float(vo),mid_v=float(vm),input_gate_v=float(vg),first_resistor_current_a=float(first),parallel_resistor_current_a=float(second),switch_current_by_kcl_a=float(switch),switch_drop_v=float(vm-vg),dc_secant_switch_ohm=float((vm-vg)/switch) if feedback==20000 else None,effective_feedback_dc_ohm=float((vo-vg)/first)))
 rows.append(dict(nominal_feedback_ohm=feedback,legs=legs))
out=dict(completed=True,original_OP_and_AC_bitidentical=True,cases=rows,provenance=records,limitations=['DC KCL uses two ideal20kohm resistors; terminal gate leakage is included in surrounding circuit.','On-state V/I is a secant at this bias, not incremental RF impedance or voltage-independent on-resistance.','Off-state residual is a subtraction of similar currents; not a validated leakage floor.','No mode-transition, distortion, mismatch or temperature qualification.'])
(P/'evidence/bb-feedback-switch-drop.json').write_text(json.dumps(out,indent=2)+'\n');print(rows)
