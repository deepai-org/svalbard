"""Normative architecture; SVG is reproducible using only the standard library."""
from pathlib import Path
from html import escape
import json
import sys
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'system_model'))
from architecture_fast.rf_quality_budget import current_allocation
ARCH=json.loads((Path(__file__).resolve().parents[2]/'spec/analog-architecture.json').read_text())
GROUPS={
'Differential clock input / source select':['refpad','refinput','clockmux'],
'RF synthesis + local quadrature':['rfpll','quadrature'],
'Wired TX synthesis + phase control':['wirepll'],
'Input + LNA':['rfpad','lna'],
'I / Q mixers':['rxmix_i','rxmix_q'],
'LPF → main PGA':['rxfilter_i','rxfilter_q','pga_i','pga_q'],
'I / Q ADCs':['adc_i','adc_q'],
'RF driver + output pad':['rfdriver','rftxpad'],
'I / Q upmixers':['txmix_i','txmix_q','txsum'],
'Reconstruction LPF':['txfilter_i','txfilter_q'],
'I / Q DACs':['dac_i','dac_q'],
'Wired RX / shared USB pair':['wirepad','termination','rxlevel','ctle','rxselect','slicer','cdr','usbhs','usbfs'],
'Wired TX / specialized pad branches':['wiredtx','tmds','usbdrive','txpad','detect'],
'Shared bias / converter reference services':['bias','refbuf'],
'Clock, configuration and observation':['clocktree','aosc','monitor'],
'Supply / return distribution':['power'],
'SPI / reset / resource ownership':['digital'],
'Shared transport / short queues / GPIO PHY':['hostio'],
'EXTERNAL FPGA + BOARD • explicitly outside the die budget':['board']}
assert set(sum(GROUPS.values(),[]))==set(ARCH['blocks']), 'Diagram/inventory block mismatch'
# Path checks prove declared connectivity, not analog behavior or protocol compliance.
edges={(net['source'].split('.')[0],sink.split('.')[0]) for net in ARCH['nets'].values() for sink in net['sinks'] if net['kind'] not in ('supply','per_instance_numeric_control')}
for name,path in ARCH['functional_paths'].items():
 for source,dest in zip(path,path[1:]): assert (source,dest) in edges,(name,source,dest)
contract=json.loads((Path(__file__).resolve().parents[2]/'spec/contract.json').read_text())
capabilities=ARCH['capability_architecture_audit']['capabilities']
assert set(capabilities)==set(contract['generic_control_surface']['external_interface_requirements'])
for name,row in capabilities.items():
 assert all(path in ARCH['functional_paths'] for path in row['paths']),name
 assert all(block in ARCH['blocks'] for block in row['required_blocks']),name
 assert all(control in ARCH['control_fields'] for control in row['control_endpoints']),name

DRAWN=set()
# Validate the declared wiring before publishing either representation.
ENDPOINTS=Counter()
for name,net in ARCH['nets'].items():
 assert net['sinks'], f"Unloaded net: {name}"
 assert net.get('electrical'), f"Untyped net: {name}"
 for endpoint,direction in [(net['source'],'out')]+[(s,'in') for s in net['sinks']]:
  block,port=endpoint.split('.',1)
  owner=ARCH['blocks'][block]
  assert port in owner['outputs' if direction=='out' else 'inputs'], endpoint
  assert owner['ports'][port]['direction']==direction, endpoint
  assert owner['ports'][port]['net']==name, endpoint
  assert owner['ports'][port]['contract']==name, endpoint
  ENDPOINTS[endpoint]+=1
for block,owner in ARCH['blocks'].items():
 assert set(owner['ports'])==set(owner['inputs']+owner['outputs']), block
 for port in owner['ports']:
  assert ENDPOINTS[f'{block}.{port}']==1, f"Unconnected or multiply declared: {block}.{port}"
