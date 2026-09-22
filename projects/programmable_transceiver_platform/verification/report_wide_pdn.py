import hashlib,json,re,sys
from pathlib import Path
from collections import Counter
root=Path(sys.argv[1]);p=root/'projects/programmable_transceiver_platform';out=root/'scratch/transceiver-wide-pdn'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
log=(out/'pdn.log').read_text();assert 'PDN_SCREEN_COMPLETE' in log and '[ERROR' not in log and 'check failed' not in log
for net in ['VDD_CORE','VSS_CORE']:assert f'All shapes on net {net} are connected.' in log
old=(root/'scratch/transceiver-repaired-geometry/supply-connected.def').read_text();new=(out/'digital-pdn.def').read_text()
for section in ['COMPONENTS','NETS']:
 assert re.search(r'^'+section+r' .*?^END '+section,old,re.M|re.S)[0]==re.search(r'^'+section+r' .*?^END '+section,new,re.M|re.S)[0]
geometry=json.loads((p/'evidence/wide-pdn-geometry.json').read_text());ir=json.loads((p/'evidence/wide-pdn-resistance.json').read_text())
assert geometry['input_database_sha256']==ir['input_database_sha256']==sha(out/'digital-pdn.odb')
areas={}
for label,folder in [('previous','transceiver-pdn-geometry'),('wide','transceiver-wide-pdn-geometry')]:
 counts=Counter()
 for line in (root/'scratch'/folder/'rectangles.tsv').read_text().splitlines():
  net,layer,x0,y0,x1,y1,kind=line.split('\t')
  if kind=='STRIPE':counts[layer]+=(int(x1)-int(x0))*(int(y1)-int(y0))/2000**2
 areas[label]=dict(counts)
previous=json.loads((p/'evidence/pdn-resistance-screen.json').read_text())
for net in ['VDD_CORE','VSS_CORE']:
 assert (root/'scratch/transceiver-pdn-ir48'/f'{net}.csv').read_bytes()==(root/'scratch/transceiver-wide-pdn-ir48'/f'{net}.csv').read_bytes()
r={'scope':'Wider local-grid candidate compared under identical requested ideal feeds and explicit uniform DC loads; not physical signoff',
 'strap_widths_um':{'Metal4':4,'Metal5':8},'pitch_um':80,'stripe_rectangle_area_um2_by_layer':areas,
 'previous_combined_voltage':previous['combined'],'candidate_combined_voltage':ir['combined'],
 'actual_source_nodes':{n:ir['rails'][n]['ideal_source'] for n in ir['rails']},
 'geometry_report_sha256':sha(p/'evidence/wide-pdn-geometry.json'),'resistance_report_sha256':sha(p/'evidence/wide-pdn-resistance.json'),
 'artifact_sha256':{f:sha(out/f) for f in ['digital-pdn.odb','digital-pdn.def','pdn.log']},
 'source_sha256':{f:sha(p/'verification'/f) for f in ['wide_pdn_screen.tcl','run_wide_pdn.sh','report_wide_pdn.py']},
 'decision':'Retain separate candidate for congestion/current-density evaluation; not an approved replacement grid.',
 'limitations':['Requested feed regions match, but source node snapping may change with geometry; comparison includes that effect.','Strap rectangle area is not routed congestion or available track capacity.','Uniform-load assumption, ideal feeds and nominal resistor models are not worst-case bounds.','No IR/EM limits, dynamic/package model, process corners, full DRC/LVS or well/tap qualification.','Full chip still lacks timing closure and completed analog/DDR macros.']}
(p/'evidence/wide-pdn-comparison.json').write_text(json.dumps(r,indent=2)+'\n')
print('WIDE_PDN_COMPARISON_PASS',areas)
