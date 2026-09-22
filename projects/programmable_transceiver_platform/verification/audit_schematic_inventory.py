#!/usr/bin/env python3
"""Record source existence and declared gaps, without equating existence to readiness."""
import hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];P=ROOT/'projects/programmable_transceiver_platform'
r=json.loads((P/'spec/schematic-implementation.json').read_text())
for b in r['blocks']:
 b['sources']=[]
 for name in b['source_paths']:
  p=ROOT/name;assert p.is_file(),name
  b['sources'].append(dict(path=name,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),subcircuits=re.findall(r'^\.subckt\s+(\S+)',p.read_text(),re.M|re.I)))
r['source_presence_checked']=True;r['whole_chip_schematic_ready']=False
(P/'evidence/schematic-implementation-audit.json').write_text(json.dumps(r,indent=2)+'\n')
print('Audited',len(r['blocks']),'block obligations; whole-chip schematic incomplete, layout gate closed.')
