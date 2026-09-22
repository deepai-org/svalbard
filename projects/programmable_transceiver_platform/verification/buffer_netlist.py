"""Bounded-fanout, unplaced buffering experiment; not a physical reset/clock tree."""
import copy
import hashlib
import json
from pathlib import Path
import sys

source, destination = map(Path, sys.argv[1:3])
original=json.loads(source.read_text())
design=copy.deepcopy(original)
module=design['modules']['pt_digital']
cells=module['cells']
clock_bits={b for name,port in module['ports'].items() if name.endswith('_clk') or name=='host_sclk' for b in port['bits']}
loads={}
for name,cell in cells.items():
    for port,bits in cell['connections'].items():
        if cell.get('port_directions',{}).get(port)=='input':
            for index,bit in enumerate(bits):
                if isinstance(bit,int) and bit not in clock_bits:
                    loads.setdefault(bit,[]).append((name,port,index))
next_bit=max(b for cell in cells.values() for bits in cell['connections'].values() for b in bits if isinstance(b,int))+1
inserted={}
buffer_type='gf180mcu_fd_sc_mcu7t5v0__buf_4'
limit=16

def branch(root, sinks):
    global next_bit
    if len(sinks)<=limit:
        for name,port,index in sinks:cells[name]['connections'][port][index]=root
        return
    parents=[]
    for start in range(0,len(sinks),limit):
        name=f'pt_distribution_{len(inserted)}'
        bit=next_bit;next_bit+=1
        cells[name]={'hide_name':0,'type':buffer_type,'parameters':{},'attributes':{},
                     'port_directions':{'I':'input','Z':'output'},'connections':{'I':[root],'Z':[bit]}}
        inserted[name]=bit
        module['netnames'][name+'_out']={'hide_name':0,'bits':[bit],'attributes':{}}
        for sink,port,index in sinks[start:start+limit]:cells[sink]['connections'][port][index]=bit
        parents.append((name,'I',0))
    branch(root,parents)

for bit,sinks in loads.items():
    if len(sinks)>limit:branch(bit,sinks)
# Independent structural invariant: collapsing every inserted identity buffer must
# restore every original cell connection, and all original ports/cell types persist.
parent={bit:cells[name]['connections']['I'][0] for name,bit in inserted.items()}
def collapse(bit):
    seen=set()
    while bit in parent:
        assert bit not in seen,'buffer cycle'
        seen.add(bit);bit=parent[bit]
    return bit
for name,old in original['modules']['pt_digital']['cells'].items():
    new=cells[name]
    assert new['type']==old['type']
    for port,bits in old['connections'].items():
        assert [collapse(b) for b in new['connections'][port]]==bits,(name,port)
assert module['ports']==original['modules']['pt_digital']['ports']
remaining={}
for cell in cells.values():
    for port,bits in cell['connections'].items():
        if cell.get('port_directions',{}).get(port)=='input':
            for bit in bits:
                if isinstance(bit,int) and bit not in clock_bits:remaining[bit]=remaining.get(bit,0)+1
assert max(remaining.values())<=limit
report={'scope':'Identity-buffer netlist experiment, no placement/wire parasitics or clock tree',
        'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'buffer_type':buffer_type,'inserted_buffers':len(inserted),'fanout_limit':limit,
        'added_cell_area_um2':len(inserted)*float(design['modules'][buffer_type]['attributes']['area']),
        'connection_collapse_check':'pass for every original cell port',
        'maximum_nonclock_input_pin_fanout':max(remaining.values()),
        'limitations':['Pin-count cap does not guarantee capacitance or slew limits.',
                       'Grouping follows netlist order, not physical distance.',
                       'Clocks remain ideal; reset recovery/removal and skew are not closed.',
                       'No switching-power or wire-area estimate.']}
destination.write_text(json.dumps(design))
destination.with_suffix('.report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
