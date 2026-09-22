import hashlib,json,re,sys
from pathlib import Path
root=Path(sys.argv[1]); project=root/'projects/programmable_transceiver_platform'
out=root/'scratch/transceiver-placement-repair'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
text=(out/'repair.log').read_text()
assert 'CONSTRAINT_AUDIT_END' in text and not re.search(r'\[ERROR|^Error:',text,re.M)
m=re.search(r'REPAIR_METRICS (\d+) ([\d.]+) (\d+)',text);assert m and int(m[3])==0
domains={}
for name,body in re.findall(r'DOMAIN_BEGIN (\w+)\n(.*?)DOMAIN_END \1',text,re.S):
 groups={}
 for block in body.split('Startpoint:')[1:]:
  g=re.search(r'Path Group: (\S+)',block);s=re.search(r'(-?\d+\.\d+)\s+slack \(',block)
  if g and s:groups.setdefault(g[1],[]).append(float(s[1]))
 assert groups
 domains[name]={k:min(v) for k,v in groups.items()}
assert len(domains)==8
base=json.loads((project/'evidence/placed-timing-screen.json').read_text())
assert sha(root/'scratch/transceiver-placement/digital.odb')==base['database_sha256']
r={'scope':'Experimental placement-aware electrical repair; not adopted or equivalence-qualified',
 'input_database_sha256':base['database_sha256'],'before':base['cases'][1],
 'after':{'cells':int(m[1]),'cell_area_um2':float(m[2]),'unplaced':int(m[3]),'worst_slacks_ns':domains,
 'electrical_violation_rows':text.split('ELECTRICAL_AUDIT_BEGIN')[1].split('ELECTRICAL_AUDIT_END')[0].count('(VIOLATED)')},
 'artifact_sha256':{f:sha(out/f) for f in ['repair.log','repaired.odb','repaired.def','repaired.v']},
 'source_sha256':{f:sha(project/'verification'/f) for f in ['repair_placement_screen.tcl','run_placement_repair.sh','report_placement_repair.py']},
 'limitations':base['limitations']+['OpenROAD detailed placement/check_placement only; independent geometry and transformed-netlist equivalence not yet rerun.','Electrical repair is not setup/hold optimization. No CTS, routed extraction or full-chip integration.']}
(project/'evidence/placement-repair-screen.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r['after'],indent=2))
