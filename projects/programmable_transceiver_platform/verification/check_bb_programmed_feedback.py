"""Compare actual transistor-selected feedback to ideal resistor settings."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-bb-programmed-feedback';B=R/'scratch/transceiver-bb-feedback-gain'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
records=[json.loads((x/'result.json').read_text()) for x in (B,W)];rows=[]
assert len(records[1]['cases'])==2
for feedback in (20000,40000):
 name=f'cm1.177_fb{feedback}';data=[];decks=[]
 for root,r in zip((B,W),records):
  assert r['source_sha256_before']==r['source_sha256_after'];c=next(x for x in r['cases'] if x['name']==name);assert c['returncode']==0
  for ext,h in c['artifacts_sha256'].items():assert sha(root/(name+ext))==h
  log=(root/(name+'.log')).read_text().lower();assert not any(k in log for k in ('warning','error','aborted'))
  with (root/(name+'.dat')).open() as f:assert f.readline().lower().split()==['frequency','gr','gi','ir','ii']
  a=np.loadtxt(root/(name+'.dat'),skiprows=1);assert a.shape==(100,5) and np.isfinite(a).all();decks.append((root/(name+'.spice')).read_text());data.append(a)
 expected=decks[0].replace('/screen/bb_filter_section.spice','/screen/bb_filter_programmable.spice').replace(f'XDUT IP IN OP ON BIAS VDD 0 pt_bb_filter RFB={feedback} C=20p','XDUT IP IN OP ON BIAS VDD 0 SEL SELB pt_bb_filter_programmable C=20p')
 expected=expected.replace('.control',f'VSEL SEL 0 {3.3 if feedback==20000 else 0}\nVSELB SELB 0 {0 if feedback==20000 else 3.3}\n.control');assert expected==decks[1]
 b,c=data;assert np.array_equal(b[:,0],c[:,0]);bg=abs(b[:,1]+1j*b[:,2]);cg=abs(c[:,1]+1j*c[:,2]);points=[]
 for f in (1e6,5e6,10e6,20e6):
  k=int(abs(b[:,0]-f).argmin());assert abs(b[k,0]-f)<1
  points.append(dict(hz=f,ideal_gain=float(bg[k]),switched_gain=float(cg[k]),relative_gain_change=float(cg[k]/bg[k]-1)))
 rows.append(dict(feedback_ohm=feedback,points=points))
out=dict(completed=True,cases=rows,provenance=records,cell_sha256=sha(P/'analog/bb_filter_programmable.spice'),limitations=['Only nominal static complementary selects; mode transitions, control skew, charge injection, noise and mismatch unqualified.','Lumped resistors/capacitors and ideal select/bias voltages; physical resistor bank and control logic still missing.','Only two modest gain settings; does not close the roughly31–35x additional gain requirement.','No adoption into connected receiver or stability qualification.'])
(P/'evidence/bb-programmed-feedback.json').write_text(json.dumps(out,indent=2)+'\n');print(rows)
