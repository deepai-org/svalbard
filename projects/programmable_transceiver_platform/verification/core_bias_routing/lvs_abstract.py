# KLayout stage for routing LVS: replace every leaf master in a copy of the
# routed GDS by a black box holding only its pin conductors (each audited pin
# rectangle grown to the full master polygon it belongs to on that layer)
# with port labels (layer/10). Masters' devices are excluded on purpose:
# their device-level LVS is per-master; this checks the 152 routed nets.
import pya, json
from pathlib import Path
base = Path('/input')
audit = json.loads((base/'pin-audit.json').read_text()); layers = audit['pdk_layers']
masters = [c['cell'] for c in json.loads((base/'pin-inputs.json').read_text())['cells']]
lay = pya.Layout(); lay.read('/work/pt_core_bias_routed.gds')
count = 0
for name in masters:
    cell = lay.cell(name); assert cell is not None, name
    keep = []
    for pin in audit['pin_details']:
        if pin['cell'] != name:
            continue
        for s in pin['shapes']:
            ln, dt = layers[s['layer']]; li = lay.find_layer(ln, dt)
            box = pya.Box(*s['box_dbu'])
            metal = pya.Region(cell.begin_shapes_rec(li)).merged() if li is not None else pya.Region()
            keep.append((ln, dt, metal.interacting(pya.Region(box)) + pya.Region(box), pin['pin'], box.center()))
    cell.clear()
    for ln, dt, region, pname, at in keep:
        cell.shapes(lay.layer(ln, dt)).insert(region)
        cell.shapes(lay.layer(ln, 10)).insert(pya.Text(pname, pya.Trans(at))); count += 1
top = lay.cell('pt_core_bias')
opt = pya.SaveLayoutOptions(); opt.select_cell(top.cell_index()); opt.write_context_info = False
lay.write('/work/lvs/pt_core_bias.gds', opt)
# Negative control layout: one Metal3 bridge between the nearest VDD and VSS
# Metal3 route segments. LVS must reject it.
w = json.loads(Path('/work/routed.json').read_text())['nets']
a = next(x for x in w['VDD']['shapes'] if x['layer'] == 'Metal3' and x['kind'] == 'segment')
b = min((x for x in w['VSS']['shapes'] if x['layer'] == 'Metal3' and x['kind'] == 'segment'),
        key=lambda x: abs(x['box_dbu'][0]-a['box_dbu'][0])+abs(x['box_dbu'][1]-a['box_dbu'][1]))
box = [min(a['box_dbu'][0], b['box_dbu'][0]), min(a['box_dbu'][1], b['box_dbu'][1]),
       max(a['box_dbu'][2], b['box_dbu'][2]), max(a['box_dbu'][3], b['box_dbu'][3])]
top.shapes(lay.layer(*layers['Metal3'])).insert(pya.Box(*[v//2 for v in box]))
lay.write('/work/lvs/neg/pt_core_bias.gds', opt)
print('LVS_NEGATIVE_BRIDGE_DBU', box)
print('LVS_ABSTRACT', len(masters), 'masters', count, 'pin shapes')
