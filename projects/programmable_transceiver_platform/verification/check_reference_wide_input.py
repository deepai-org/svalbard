#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-reference-pair-wide-input-dc';B=R/'scratch/transceiver-reference-pair-device-dc'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((W/'change-manifest.json').read_text());assert len(m['changes'])==2
for old,new in m['changes']:
 assert old.startswith(('XIP ','XIN ')) and 'pfet_03v3' in old
 assert new==old.replace('w=8u l=.5u','w=16u l=.5u')
pair=(P/'analog/reference/adc_reference_pair_tuned.spice').read_text()
for file in ('buffer_scaled_tune.spice','buffer_complement_tune.spice'):
 cell=(P/'analog/reference'/file).read_text()
 for old,new in m['changes']:cell=cell.replace(old,new)
 pair=pair.replace('.include /screen/reference/'+file,cell)
records=[json.loads((root/'result.json').read_text()) for root in (B,W)];rows=[]
for name,target in [('VH',2.15),('VL',1.15)]:
 arrays=[]
 for root,record in zip((B,W),records):
  assert record['sources_before']==record['sources_after'];c=next(x for x in record['cases'] if x['name']==name);assert c['returncode']==0
  for ext,h in c['artifacts_sha256'].items():assert sha(root/(name+ext))==h
  log=(root/(name+'.log')).read_text().lower();assert not any(x in log for x in ['warning','error','aborted'])
  with (root/(name+'.dat')).open() as f:h=f.readline().lower().split()
  a=np.loadtxt(root/(name+'.dat'),skiprows=1);assert a.shape==(41,len(h)) and np.isfinite(a).all();arrays.append((h,a))
 expected=(B/(name+'.spice')).read_text().replace('.include /screen/reference/adc_reference_pair_tuned.spice',pair);assert expected==(W/(name+'.spice')).read_text()
 (h,b),(ch,c)=arrays;assert h==ch and np.array_equal(b[:,0],c[:,0]);node='v(oh)' if name=='VH' else 'v(ol)';stage='xhigh' if name=='VH' else 'xlow';values=[]
 for label,a in [('baseline',b),('candidate',c)]:
  v=dict(zip(h,a[20]));stem=f'@m.xdut.{stage}.'
  values.append(dict(case=label,error_v=float(v[node]-target),mirror_current_difference_a=float(v[stem+'xmn.m0[id]']-v[stem+'xmp.m0[id]']),tail_margin_v=float(v[stem+'xt.m0[vds]']-v[stem+'xt.m0[vdsat]']),tail_margin_sweep_min_v=float((a[:,h.index(stem+'xt.m0[vds]')]-a[:,h.index(stem+'xt.m0[vdsat]')]).min()),tail_margin_sweep_max_v=float((a[:,h.index(stem+'xt.m0[vds]')]-a[:,h.index(stem+'xt.m0[vdsat]')]).max()),supply_power_w=float(-3.3*v['i(vdd)'])))
 rows.append(dict(rail=name,values=values))
out=dict(disposition="Diagnostic only: wider high input pair does not restore reported tail saturation margin; retained baseline unchanged.",completed=True,exact_declared_changes_verified=True,cases=rows,provenance=records,limitations=['DC only; Wider input devices increase capacitance and area; compensation and connected dynamics must be rechecked.','Widening input FETs changes operating current and capacitance as well as headroom; not a unique causal proof.','Ideal target/bias and zero external load remain.'])
(P/'evidence/reference-wide-input.json').write_text(json.dumps(out,indent=2)+'\n');print(rows)
