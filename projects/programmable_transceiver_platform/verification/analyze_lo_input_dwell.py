"""Correlate ring-cycle input dwell with output threshold edges; no causality claim."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';B=R/'scratch/transceiver-lo-receiver-replay-prepared'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((B/'manifest.json').read_text());assert sha(B/'parent_samples.npy')==m['artifacts_sha256']['parent_samples.npy']
a=np.load(B/'parent_samples.npy');h=m['sample_columns'];t=a[:,0];assert np.isfinite(a).all() and np.all(np.diff(t)>0)
def v(n):return a[:,h.index(n)]
def edges(y,threshold):
 k=np.flatnonzero((y[:-1]<threshold)&(y[1:]>=threshold));return t[k]+(threshold-y[k])*np.diff(t)[k]/np.diff(y)[k]
ring=edges(v('v(p)')-v('v(n)'),0);dc=P/'evidence/lo-transfer-dc.json';d=json.loads(dc.read_text());assert d['completed'];threshold=d['cases'][0]['threshold_inputs_v']['out'];rows=[]
for suffix in ('ip','in','qp','qn'):
 y=v('v(b'+suffix+')');out=edges(v('v(o'+suffix+')'),1.65);cycles=[]
 for lo,hi in zip(ring[:-1],ring[1:]):
  if lo<512e-9 or hi>1024e-9:continue
  mask=(t>lo)&(t<hi);tt=np.r_[lo,t[mask],hi];yy=np.interp(tt,t,y)
  # Linear segment fractions above threshold; integrate dwell exactly for that interpolation.
  z=yy-threshold;fraction=(z[:-1]>0).astype(float);cross=z[:-1]*z[1:]<0
  rising=cross&(z[:-1]<0);falling=cross&(z[:-1]>0)
  fraction[rising]=z[1:][rising]/(z[1:][rising]-z[:-1][rising]);fraction[falling]=z[:-1][falling]/(z[:-1][falling]-z[1:][falling])
  above=float(np.sum(np.diff(tt)*fraction)/(hi-lo));count=int(((out>=lo)&(out<hi)).sum())
  cycles.append(dict(start_ns=float(lo*1e9),output_rises=count,input_min_v=float(yy.min()),input_max_v=float(yy.max()),fraction_above_static_threshold=above))
 summary={}
 for count in sorted(set(c['output_rises'] for c in cycles)):
  group=[c for c in cycles if c['output_rises']==count];summary[str(count)]=dict(cycles=len(group),dwell_range=[min(c['fraction_above_static_threshold'] for c in group),max(c['fraction_above_static_threshold'] for c in group)],minimum_input_range_v=[min(c['input_min_v'] for c in group),max(c['input_min_v'] for c in group)],maximum_input_range_v=[min(c['input_max_v'] for c in group),max(c['input_max_v'] for c in group)])
 rows.append(dict(leg=suffix,groups_by_output_rises=summary,cycles=cycles))
out=dict(completed=True,parent_samples_sha256=sha(B/'parent_samples.npy'),dc_evidence_sha256=sha(dc),static_threshold_v=threshold,legs=rows,limitations=['Ring-defined bins can assign an edge to an adjacent cycle as phase changes; missing bins alone are not proof of lost pulses.', 'Static unloaded threshold is diagnostic, not a dynamic switching or mixer-conduction threshold.', 'Dwell correlation does not establish a unique mechanism; replay MID/PRE and loading evidence still required.'])
(P/'evidence/lo-input-dwell.json').write_text(json.dumps(out,indent=2)+'\n')
for x in rows:print(x['leg'],x['groups_by_output_rises'])