assert len(sum(GROUPS.values(),[]))==len(ARCH['blocks']), 'Duplicate diagram block'
def param(block,key): return ARCH['blocks'][block]['parameters'][key]
assert param('monitor','management_observation_clock_hz')==param('aosc','nominal_hz')
assert ARCH['nets']['RX_DETECT_INJECT']['source']=='detect.test_current'
assert ARCH['nets']['RX_DETECT_INJECT']['sinks']==['txpad.test_current']
assert 'detect' in ARCH['control_fields']['txpad.config']['fields']['branch']['values']
assert 'cdr.electrical_quiet' in ARCH['nets']['ELECTRICAL_QUIET']['sinks']
assert 'cdr.squelch' in ARCH['nets']['squelch']['sinks']
assert ARCH['nets']['cdr_loss']['sinks']==['monitor.cdr_loss']

controls=ARCH['control_fields']
assert set(controls)==set(ARCH['nets']['CONTROL']['sinks']), 'Unspecified control endpoint'
control_bits=0
for endpoint,definition in controls.items():
 assert definition['update'], endpoint
 for field,contract in definition['fields'].items():
  bits=contract['bits']; control_bits+=bits
  assert bits>0, (endpoint,field)
  if 'values' in contract:
   assert contract['default'] in contract['values'], (endpoint,field)
   assert len(contract['values'])<=2**bits, (endpoint,field)
  else:
   assert 0<=contract['minimum']<=contract['default']<=contract['maximum']<2**bits, (endpoint,field)
assert control_bits==ARCH['nets']['CONTROL']['electrical']['conductors']
for name,mode in ARCH['operating_modes'].items():
 assert set(mode['block_states'])==set(ARCH['blocks']), name
 outputs=mode['output_constraints']
 assert not (outputs['rf_output_enabled'] and (outputs['wire_tx_enabled'] or outputs['usb_drive_enabled'])), name
 assert not (outputs['wire_tx_enabled'] and outputs['usb_drive_enabled']), name
for leg in ['i','q']:
 sar=ARCH['blocks']['adc_'+leg]['parameters']
 assert sar['acquisition_s']+sar['decision_s']+sar['reset_s']<=1/sar['sample_rate_max_hz']+1e-18
assert param('usbfs','series_external_ohm')==0, 'FS-only board resistor must not load shared HS pad'
assert param('usbfs','drive_output_r_ohm')+param('usbdrive','switch_r_ohm')==param('usbfs','effective_output_r_ohm')
area={}
for name,block in ARCH['blocks'].items():
 allocation=block['resource_allocation']; group=allocation['area_group']
 area[group]=area.get(group,0)+allocation['area_ceiling_um2']
 assert set(allocation['current_budget_ma'])==set(ARCH['operating_modes']),name
assert area==ARCH['resource_totals']['area_used_um2']
for group,total in area.items():
 if group!='external': assert total<=ARCH['area_budget_um2'][group],group
for dac in ('dac_i','dac_q'):
 steering_floor_ma=1000*param(dac,'full_scale_current_a')
 for mode in ('rf_rx','rf_tx'):
  assert ARCH['blocks'][dac]['resource_allocation']['current_budget_ma'][mode]>=steering_floor_ma, 'Warm DAC steering current is underallocated'
assert sum(ARCH['resource_policy']['decoupling_pf'].values())==1000
assert sum(ARCH['resource_policy']['memory_bits'].values())<=ARCH['resource_policy']['memory_total_cap_bits']
assert ARCH['resource_policy']['memory_bits']['control_shadow_and_active']==2*control_bits
for mode in ARCH['operating_modes']:
 current=sum(b['resource_allocation']['current_budget_ma'][mode] for b in ARCH['blocks'].values())
 assert abs(current-ARCH['resource_totals']['current_ma'][mode])<1e-6
 branch=ARCH['resource_policy']['primary_current_case_by_mode'].get(mode)
 assert current_allocation(ARCH,mode,branch=branch)['meets_allocation'],mode
for rail in ['RF','WIRE','PLL','CONV','CORE','HOST']:
 assert any(s.startswith('monitor.') for s in ARCH['nets'][rail+'_VDD']['sinks']),rail



A=['''<svg xmlns="http://www.w3.org/2000/svg" width="1800" height="1590" viewBox="0 0 1800 1590" role="img" aria-labelledby="title desc"><title id="title">Svalbard normative transceiver architecture</title><desc id="desc">RF west, wired east, timing north, host south. 74 provider sites, 37 functional signals. RF and wired payload operation exclusive. External clock input is one differential REF_IN / REF_IN_N port. Physical performance remains unqualified.</desc><defs><marker id="a" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto-start-reverse"><path d="M0 0L8 4L0 8" fill="#355269"/></marker></defs><rect width="1800" height="1590" fill="white"/><g font-family="DejaVu Sans,sans-serif" fill="#172a3a">''']
def text(x,y,t,size=16,bold=False):
 A.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{600 if bold else 400}">{escape(t)}</text>')
