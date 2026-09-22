#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];P=ROOT/'projects/programmable_transceiver_platform';W=ROOT/'scratch/transceiver-vco-split-lower';r=json.loads((W/'result.json').read_text())
for c in r['cases']:
 for s,h in c['artifacts_sha256'].items():assert hashlib.sha256((W/(f"v{c['control_v']:g}"+s)).read_bytes()).hexdigest()==h
 assert c['gate_range_v'][0]>1.4 and c['gate_range_v'][1]<1.6
upper=json.loads((P/'evidence/vco-split-tuning.json').read_text());points=sorted(r['cases']+upper['cases'],key=lambda c:c['control_v'])
r['combined_points']=[dict(control_v=c['control_v'],frequency_hz=c['frequency_hz']) for c in points]
r['all_sampled_secants_positive']=all(b['frequency_hz']>a['frequency_hz'] for a,b in zip(points,points[1:]))
r['nominal_targets_bracketed']={str(f):any(a['frequency_hz']<=f<=b['frequency_hz'] for a,b in zip(points,points[1:])) for f in (2.4e9,2.5e9)}
r['limitations']=[x.replace('Four tuning points','Sampled tuning points') for x in r['limitations']]
r['limitations'].append('Sampled frequency bracketing is not startup, continuous monotonicity, process coverage or capture-range qualification.')
(P/'evidence/vco-split-lower.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
