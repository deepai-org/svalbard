#!/usr/bin/env python3
import hashlib,json,re
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-reference-breakpoint'
r=json.loads((W/'result.json').read_text());assert {c['kind'] for c in r['cases']}=={'pulse','pwl'}
for c in r['cases']:
 name=c['kind'];assert c['returncode']==0
 for ext,digest in c['artifacts_sha256'].items():assert hashlib.sha256((W/(name+ext)).read_bytes()).hexdigest()==digest
 source=R/'scratch'/('transceiver-closed-loop-gear' if name=='pulse' else 'transceiver-closed-loop-pwl-reference')/'closed.spice';assert hashlib.sha256(source.read_bytes()).hexdigest()==c['reference_source_deck_sha256']
 d=(W/(name+'.spice')).read_text();assert next(x for x in source.read_text().splitlines() if x.startswith('VREF ')) in d
 assert 'tran 2p 3201n 0 2p uic' in d
 log=(W/(name+'.log')).read_text();assert 'aborted' not in log and 'Timestep too small' not in log
 m=re.search(r'final_output\s*=\s*([0-9.e+-]+)',log,re.I);assert m
 c['final_output_v']=float(m.group(1))
r['status']='both_minimal_passive_reference_tests_complete';r['interpretation']='The reference fixture alone completes with a passive load. This does not isolate the active PLL failure or establish a simulator bug.'
(P/'evidence/reference-breakpoint-screen.json').write_text(json.dumps(r,indent=2)+'\n');print(r['interpretation'])
