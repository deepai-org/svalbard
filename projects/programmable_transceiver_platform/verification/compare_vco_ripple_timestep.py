#!/usr/bin/env python3
"""Compare measured ripple response without declaring numerical convergence."""
import hashlib,json,math
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
paths=[P/'evidence'/name for name in ('vco-supply-ripple.json','vco-supply-ripple-fine.json')]
a,b=[json.loads(p.read_text()) for p in paths]
out=dict(status='pending',completed=False,input_audit_sha256={p.name:sha(p) for p in paths},limitations=['Two timesteps provide sensitivity evidence, not proof of convergence to the physical solution.','One deterministic disturbance; no intrinsic jitter/noise, process or full PLL qualification.'])
if a['completed'] and b['completed']:
 roots=[R/'scratch'/name for name in ('transceiver-vco-supply-ripple','transceiver-vco-supply-ripple-fine')]
 assert a['provenance']['source_sha256_before']==b['provenance']['source_sha256_before']
 for root,audit in zip(roots,(a,b)):
  for case in audit['provenance']['cases']:
   for ext,h in case['artifacts_sha256'].items():assert sha(root/(case['name']+ext))==h
 for name in ('quiet','ripple'):
  coarse=(roots[0]/(name+'.spice')).read_text();fine=(roots[1]/(name+'.spice')).read_text()
  assert coarse.count('tran 2p 201n 0 2p uic')==1
  assert coarse.replace('tran 2p 201n 0 2p uic','tran 1p 201n 0 1p uic')==fine
 assert [w['window_ns'] for w in a['windows']]==[w['window_ns'] for w in b['windows']]
 out.update(status='terminal_comparison',completed=True,windows=[])
 for x,y in zip(a['windows'],b['windows']):
  phase=math.atan2(y['cos_ps'],y['sin_ps'])-math.atan2(x['cos_ps'],x['sin_ps'])
  phase=math.atan2(math.sin(phase),math.cos(phase))
  out['windows'].append(dict(window_ns=x['window_ns'],coarse_peak_ps=x['ripple_peak_ps'],fine_peak_ps=y['ripple_peak_ps'],peak_change_ps=y['ripple_peak_ps']-x['ripple_peak_ps'],peak_change_percent=100*(y['ripple_peak_ps']/x['ripple_peak_ps']-1),phase_change_degrees=math.degrees(phase),sin_cos_vector_change_ps=math.hypot(y['sin_ps']-x['sin_ps'],y['cos_ps']-x['cos_ps']),offset_change_ps=y['offset_ps']-x['offset_ps'],drift_change_ps_per_ns=y['drift_ps_per_ns']-x['drift_ps_per_ns'],coarse_residual_rms_ps=x['residual_rms_ps'],fine_residual_rms_ps=y['residual_rms_ps']))
(P/'evidence/vco-ripple-timestep-comparison.json').write_text(json.dumps(out,indent=2)+'\n')
print(out['status'],out['completed']);print(out.get('windows',[]))