def box(x,y,w,h,title,lines=(),fill='#f1f6fa'):
 members=GROUPS.get(title,[])
 DRAWN.update(members)
 A.append('<g data-blocks="'+escape(' '.join(members))+'">')
 A.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="5" fill="{fill}" stroke="#8096a6"/>')
 display={'RF driver + output pad':'RF driver / ESD','Shared bias / converter reference services':'Bias / converter references'}.get(title,title)
 text(x+12,y+25,display,min(17, (w-24)/(max(1,len(display))*0.61)),True)
 for i,l in enumerate(lines):text(x+12,y+49+i*21,l,14)
 A.append('</g>')
def wire(pts,clock=False,both=False):
 A.append('<polyline points="'+' '.join(f'{x},{y}' for x,y in pts)+'" fill="none" stroke="'+('#8655a2' if clock else '#355269')+'" stroke-width="2" '+('stroke-dasharray="6 4" ' if clock else '')+'marker-end="url(#a)" '+('marker-start="url(#a)"' if both else '')+'/>')
text(30,38,'SVALBARD / NORMATIVE ARCHITECTURE',28,True)
text(30,67,"Current architecture • review fixes selected; physical performance unqualified",17)
box(210,150,1380,970,'ONE GF180MCU DIE • RF OR WIRED PAYLOAD • 74 PROVIDER-COMPATIBLE SITES',(), '#fcfdfe')
text(230,203,'Functional paths; candidate pads: RF/REF west, wired east, H2D north, D2H/control south. Core budget: 12.92 mm².',14)
box(590,85,610,65,'REF_IN / REF_IN_N (2) • west-edge pair',('Alternate external reference / clock / RF LO; no simultaneous inputs',),'#fff6df')
wire([(1190,150),(1115,150),(1115,205),(1080,205),(1080,220)],True)
box(700,220,400,110,'Differential clock input / source select',('Two protected legs; RF-capable conditioning', 'HF bypass / divide; LF → ×10 video PLL', '50 Ω/leg; high-Z; HF 1 V / LF 0.5 V peak'))
box(245,220,405,110,'RF synthesis + local quadrature',('PFD / charge pump / loop filter / ring VCO', 'RC polyphase OR ÷2 quadrature; local buffers', 'Carrier → samples; RF host: carrier or H2D/2'))
box(1150,220,405,110,'Wired TX synthesis + phase control',('PFD / charge pump / filter / oscillator / divider', 'External timing or synthesis; flexible ×10 mode', 'Qualified divider reset + common word epoch'))
wire([(700,266),(650,266)],True);wire([(1100,266),(1150,266)],True)
text(250,370,'RF RX • differential I/Q branches',20,True)
box(20,412,170,80,'RF_RX P/N (2)',('Board preselection', 'matching / balun'),'#fff6df')
box(245,400,180,95,'Input + LNA',('Protection / bias', 'Selectable gain'))
box(460,400,180,95,'I / Q mixers',('LO-I / LO-Q', 'Separate branches'))
box(675,400,200,95,'LPF → main PGA',('Tunable poles / Q / zeros', 'Offset / common-mode'))
box(910,400,180,95,'I / Q ADCs',('10-bit SAR; 8 ENOB', '12-bit host words', 'Test: 0, ±VREF/4'))
for a,b in [(190,245),(425,460),(640,675),(875,910)]:wire([(a,455),(b,455)])
text(700,355,'LO-I / LO-Q → local RX and TX mixer ports',14)
wire([(550,385),(550,400)],True)
text(250,540,'RF TX • differential I/Q branches',20,True)
box(20,572,170,95,'RF_TX P/N (2)',('Board matching / filter', 'External PA as needed'),'#fff6df')
box(245,565,180,95,'RF driver + output pad',(f"Gain {param('rfdriver','nominal_gain'):g}; {param('rfdriver','bias_current_a')*1e3:g} mA bias", 'Summation → RF ESD'))
box(460,565,180,95,'I / Q upmixers',('LO-I / LO-Q', 'Local summation'))
box(675,565,200,95,'Reconstruction LPF',('Selectable cutoff / gain', 'Fifth-order Butterworth'))
box(910,565,180,95,'I / Q DACs',('Segmented 10-bit DAC', '12-bit host words'))
for a,b in [(245,190),(460,425),(675,640),(910,875)]:wire([(a,615),(b,615)])
wire([(550,550),(550,565)],True)
box(1140,385,410,120,'Wired RX / shared USB pair',('Protection / termination / DC level divider', 'CTLE or USB HS preamp → explicit 2:1 mux', '98 tracking samplers → phase-bank CDR → RX words', '8-phase burst sampling; FS/LS sensing / squelch'))
box(1610,405,175,100,'WIRE_RX P/N (2)',('USB D+ / D− alias', 'Bidirectional in USB'),'#fff6df')
wire([(1610,455),(1550,455)],both=True)
box(1140,550,410,130,'Wired TX / specialized pad branches',('TX words → serializer → main / postcursor driver', 'Paired detect-current injection; DC TMDS branch', 'USB HS + FS/LS drive / pulls → WIRE_RX pair', 'WIRE_TX high impedance during USB operation'))
box(1610,570,175,85,'WIRE_TX P/N (2)',('Serial / TMDS', 'Board termination'),'#fff6df')
wire([(1550,615),(1610,615)])
wire([(1515,550),(1570,550),(1570,485),(1550,485)])
wire([(1360,330),(1360,360),(1120,360),(1120,585),(1140,585)],True)
box(245,715,410,130,'Shared bias / converter reference services',('Startup / V-I bias; error amp + source/sink buffer', f"{param('refbuf','target_v'):g} V reference; {param('refbuf','reservoir_f')*1e12:g} pF reservoir; {param('refbuf','source_limit_a')*1e3:g} mA buffer", '10 µA master bias; 1.65 V common-mode', 'No universal GHz analog crossbar'),'#fff8e9')
box(690,715,400,130,'Clock, configuration and observation',('Carrier dividers → ADC/DAC and RF D2H clock', f"Independent {param('aosc','nominal_hz')/1e6:g} MHz management oscillator", 'Sticky loss / supply / reference supervision', 'Clock-source changes only while payload stopped'),'#f7f0fa')
box(1610,745,175,85,'PWR / GND',('18 fixed provider sites', 'One supply / one return'),'#fff6df')
wire([(1610,790),(1550,790)])
box(1140,715,410,130,'Supply / return distribution',('Common VDD/DVDD → local supply branches', 'CORE / HOST share source; common return', f"One 3.3 V source; {param('power','total_on_die_decoupling_f')*1e9:g} nF die decoupling", 'Host harmonics and package coupling remain risks'),'#fff8e9')
wire([(1000,495),(1105,495),(1105,885),(900,885),(900,910)])
wire([(870,910),(870,865),(1115,865),(1115,645),(1090,645)])
wire([(1200,505),(1128,505),(1128,880),(1250,880),(1250,910)])
wire([(1290,910),(1290,890),(1565,890),(1565,695),(1200,695),(1200,680)])
box(245,910,410,125,'SPI / reset / resource ownership',('Generic numeric controls; no chip protocol profiles', 'Atomic config; SPI-clock one-shot sync marker', '48-bit RF sample time / launch; FPGA calibration', 'Bulk capture / waveform memory stays on FPGA'))
box(690,910,860,125,'Shared transport / short queues / GPIO PHY',('RF I/Q or wired words ↔ packing / gearbox ↔ bounded CDC / elasticity ↔ SDR / DDR capture / launch', '1,024-bit ingress allocation; bulk payload and fault quarantine remain on FPGA', 'D2H: active clock or H2D-follow; direct bursts: 100 MHz SDR byte/control/parity', 'Wired line-rate sampling stays dedicated; RF converters are not serial-lane samplers'))
wire([(655,970),(690,970)],both=True)
box(245,1060,410,75,'SPI (4) + RESET_N (1)',('Independent configuration / recovery',),'#fff6df')
box(720,1060,370,75,'H2D[9:0] + H2D_CLK (11)',('North bank; FPGA → chip SDR / DDR',),'#fff6df')
box(1150,1060,400,75,'D2H[9:0] + D2H_CLK (11)',('South bank; chip → FPGA SDR / DDR',),'#fff6df')
wire([(450,1060),(450,1035)]);wire([(900,1060),(900,1035)]);wire([(1350,1035),(1350,1060)])
box(245,1190,1305,145,'EXTERNAL FPGA + BOARD • explicitly outside the die budget',('FPGA: protocols / modem / CRC / FEC; calibration / I-Q correction; resampling / TX FIR; periodic clock fitting / history.', 'RF: carrier ÷64/128/256/512 samples; hopping uses stable H2D/2 host clock. FPGA pays causal latency.', 'Recovery: actual protocol preambles / tracking; selectable filter settings trade clean-signal fidelity against blocker rejection.', 'Board: clean oscillator / LO, RF preselection / matching, optional PA, power / decoupling; specialized wired support as required.'),'#eaf3ff')
wire([(450,1190),(450,1135)],both=True);wire([(900,1190),(900,1135)]);wire([(1350,1135),(1350,1190)])
text(30,1380,'READING THE DIAGRAM',18,True)
text(30,1410,'Solid arrows: bundled payload / functional paths. Purple dashed arrows: timing. Local service fanout is named, not individually routed.',16)
text(30,1440,'37 functional signals + 18 fixed supply/return + 19 spare signal sites = 74. Supersedes the early approximate 50-total target.',16)
text(30,1470,'Multiple identical dies can supply HDMI/DVI data lanes; forwarded-clock interface and cross-die alignment remain board/FPGA obligations.',16)
text(30,1500,'Analog signal pads / custom frontends at compatible bond sites; standard GPIO signal circuitry is not required for RF / fast lanes.',16)
text(30,1530,'Circuit candidate sheets are exploratory detail, not additional required blocks. RF and wired exclusivity saves activity, not fabricated area.',16)
assert DRAWN==set(ARCH['blocks']), 'Inventory block omitted from rendered groups'
A.append('</g></svg>')
def publish(path,content):
 if '--check' in sys.argv:
  assert path.read_text()==content, f"Stale generated artifact: {path}"
 else:
  path.write_text(content)
