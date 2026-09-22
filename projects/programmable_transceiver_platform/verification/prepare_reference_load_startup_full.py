#!/usr/bin/env python3
"""Promote tested first-ps source representation to full diagnostic horizon."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';B=R/'scratch/transceiver-reference-load-prepared';S=R/'scratch/transceiver-reference-load-startup';O=R/'scratch/transceiver-reference-load-startup-prepared'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((S/'result.json').read_text());c=next(c for c in r['cases'] if c['case']=='startup1ps');assert c['returncode']==0
assert sha(S/'startup1ps-demand.spice')==c['source_sha256']
e=json.loads((P/'evidence/reference-load-startup.json').read_text());assert next(x for x in e['cases'] if x['case']=='startup1ps')['completed']
m=json.loads((B/'manifest.json').read_text());assert sha(B/'load.spice')==m['deck_sha256']
O.mkdir(exist_ok=True);(O/'load.spice').write_bytes((B/'load.spice').read_bytes());(O/'demand.spice').write_bytes((S/'startup1ps-demand.spice').read_bytes())
m.update(demand_sha256=sha(O/'demand.spice'),startup_approximation_max_current_change_a=c['startup_max_current_change_a'],startup_evidence_sha256=sha(P/'evidence/reference-load-startup.json'),scope='Same full209.9ns measured-load circuit; only first1ps source interpolation changed as validated short test.')
(O/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');(P/'evidence/reference-load-startup-full-preparation.json').write_text(json.dumps(m,indent=2)+'\n');print('unchanged full circuit; verified startup-source bytes')
