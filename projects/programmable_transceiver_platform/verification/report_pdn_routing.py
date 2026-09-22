import hashlib,json,re,sys
from pathlib import Path
root=Path(sys.argv[1]);p=root/'projects/programmable_transceiver_platform'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
cases=[]
clocks={'host_tx_clk','host_rx_clk','wire_rx_clk','wire_tx_clk','rf_rx_clk','rf_tx_clk','host_sclk','ref_clk'}
for name,folder,record in [('original','transceiver-pdn','digital-pdn-screen.json'),('wide','transceiver-wide-pdn','wide-pdn-comparison.json')]:
 base=json.loads((p/'evidence'/record).read_text());db=root/'scratch'/folder/'digital-pdn.odb'
 assert sha(db)==base['artifact_sha256']['digital-pdn.odb']
 out=root/f'scratch/transceiver-pdn-routing-{name}';text=(out/'routing.log').read_text()
 assert 'PDN_ROUTING_SCREEN_COMPLETE' in text and '[ERROR' not in text
 table=text.split('Final congestion report:')[-1];layers={}
 for layer,resource,demand,usage,h,v,total in re.findall(r'^(Metal\d|Total)\s+(\d+)\s+(\d+)\s+([\d.]+)%\s+(\d+)\s*/\s*(\d+)\s*/\s*(\d+)',table,re.M):
  layers[layer]={'resource':int(resource),'demand':int(demand),'usage_percent':float(usage),'max_horizontal_overflow':int(h),'max_vertical_overflow':int(v),'total_overflow':int(total)}
 assert set(layers)=={'Metal1','Metal2','Metal3','Metal4','Metal5','Total'}
 guide=(out/'routes.guide').read_text();nets=re.findall(r'^([^\n]+)\n\(\n',guide,re.M)
 routed=int(re.search(r'Routed nets: (\d+)',text)[1]);assert len(nets)==len(set(nets))==routed
 assert clocks<=set(nets),'unbuffered clock net omitted'
 cases.append({'case':name,'input_database_sha256':sha(db),'layers':layers,'routed_nets':routed,
  'routed_net_names_sha256':hashlib.sha256('\n'.join(sorted(nets)).encode()).hexdigest(),
  'wirelength_um':int(re.search(r'Total wirelength: (\d+) um',text)[1]),
  'raw_clock_nets_present':sorted(clocks),'log_sha256':sha(out/'routing.log'),'guides_sha256':sha(out/'routes.guide')})
a,b=cases
assert a['routed_nets']==b['routed_nets'] and a['routed_net_names_sha256']==b['routed_net_names_sha256']
r={'scope':'Global-routing congestion comparison with PDN obstructions; no detailed routing, CTS or timing qualification',
 'cases':cases,'resource_change_percent':100*(b['layers']['Total']['resource']/a['layers']['Total']['resource']-1),
 'wirelength_change_percent':100*(b['wirelength_um']/a['wirelength_um']-1),
 'source_sha256':{f:sha(p/'verification'/f) for f in ['pdn_routing_screen.tcl','run_pdn_routing.sh','report_pdn_routing.py']},
 'limitations':['No STA clock definitions: eight unbuffered clock nets are routed as ordinary nets and explicitly checked present in guides. No clock tree, skew or latency qualification.','No timing-driven criticality, layer derating margin, detailed-route DRC, pin-access or antenna signoff.','Global capacity is a coarse model and zero overflow does not prove detailed routability.','Abstract digital-region pins, no analog macros, full-chip padframe or package feeds.','Power-grid current/EM and all previous setup/recovery failures remain open.']}
(p/'evidence/pdn-routing-comparison.json').write_text(json.dumps(r,indent=2)+'\n')
print('PDN_ROUTING_COMPARISON_PASS',r['resource_change_percent'],r['wirelength_change_percent'])
