"""Expand actual ring device terminals; do not infer noise PSD from topology."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';S=P/'analog/pll/ring_vco_split.spice'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
s=S.read_text();delay=s.split('.subckt pt_split_delay ',1)[1].split('.ends pt_split_delay',1)[0];ports=delay.splitlines()[0].split(' params:')[0].split();body=delay.splitlines()[1:]
ring=s.split('.subckt pt_split_ring ',1)[1].split('.ends pt_split_ring',1)[0]
rows=[]
for line in ring.splitlines()[1:]:
 if not line.startswith(('X0 ','X1 ','X2 ','XBUF ')):continue
 words=line.split();stage=words[0];assert words[9]=='pt_split_delay';mapping=dict(zip(ports,words[1:9]));assert len(mapping)==8
 def node(n):
  n=mapping.get(n,stage+'.'+n)
  return 'XRX.XVCO.'+n if n not in ('VCTRL','REGEN','VDD','VSS') else {'VCTRL':'CTRL','REGEN':'REGEN','VDD':'PLLVDD','VSS':'0'}[n]
 for device in body:
  if not device.startswith('X'):continue
  w=device.split();isfet=w[5]=='nfet_03v3' if len(w)>5 else False
  if isfet:
   terminals=dict(zip(('drain','gate','source','bulk'),map(node,w[1:5])))
   role='capacitor' if w[0] in ('XCP','XCN') else 'tail' if w[0] in ('XMT','XMLT') else 'regenerative_pair' if w[0] in ('XLP','XLN') else 'input_pair'
   perturbation=None if role=='capacitor' else [terminals['drain'],terminals['source']]
  else:
   assert w[4]=='ppolyf_u';terminals=dict(zip(('a','b','substrate'),map(node,w[1:4])));role='load_resistor';perturbation=[terminals['a'],terminals['b']]
  rows.append(dict(instance='XRX.XVCO.'+stage+'.'+w[0],inside_loop=stage!='XBUF',role=role,terminals=terminals,candidate_current_injection_nodes=perturbation))
assert len(rows)==40
channel=next(x for x in rows if x['instance']=='XRX.XVCO.X0.XMP')
m=R/'scratch/transceiver-vco-channel-kick/manifest.json';manifest=json.loads(m.read_text());assert manifest['pulse_nodes']==channel['candidate_current_injection_nodes']
assert manifest['source_sha256_before']['/screen/pll/ring_vco_split.spice']==sha(S)
out=dict(completed=True,source_sha256=sha(S),pulse_manifest_sha256=sha(m),devices=rows,counts=dict(loop_devices=sum(x['inside_loop'] for x in rows),buffer_devices=sum(not x['inside_loop'] for x in rows),mos_capacitors=sum(x['role']=='capacitor' for x in rows),load_resistors=sum(x['role']=='load_resistor' for x in rows)),limitations=['Topology inventory only: not a complete independent-noise-source expansion of PDK subcircuits.', 'Channel-terminal injection alone omits gate, body, resistor and correlated model sources; MOS capacitors require separate model inspection.', 'One pulse phase and magnitude cannot provide cycle weighting, linearity or integrated phase noise.', 'Supply, control, bias, output loading and PLL feedback noise remain outside this local inventory.', 'PDK noise options and selected corners do not bound undisclosed silicon variation.'])
(P/'evidence/ring-noise-ports.json').write_text(json.dumps(out,indent=2)+'\n');print(out['counts']);print('channel pulse endpoints match actual transistor:',channel['candidate_current_injection_nodes'])