publish(Path(__file__).with_name('transceiver-block-diagram.svg'),'\n'.join(A)+'\n')
doc=Path(__file__).resolve().parents[2]/'spec/block-diagram.md'
marker='<!-- BEGIN GENERATED ARCHITECTURE CONNECTIONS -->'
end='<!-- END GENERATED ARCHITECTURE CONNECTIONS -->'
rows=[marker,'## Complete declared connections','',
 'Generated from `analog-architecture.json`; schematic-level bundles, not physical routes. '+
 'CONTROL bundles the individually specified control_fields endpoints. Bidirectional pad '+
 'aliases describe the same physical nodes in different modes; they are not extra pins.', '',
 '| Net | Kind | Source | Destinations |','|---|---|---|---|']
for name,net in ARCH['nets'].items():
 rows.append(f"| `{name}` | {net['kind']} | `{net['source']}` | "+', '.join(f'`{s}`' for s in net['sinks'])+' |')
rows.extend(['','### Capability path audit','',
 'These are external architecture mappings, not on-chip protocol profiles or compliance verdicts. '+
 'The inventory records the associated control endpoints and external dependencies.', '',
 '| Intended capability | Connected paths |','|---|---|'])
for name,row in ARCH['capability_architecture_audit']['capabilities'].items():
 rows.append('| `'+name+'` | '+', '.join('`'+path+'`' for path in row['paths'])+' |')
rows.extend(['',end])
content=doc.read_text()
if marker in content:
 start=content.index(marker); stop=content.index(end,start)+len(end)
 content=content[:start]+'\n'.join(rows)+content[stop:]
else:
 content=content.rstrip()+'\n\n'+'\n'.join(rows)+'\n'
publish(doc,content)
print(f"Architecture coverage: {len(ARCH['blocks'])} blocks, {len(ARCH['nets'])} nets, {len(ENDPOINTS)} ports; generated artifacts consistent.")
