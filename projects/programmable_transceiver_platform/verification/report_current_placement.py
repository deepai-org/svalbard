"""Bind latest accepted RTL/mapping to a separate diagnostic placement."""
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1]);p=root/'projects/programmable_transceiver_platform';out=root/'scratch/transceiver-current-placement'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
placement=json.loads((out/'placement-screen.json').read_text())
timing=json.loads((out/'placed-timing-screen.json').read_text())
characterization=json.loads((p/'evidence/fifo-flags-screen.json').read_text())
oldplacement=json.loads((p/'evidence/digital-placement-screen.json').read_text())
oldtiming=json.loads((p/'evidence/placed-timing-screen.json').read_text())
assert placement['pdk_sha256']==oldplacement['pdk_sha256'],'PDK changed'
assert placement['row_area_um2']==oldplacement['row_area_um2'],'region changed'
assert timing['database_sha256']==placement['artifact_sha256']['digital.odb']
for name,digest in characterization['area_screen']['source_sha256'].items():assert sha(p/name)==digest,name
expected=characterization['profiles'][1]['worst_reported_slack_ns_by_domain_and_group']
actual=timing['cases'][0]['worst_slacks_ns']
assert actual.keys()==expected.keys()
for domain,groups in expected.items():
 assert actual[domain].keys()==groups.keys()
 for group,slack in groups.items():assert abs(actual[domain][group]-slack)<0.0002,(domain,group)
r={'scope':'Current pass-41 accepted RTL diagnostic placement and signal-RC timing; no tapeout/signoff claim',
 'placement':placement,'timing':timing,'previous_placed_timing':oldtiming['cases'][1],
 'characterization_sha256':sha(p/'evidence/fifo-flags-screen.json'),
 'checks':['Source and netlist hashes match characterized accepted RTL','Same PDK and realized row area as previous placement','Independent geometry checks and three negative controls pass','Zero-RC placed timing reproduces every characterized domain/group within 0.0002 ns'],
 'source_sha256':{f:sha(p/'verification'/f) for f in ['run_current_placement.sh','report_current_placement.py']},
 'limitations':['Current mapped candidate has not undergone whole-design formal equivalence. Prior mapped proof does not apply.','No CTS, propagated clocks, reset repair, PDN, analog macros, routing or extracted coupling.','Metal3 uniform-layer placement RC is illustrative, not a proven uncertainty bound.','External IO remains unconstrained. Electrical violations can cause extrapolation.','No routability, total-power, full-chip DRC/LVS or protocol qualification.']}
(p/'evidence/current-placement-screen.json').write_text(json.dumps(r,indent=2)+'\n')
print('CURRENT_PLACEMENT_REPORT_PASS',placement['instances'],placement['row_utilization'],timing['cases'][1]['worst_slacks_ns'])
