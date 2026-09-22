import hashlib,json,re,sys
from pathlib import Path
root=Path(sys.argv[1]);p=root/'projects/programmable_transceiver_platform';out=root/'scratch/transceiver-repaired-geometry'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
g=json.loads((out/'placement-screen.json').read_text())
before=[l.split('\t') for l in (out/'supply-before.tsv').read_text().splitlines()]
after=[l.split('\t') for l in (out/'supply-after.tsv').read_text().splitlines()]
expected={'VDD':('POWER','VDD_CORE'),'VNW':('POWER','VDD_CORE'),'VSS':('GROUND','VSS_CORE'),'VPW':('GROUND','VSS_CORE')}
def verify(rows):
 instances={}
 for inst,master,pin,kind,net in rows:
  assert pin in expected and (kind,net)==expected[pin],(inst,pin,kind,net)
  assert pin not in instances.setdefault(inst,set());instances[inst].add(pin)
 assert len(instances)==g['instances']
 assert all(pins==set(expected) for pins in instances.values())
verify(after)
assert [r[:4] for r in before]==[r[:4] for r in after]
assert all(r[4]=='UNCONNECTED' for r in before)
# A wrong-rail assignment must fail the same checker.
bad=[r[:] for r in after];bad[0][4]='VSS_CORE' if bad[0][4]=='VDD_CORE' else 'VDD_CORE'
try:verify(bad)
except AssertionError:pass
else:raise AssertionError('wrong supply escaped checker')
assert (out/'signals-before.tsv').read_bytes()==(out/'signals-after.tsv').read_bytes(),'signal connectivity changed'
def components(name):return re.search(r'\nCOMPONENTS .*?\nEND COMPONENTS', (out/name).read_text(),re.S)[0]
assert components('digital.def')==components('supply-connected.def'),'placement changed'
r={'scope':'Independent repaired geometry and logical power/well net assignment only; no metal power delivery',
 'geometry':g,'supply_pins_checked':len(after),'initially_unconnected':len(before),'remaining_unconnected':0,
 'tie_supply_pins_checked':sum('__tie' in r[1] for r in after),'rail_mapping':expected,
 'checks':['all instances have exactly four expected supply/well pins','wrong-rail negative control rejected','all non-supply instance-pin connections unchanged','DEF component placement unchanged'],
 'artifact_sha256':{f:sha(out/f) for f in ['supply-before.tsv','supply-after.tsv','signals-before.tsv','signals-after.tsv','supply-connected.odb','supply-connected.def']},
 'source_sha256':{f:sha(p/'verification'/f) for f in ['repaired_geometry_screen.tcl','run_repaired_geometry.sh','report_repaired_geometry.py']},
 'limitations':['Global connection assigns database nets only; no straps, rails, vias, taps, pad connections or IR/EM closure.','Well/substrate continuity and isolation require layout/LVS qualification.','Original mapped equivalence covers signal logic; these logical supply assignments do not prove powered behavior.','All prior setup/recovery failures and analog/DDR/full-chip signoff gaps remain.']}
(p/'evidence/repaired-geometry-supply-screen.json').write_text(json.dumps(r,indent=2)+'\n')
print('REPAIRED_GEOMETRY_SUPPLY_PASS',g['instances'],len(after),r['tie_supply_pins_checked'])
