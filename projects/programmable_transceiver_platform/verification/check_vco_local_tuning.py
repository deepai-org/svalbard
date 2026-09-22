#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];W=ROOT/'scratch/transceiver-vco-local-tuning';r=json.loads((W/'result.json').read_text())
for c in r['cases']:
 name=f"v{c['control_v']:g}"
 for s,h in c['artifacts_sha256'].items():assert hashlib.sha256((W/(name+s)).read_bytes()).hexdigest()==h
 assert c['gate_range_v'][0]>1.4 and c['gate_range_v'][1]<1.6
r['local_tuning_sign_consistent']=all(x>0 for x in r['slopes_hz_per_v']) or all(x<0 for x in r['slopes_hz_per_v'])
r['feedback_interpretation']='Positive local tuning: sourcing pump current speeds VCO; REF-leading UP has negative-feedback polarity.' if all(x>0 for x in r['slopes_hz_per_v']) else 'Do not assume positive local tuning; inspect measured slopes before feedback connection.'
(ROOT/'projects/programmable_transceiver_platform/evidence/vco-local-tuning.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(dict(cases=[(c['control_v'],c['frequency_hz']) for c in r['cases']],slopes=r['slopes_hz_per_v'],interpretation=r['feedback_interpretation']),indent=2))
