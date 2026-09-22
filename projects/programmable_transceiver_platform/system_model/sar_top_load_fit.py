"""Observed-trajectory loading hypothesis; train one frame, check two others."""
import hashlib,json
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parents[1];source=P/'evidence/sar-all-bottom-plates.json'
r=json.loads(source.read_text());assert r['completed'] and r['original_vectors_maximum_difference']==0
f=r['frames'][0];anchor=f['steps'][0]['actual_residue_v']
x=np.array([s['bottom_plate_prediction_v']-anchor for s in f['steps'][1:]])
y=np.array([s['actual_residue_v']-anchor for s in f['steps'][1:]])
beta=float(x@y/(x@x));assert 0<beta<1
rows=[]
for f in r['frames']:
    anchor=f['steps'][0]['actual_residue_v']
    errors=[s['actual_residue_v']-(anchor+beta*(s['bottom_plate_prediction_v']-anchor)) for s in f['steps']]
    rows.append(dict(hold_ns=f['hold_ns'],training=f is r['frames'][0],maximum_residue_error_v=max(map(abs,errors)),errors_v=errors))
out=dict(beta=beta,equivalent_extra_capacitance_ratio=1/beta-1,frames=rows,
    source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    limitations=['Uses measured bottom trajectories and frame anchors; not autonomous conversion prediction.',
      'Effective capacitance is a hypothesis, not unique identification of physical devices.',
      'Two held-out conversions at one magnitude do not establish generality or noise tolerance.'])
(P/'evidence/sar-top-load-fit.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
