"""Retain completed positive and negative controls, never a pending proof claim."""
import hashlib
import json
from pathlib import Path
import sys
out=Path(sys.argv[1]);project=Path(__file__).resolve().parents[1]
r=json.loads((out/'equivalence-inputs.json').read_text())
positive=(out/'proof.log').read_text();negative=(out/'negative-proof.log').read_text()
assert 'SAT proof finished - no model found: SUCCESS!' in positive
assert 'proof did fail' in negative and '\\trigger' in negative
r['proof_status']='pass'
r['negative_control']='Deliberate inversion of status[0] rejected by the same SAT comparison'
r['library_sha256']=(out/'library.sha256').read_text().split()[0]
r['artifact_sha256']={name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in ['gold-cut.json','gate-cut.json','gate-negative.json','proof.log','negative-proof.log']}
r['harness_sha256']={name:hashlib.sha256((project/'verification'/name).read_bytes()).hexdigest() for name in ['mapping_equivalence.py','run_mapping_equivalence.sh','report_mapping_equivalence.py']}
r['limitations']=['Two-state Boolean equivalence under matched arbitrary register state; no X/metastability/glitch/timing proof.',
 'Compares selected mapped artifacts, not original behavioral RTL against gates.',
 'All mapped register cell types/parameters and input pins are compared; equivalent initial state correspondence is required.',
 'No placement, wire parasitics, clock/reset physical distribution or analog qualification.']
r['harness_correction']='Negative control initially exposed inconsistent port/net-name wiring; generator now checks these agree and mutates both. Corrected positive and negative checks both rerun.'
(out/'equivalence-result.json').write_text(json.dumps(r,indent=2)+'\n')
print(f"EQUIVALENCE_RECORDED registers={r['matched_registers']} input_bits={r['register_input_bits_observed']} output_bits={r['top_output_bits']}")
