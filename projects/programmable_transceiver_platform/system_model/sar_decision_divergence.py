"""Localize first ideal/actual SAR decision divergence, without assigning causality."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parents[1];R=P.parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--variant',choices=['double','rzero','divider','clamped'],default='double');args=ap.parse_args()
folder='sar-reservoir-full' if args.variant=='double' else 'sar-reference-'+args.variant
ideal_name='sar-ideal-transfer' if args.variant=='double' else 'sar-'+args.variant+'-ideal-transfer'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
e=P/'evidence'/(ideal_name+'.json');ideal=json.loads(e.read_text());source=P/'evidence'/(folder+'.json');assert sha(source)==ideal['source_sha256'];d=json.loads(source.read_text());rows=[]
for variant,key,folder,name in [('baseline','baseline_frames','adc-sar8-reference-reservoir','typical_first1'),(args.variant,'frames',folder,'baseline')]:
 p=R/('scratch/transceiver-'+folder)/(name+'.dat')
 if variant!='baseline':assert sha(p)==d['waveform_sha256']
 else:
  m=json.loads((R/'scratch/transceiver-sar-reservoir-full-prepared/manifest.json').read_text());assert sha(p)==m['donor_artifacts_sha256']['.dat']
 with p.open() as f:h=f.readline().lower().split()
 a=np.loadtxt(p,skiprows=1)
 def at(n,ns):return float(np.interp(ns*1e-9,a[:,0],a[:,h.index('v('+n+')')]))
 for frame in d[key]:
  anchor=frame['steps'][0]['preclock_residue_v'];span0=frame['steps'][0]['preclock_span_v'];hold=frame['hold_ns'];target=next(r for r in ideal['results'] if r['variant']==variant and r['hold_ns']==hold);events=[]
  for actual,expected in zip(frame['steps'],target['ideal_held_steps']):
   ns=actual['clock_ns'];bits=[at('sd'+str(k),ns) for k in range(8)];assert all(v<.33 or v>2.97 for v in bits)
   code=sum(int(v>1.65)*2**k for k,v in enumerate(bits));keep=actual['comparator_v']<0
   nominal=anchor+(code-128)/128
   rail=anchor+((2*code-255)*actual['preclock_span_v']-span0)/256
   events.append(dict(bit=actual['bit'],actual_trial=code,ideal_trial=expected['trial'],actual_keep=keep,ideal_keep=expected['keep'],actual_residue_v=actual['preclock_residue_v'],nominal_rail_residue_v=nominal,measured_rail_residue_v=rail,remaining_residual_v=actual['preclock_residue_v']-rail,decision_diverges=keep!=expected['keep']))
  first=next((x for x in events if x['decision_diverges']),None)
  if first:assert first['actual_trial']==first['ideal_trial']
  rows.append(dict(variant=variant,hold_ns=hold,first_divergence=first,steps=events))
out=dict(source_sha256=sha(e),results=rows,limitations=['Measured-rail formula assumes all bottom plates follow rails and equal capacitors; residual is not exclusively switch injection.','Held anchor hides initial acquisition/loading errors.','After first divergent decision, ideal and actual trial histories differ; later differences are not matched-input comparisons.','No noise, mismatch or parasitic qualification.'])
(P/'evidence'/('sar-decision-divergence.json' if args.variant=='double' else 'sar-'+args.variant+'-decision-divergence.json')).write_text(json.dumps(out,indent=2)+'\n')
for r in rows:print(r['variant'],r['hold_ns'],r['first_divergence'])
