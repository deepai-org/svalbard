"""Audit the pinned PDNSim additive-current/report-override discrepancy."""
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1]);p=root/'projects/programmable_transceiver_platform'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
results=[];artifacts={}
for net in ['VDD_CORE','VSS_CORE']:
 currents={};resistors={};sources={}
 for ma in [0,24,48]:
  folder=root/f'scratch/transceiver-pdn-ir{ma}';path=folder/f'{net}.spice'
  log=(folder/'ir.log').read_text();assert 'IR_SCREEN_COMPLETE' in log and '[ERROR' not in log
  lines=path.read_text().splitlines()
  currents[ma]={l.split()[0]:float(l.split()[-1]) for l in lines if l.startswith('I')}
  resistors[ma]=[l for l in lines if l.startswith('R')];sources[ma]=[l for l in lines if l.startswith('V')]
  assert len(currents[ma])==26438
  artifacts[str(path.relative_to(root))]=sha(path)
  artifacts[str((folder/'ir.log').relative_to(root))]=sha(folder/'ir.log')
 assert resistors[0]==resistors[24]==resistors[48]
 assert sources[0]==sources[24]==sources[48]
 assert currents[0].keys()==currents[24].keys()==currents[48].keys()
 # SPICE emits rounded current values. Check every source, not only total load.
 zero=sum(currents[0].values());assert zero>.03
 errors={}
 for ma in [24,48]:
  errors[ma]=max(abs(currents[ma][n]-currents[0][n]-ma/1000/26438) for n in currents[0])
  assert errors[ma]<1.1e-8,(net,ma,errors[ma])
  assert abs(sum(currents[ma].values())-zero-ma/1000)<2e-5
 results.append({'net':net,'source_count':26438,'zero_user_load_current_a':zero,
  'total_exported_current_a':{ma:sum(v.values()) for ma,v in currents.items()},'maximum_node_addition_error_a':errors})
source=root/'scratch/pdnsim-source/ir_solver.cpp'
if not source.exists():
 import urllib.request
 source.parent.mkdir(parents=True,exist_ok=True)
 source.write_bytes(urllib.request.urlopen('https://raw.githubusercontent.com/The-OpenROAD-Project/OpenROAD/dcf36133a369abc8f3c5e5738cd4d82e4903c0e0/src/psm/src/ir_solver.cpp',timeout=30).read())
assert sha(source)=='b69bd5ea8e408e5a45a157b3a4e24b57b38fa72d3609e18fc802bfd6531ea893','pinned source content differs'
text=source.read_text()
start=text.index('IRSolver::Power IRSolver::buildNodeCurrentMap(');end=text.index('return total_power;',start)
body=text[start:end]
assert body.count('currents[node] += current / nodes.size();')==2
assert 'instance_powers[inst] = find_power->second;' in body
r={'scope':'Pinned-tool load-model bug diagnosis, not chip current characterization',
 'tool_commit':'dcf36133a369abc8f3c5e5738cd4d82e4903c0e0',
 'source_url':'https://github.com/The-OpenROAD-Project/OpenROAD/blob/dcf36133a369abc8f3c5e5738cd4d82e4903c0e0/src/psm/src/ir_solver.cpp#L831',
 'source_file_sha256':sha(source),'results':results,'artifact_sha256':artifacts,'checker_sha256':sha(p/'verification/check_pdnsim_loads.py'),
 'finding':'buildNodeCurrentMap first adds automatic STA currents, then adds user currents with +=; the separate instance_powers map is overwritten for the printed total. User power therefore does not replace current in this revision.',
 'action':'Do not use direct PDNSim voltages as specified-load results. Continue independently solving exported resistor topology with explicit audited currents. No local tool binary patch applied.',
 'limitations':['Automatic-current residue is an unqualified tool estimate, not measured or bounded silicon current.','Diagnosis is specific to this pinned revision; other revisions require separate verification.','Independent resistor model still lacks package, process, dynamic and full physical signoff qualification.']}
(p/'evidence/pdnsim-load-audit.json').write_text(json.dumps(r,indent=2)+'\n')
print('PDNSIM_LOAD_AUDIT_PASS',results)
