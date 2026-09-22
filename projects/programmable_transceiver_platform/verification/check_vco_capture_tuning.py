#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];W=ROOT/'scratch/transceiver-vco-capture-tuning';r=json.loads((W/'result.json').read_text())
for c in r['cases']:
 for s,h in c['artifacts_sha256'].items():assert hashlib.sha256((W/(f"v{c['control_v']:g}"+s)).read_bytes()).hexdigest()==h
 assert c['gate_range_v'][0]>1.4 and c['gate_range_v'][1]<1.6
r['secant_sign_change_observed']=min(r['slopes_hz_per_v'])<0<max(r['slopes_hz_per_v'])
r['interpretation']='A fixed UP-increases-frequency relationship cannot be assumed across the sampled range; turning point resolution and robust branch selection remain open.' if r['secant_sign_change_observed'] else 'No sign reversal between sampled points; monotonicity between or beyond points remains unproved.'
r['limitations'].append('41ns snapshots; final slow divider/PFD acquisition not exercised. No precise turning point or globally monotonic interval established.')
(ROOT/'projects/programmable_transceiver_platform/evidence/vco-capture-tuning.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
