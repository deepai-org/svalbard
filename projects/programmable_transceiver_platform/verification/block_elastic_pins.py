import json,pathlib
out=pathlib.Path('/out');m=json.loads((out/'mapped.json').read_text())['modules']['pt_block_elastic']
bits=set()
for name,net in m['netnames'].items():
 if name.startswith('receive_buffer.mem['):bits.update(net['bits'])
assert len(bits)==168,len(bits)
pins=[];dbits=set();full=[]
for name,c in m['cells'].items():
 if '__dff' in c['type']:
  if set(c['connections'].get('Q',[])) & bits:
   pins.append(name+'/D');dbits.update(c['connections']['D'])
  if set(c['connections'].get('Q',[])) & set(m['netnames']['full']['bits']):full.append(name+'/Q')
assert len(pins)==168 and len(full)==1
# Reachability through combinational logic, stopping at all sequential cells.
reachable=set(m['ports']['rd_ready']['bits'])
while True:
 before=len(reachable)
 for c in m['cells'].values():
  if '__dff' in c['type'] or not c['type'].startswith('gf180'):continue
  inputs={b for port,bs in c['connections'].items() if c['port_directions'][port]=='input' for b in bs}
  if reachable & inputs:
   reachable.update(b for port,bs in c['connections'].items() if c['port_directions'][port]=='output' for b in bs)
 if len(reachable)==before:break
assert not reachable & dbits,'downstream ready reaches receiving data without a register'
(out/'pins.tcl').write_text('set capture_pins [get_pins {'+' '.join(pins)+'}]\nset full_pin [get_pins {'+' '.join(full)+'}]\n')
(out/'cone.json').write_text(json.dumps({'capture_bits':168,'capacity_registers':1,'rd_ready_to_capture_combinational_path':False})+'\n')
