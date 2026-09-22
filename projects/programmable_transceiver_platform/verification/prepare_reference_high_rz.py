#!/usr/bin/env python3
"""One high-reference compensation-resistor change under verified measured load."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';B=R/'scratch/transceiver-reference-load-startup-prepared';W=R/'scratch/transceiver-reference-load-startup-full';O=R/'scratch/transceiver-reference-high-rz-prepared'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
e=json.loads((P/'evidence/reference-load-startup-full.json').read_text());assert e['completed'] and e['diagnostic_reproduction_pass']
for ext,h in e['provenance']['artifacts_sha256'].items():assert sha(W/('load'+ext))==h
m=json.loads((B/'manifest.json').read_text());assert sha(B/'demand.spice')==m['demand_sha256']
base=(W/'load.spice').read_text();cell=(P/'analog/reference/adc_reference_pair_tuned.spice').read_text()
old='XHIGH HIGH_TARGET VH BN BP VDD VSS pt_reference_buffer_complement_tune S=4 CC=2p RZ=2000'
assert cell.count(old)==1;changed=cell.replace(old,old.replace('RZ=2000','RZ=4000'))
inc='.include /screen/reference/adc_reference_pair_tuned.spice';assert base.count(inc)==1
d=base.replace(inc,changed);assert d.replace(changed,inc)==base
O.mkdir(exist_ok=True);(O/'load.spice').write_text(d);(O/'demand.spice').write_bytes((B/'demand.spice').read_bytes())
m.update(deck_sha256=sha(O/'load.spice'),candidate_baseline_deck_sha256=sha(W/'load.spice'),candidate_exact_reversal=True,scope='High-reference RZ parameter2000->4000 atS4: physical ideal series resistor500->1000ohm. Low reference, CC8pF, device sizes, load and solver unchanged.',hypothesis='Stronger high-rail compensation damping may reduce overshoot/recovery error; bandwidth loss may worsen next decision. Evaluate all windows and power, not only worst droop.')
(O/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');(P/'evidence/reference-high-rz-preparation.json').write_text(json.dumps(m,indent=2)+'\n');print('high-reference resistor-only reversal; identical load bytes')
