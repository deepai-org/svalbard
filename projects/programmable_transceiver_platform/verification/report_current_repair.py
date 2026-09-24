from timing_log import domain_group_slacks
import hashlib,json,re,sys
from pathlib import Path
root=Path(sys.argv[1]);p=root/'projects/programmable_transceiver_platform';out=root/'scratch/transceiver-current-repair'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
base=json.loads((p/'evidence/current-placement-screen.json').read_text())
assert sha(root/'scratch/transceiver-current-placement/digital.odb')==base['placement']['artifact_sha256']['digital.odb']
text=(out/'repair.log').read_text();assert 'CONSTRAINT_AUDIT_END' in text and not re.search(r'\[ERROR|^Error:',text,re.M)
m=re.search(r'REPAIR_METRICS (\d+) ([\d.]+) (\d+)',text);assert m and int(m[3])==0
domains=domain_group_slacks(text)
assert len(domains)==8
proof=json.loads((out/'proof/equivalence-result.json').read_text())
assert proof['proof_status']=='pass' and proof['gold_sha256']==sha(out/'gold.json') and proof['gate_sha256']==sha(out/'gate.json')
# Check that the exported JSON instances agree with the physical counts.
gold=json.loads((out/'gold.json').read_text())['modules']['pt_digital']['cells']
gate=json.loads((out/'gate.json').read_text())['modules']['pt_digital']['cells']
assert len(gold)==base['placement']['instances'] and len(gate)==int(m[1])
changed=[{'instance':k,'before':gold[k]['type'],'after':gate[k]['type']} for k in gold if k in gate and gold[k]['type']!=gate[k]['type']]
r={'scope':'Electrical repair of current placed candidate, with mapped-state next-state/output equivalence; not RTL-to-gates or signoff',
 'before':base['timing']['cases'][1],
 'after':{'cells':int(m[1]),'cell_area_um2':float(m[2]),'unplaced':int(m[3]),'worst_slacks_ns':domains,'electrical_violation_rows':text.split('ELECTRICAL_AUDIT_BEGIN')[1].split('ELECTRICAL_AUDIT_END')[0].count('(VIOLATED)')},
 'missing_tie_failure':json.loads((p/'evidence/missing-tie-failure.json').read_text()),
 'resized_instances':changed,'inserted_instances':sorted(set(gate)-set(gold)),'removed_instances':sorted(set(gold)-set(gate)),
 'input_database_sha256':base['placement']['artifact_sha256']['digital.odb'],'equivalence':proof,
 'artifact_sha256':{f:sha(out/f) for f in ['repair.log','repaired.odb','repaired.def','repaired.v','gold.json','gate.json','gold-read.log','gate-read.log']},
 'source_sha256':{f:sha(p/'verification'/f) for f in ['current_repair_screen.tcl','run_current_repair.sh','report_current_repair.py','timing_log.py']},
 'limitations':['OpenROAD legalizes/checks placement; independent post-repair geometry checks not yet rerun.','Equivalence compares mapped artifacts under matching arbitrary register state, not original behavioral RTL.','Ideal clocks, uniform Metal3 placement estimate, no extracted/coupled routing, PDN or analog macros.','No external IO, full-chip power, protocol timing or signoff qualification.']}
(p/'evidence/current-repair-screen.json').write_text(json.dumps(r,indent=2)+'\n')
print('CURRENT_REPAIR_PASS',r['after'])
