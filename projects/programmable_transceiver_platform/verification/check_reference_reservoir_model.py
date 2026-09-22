#!/usr/bin/env python3
import hashlib,json,re
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-reference-reservoir-model'
r=json.loads((W/'result.json').read_text());s=(P/'analog/reference/reservoir_mim.spice').read_text();assert hashlib.sha256(s.encode()).hexdigest()==r['source_sha256']
blocks=dict(re.findall(r'\.subckt (\w+) P N\n(.*?)\.ends',s,re.S))
assert blocks['pt_ref_reservoir_1']=='XC P N cap_mim_1f5_m4m5_noshield c_length=5u c_width=5u\n'
counts={'pt_ref_reservoir_1':1}
for i in range(1,12):
 n=2**i;name=f'pt_ref_reservoir_{n}';assert blocks[name]==f'XA P N pt_ref_reservoir_{n//2}\nXB P N pt_ref_reservoir_{n//2}\n';counts[name]=2*counts[f'pt_ref_reservoir_{n//2}']
assert counts['pt_ref_reservoir_2048']==2048
unit=json.loads((P/'evidence/adc-mim-model-audit.json').read_text());assert {c['corner'] for c in r['cases']}=={'typical','ss','ff'}
for c in r['cases']:
 for ext,digest in c['artifacts_sha256'].items():assert hashlib.sha256((W/(c['corner']+ext)).read_bytes()).hexdigest()==digest
 expected=2048*next(x['capacitance_f'] for x in unit['cases'] if x['corner']==c['corner'] and x['par']==1 and x['bias_v']==1)
 assert abs(c['capacitance_f']/expected-1)<1e-8
r.update(status='explicit_reservoir_model_capacitance_checked',units_per_rail=2048,limitations=['Conditional installed MIM option; no layout, extracted parasitics, mismatch or process-bound qualification.', 'Verifies model replication, not stability or regulation when connected to a driver.'])
(P/'evidence/reference-reservoir-model.json').write_text(json.dumps(r,indent=2)+'\n');print([(c['corner'],c['capacitance_f']*1e12) for c in r['cases']])
