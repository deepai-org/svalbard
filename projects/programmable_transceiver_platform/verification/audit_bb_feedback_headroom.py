#!/usr/bin/env python3
"""Check reported PMOS headroom against physical source/drain voltages."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-bb-feedback-gain'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
E=P/'evidence/bb-feedback-gain.json';e=json.loads(E.read_text());assert e['completed'];rows=[]
for c in e['provenance']['cases']:
 name=c['name']
 for ext,h in c['artifacts_sha256'].items():assert sha(W/(name+ext))==h
 with (W/(name+'-op.dat')).open() as f:h=f.readline().lower().split()
 a=np.loadtxt(W/(name+'-op.dat'),skiprows=1);assert len(a)==len(h) and np.isfinite(a).all();v=dict(zip(h,a));devs=[]
 for stage,tail,dp,dn in [('xa','v(xdut.t1)','v(xdut.mn)','v(xdut.mp)'),('xb','v(xdut.t2)','v(on)','v(op)')]:
  for dev,physical in [('xip',v[tail]-v[dp]),('xin',v[tail]-v[dn]),('xtail',3.3-v[tail])]:
   key=f'@m.xdut.{stage}.{dev}.m0';reported=float(v[key+'[vds]']);sat=float(v[key+'[vdsat]'])
   assert physical>0 and abs(physical-reported)<1e-10
   devs.append(dict(device=stage+'.'+dev,physical_vsd_v=float(physical),reported_vds_v=reported,reported_vdsat_v=sat,reported_headroom_v=reported-sat))
 rows.append(dict(name=name,feedback_ohm=c['feedback_ohm'],source_common_mode_v=c['common_mode_v'],devices=devs,worst_reported_headroom_v=min(x['reported_headroom_v'] for x in devs)))
out=dict(parent_evidence_sha256=sha(E),cases=rows,limitations=['Nominal stationary zero-differential operating points only; does not establish swing, mismatch, bias tolerance or dynamic headroom.','Positive reported saturation margin is not sufficient evidence of loop stability or achievable closed-loop gain.','Physical-to-model voltage orientation checked for these operating points; not a universal reverse-operation convention.'])
(P/'evidence/bb-feedback-headroom.json').write_text(json.dumps(out,indent=2)+'\n')
for row in rows:print(row['name'],row['worst_reported_headroom_v'])
