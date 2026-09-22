import json,pathlib
m=json.loads(pathlib.Path('/out/mapped.json').read_text())['modules']['pt_block_fifo_capture']
bits=set(m['ports']['captured']['bits']); pins=[]
for name,c in m['cells'].items():
    if '__dff' in c['type'] and set(c['connections'].get('Q',[])) & bits:
        pins.append(name+'/D')
assert len(pins)==84
pathlib.Path('/out/capture-pins.tcl').write_text('set capture_pins [get_pins {'+' '.join(pins)+'}]\n')
rb=set(m['netnames']['fifo.storage.rb']['bits']); pointer=[]
for name,c in m['cells'].items():
    if '__dff' in c['type'] and set(c['connections'].get('Q',[])) & rb:
        pointer.append(name+'/Q')
assert len(pointer)==4
with pathlib.Path('/out/capture-pins.tcl').open('a') as f:
    f.write('set pointer_pins [get_pins {'+' '.join(pointer)+'}]\n')
