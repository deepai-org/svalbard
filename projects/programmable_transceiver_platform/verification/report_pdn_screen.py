import hashlib,json,re,sys
from pathlib import Path
from collections import Counter
root=Path(sys.argv[1]);p=root/'projects/programmable_transceiver_platform';out=root/'scratch/transceiver-pdn'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
log=(out/'pdn.log').read_text()
assert 'PDN_SCREEN_COMPLETE' in log and '[ERROR' not in log
for net in ['VDD_CORE','VSS_CORE']:assert f'All shapes on net {net} are connected.' in log
assert 'check failed' not in log
before=(root/'scratch/transceiver-repaired-geometry/supply-connected.def').read_text();after=(out/'digital-pdn.def').read_text()
for section in ['COMPONENTS','NETS']:
 def extract(s):return re.search(r'^'+section+r' .*?^END '+section,s,re.M|re.S)[0]
 assert extract(before)==extract(after),section
counts={net:Counter() for net in ['VDD_CORE','VSS_CORE']}
for line in (out/'grid-shapes.tsv').read_text().splitlines():
 net,kind=line.split('\t');counts[net][kind]+=1
for net,values in counts.items():
 for kind in ['Metal1','Metal4','Metal5','VIA']:assert values[kind]>0,(net,kind)
base=json.loads((p/'evidence/repaired-geometry-supply-screen.json').read_text())
assert sha(root/'scratch/transceiver-repaired-geometry/supply-connected.odb')==base['artifact_sha256']['supply-connected.odb']
r={'scope':'Provisional local digital PDN generation and OpenROAD connectivity/placement checks, not power integrity or full-chip DRC/LVS',
 'input_database_sha256':base['artifact_sha256']['supply-connected.odb'],
 'grid':{'Metal1':{'width_um':0.6,'followpins':True},'Metal4':{'width_um':2.0,'pitch_um':80,'offset_um':10},'Metal5':{'width_um':4.0,'pitch_um':80,'offset_um':10},'connections':[['Metal1','Metal4'],['Metal4','Metal5']],'generated_access_pin_layer':'Metal5'},
 'special_wire_shape_counts':counts,'checks':['Both rail shape networks connected by check_power_grid','Post-PDN check_placement passes','DEF components and signal NETS sections unchanged'],
 'rejected_low_layer_trial':'Metal2/Metal3 strap version connected electrically but failed placement blocked-layer checks on 7572 instances; retained source in evidence/experiments/pdn-low-layer.tcl',
 'artifact_sha256':{f:sha(out/f) for f in ['digital-pdn.odb','digital-pdn.def','pdn.log','grid-shapes.tsv']},
 'source_sha256':{f:sha(p/'verification'/f) for f in ['pdn_screen.tcl','run_pdn_screen.sh','report_pdn_screen.py']},
 'limitations':['Provisional widths/pitch; no current/activity-based sizing, IR drop or electromigration check.','Generated local power access pins are not package-pad connections; single CORE supply/return delivery remains unfinished.','No independent DRC/LVS, via enclosure/array signoff or well/substrate/tap continuity qualification.','Upper-layer routing resources now consumed; signal/clock congestion and timing must be re-evaluated.','No extracted timing or supply-noise qualification; prior setup/recovery failures and incomplete analog/DDR blocks remain.']}
(p/'evidence/digital-pdn-screen.json').write_text(json.dumps(r,indent=2)+'\n')
print('PDN_SCREEN_RECORDED',dict(counts))
