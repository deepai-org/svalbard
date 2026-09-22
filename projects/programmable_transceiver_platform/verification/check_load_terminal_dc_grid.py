"""Validate independent DC-grid artifacts before publishing current ranges."""
import hashlib,json
import numpy as np
from pathlib import Path
P=Path(__file__).resolve().parents[1];R=P.parents[1]
W=R/'scratch/transceiver-load-terminal-dc-grid'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((W/'result.json').read_text())
assert r['source_hashes_before']==r['source_hashes_after']
assert sha(P/'evidence/reference-load-bias-envelope.json')==r['source_hashes_before']['/input/envelope.json']
assert sha(P/'analog/reference/load_terminal_dc_grid.py')==r['source_hashes_before']['/screen/reference/load_terminal_dc_grid.py']
for ext,h in r['artifacts_sha256'].items():assert sha(W/('probe'+ext))==h
assert len(r['cases'])==50
summary=[]
spec=json.loads((P/'evidence/reference-load-bias-envelope.json').read_text())
for kind in ('n','p'):
 rows=[c for c in r['cases'] if c['type']==kind]
 bounds,=[b for b in spec['proposed_independent_sweep'] if b['rail']==('xhigh' if kind=='n' else 'xlow')]
 expected={(d,g) for d in np.linspace(*bounds['drain_bounds_v'],5) for g in np.linspace(*bounds['gate_bounds_v'],5)}
 assert {(c['drain_v'],c['gate_v']) for c in rows}==expected and len(expected)==25
 assert all(abs(c['terminal_kcl_error_a'])<1e-14 for c in rows)
 assert all(abs(c['drain_minus_channel_a']+c['body_current_a'])<1e-14 for c in rows)
 currents=[c['drain_minus_channel_a'] for c in rows]
 summary.append(dict(type=kind,minimum_excess_a=min(currents),maximum_excess_a=max(currents),
                     charge_range_over_1p1ns_c=[min(currents)*1.1e-9,max(currents)*1.1e-9]))
r.update(grid_summaries=summary,checker_sha256=sha(Path(__file__)),physical_qualification=False)
(P/'evidence/load-terminal-dc-grid.json').write_text(json.dumps(r,indent=2,allow_nan=False)+'\n')
print(json.dumps(summary,indent=2))
