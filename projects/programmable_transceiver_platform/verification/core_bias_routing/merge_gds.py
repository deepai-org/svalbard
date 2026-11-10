# KLayout stage: write the routed core-bias GDS from the exported geometry
# (routes, vias, boundary pins + labels) on top of the qualified placement,
# then prove every leaf master is unchanged (zero XOR on every layer).
import pya, json, re, hashlib
import xml.etree.ElementTree as ET
from pathlib import Path

base = Path('/input'); out = Path('/work')
wires = json.loads((out/'routed.json').read_text()); manifest = json.loads((base/'pin-inputs.json').read_text())
layers = {}
for e in ET.parse('/foss/pdks/gf180mcuD/libs.tech/klayout/tech/gf180mcu.lyp').iter('properties'):
    m = re.fullmatch(r'((?:Metal[1-5])|(?:Via[1-4]))\s+(\d+)/(\d+)@\d+', e.findtext('source') or '')
    if m:
        layers[m[1]] = (int(m[2]), int(m[3]))
assert len(layers) == 9, layers
layout = pya.Layout(); layout.read(str(base/'pt_core_bias_placement.gds'))
top = layout.cell('pt_core_bias_placement'); assert top is not None
top.name = 'pt_core_bias'
scale = wires['dbu_per_um']*layout.dbu; assert scale == 2, scale
count = 0
for name, net in wires['nets'].items():
    for shape in net['shapes']:
        c = shape['box_dbu']; assert all(v % 2 == 0 for v in c), (name, c)
        top.shapes(layout.layer(*layers[shape['layer']])).insert(pya.Box(*[v//2 for v in c])); count += 1
    for pin in net['pins']:
        c = pin['box_dbu']; assert all(v % 2 == 0 for v in c)
        box = pya.Box(*[v//2 for v in c]); ln, dt = layers[pin['layer']]
        top.shapes(layout.layer(ln, dt)).insert(box)
        top.shapes(layout.layer(ln, 10)).insert(pya.Text(pin['name'], pya.Trans(box.center())))
options = pya.SaveLayoutOptions(); options.select_cell(top.cell_index()); options.write_context_info = False
layout.write(str(out/'pt_core_bias_routed.gds'), options)
check = pya.Layout(); check.read(str(out/'pt_core_bias_routed.gds'))
xor = {}
for item in manifest['cells']:
    source = pya.Layout(); source.read(str(base/item['gds'])); a = source.cell(item['cell']); b = check.cell(item['cell']); assert b is not None
    for layer in {(l.get_info(i).layer, l.get_info(i).datatype) for l in [source, check] for i in l.layer_indexes()}:
        ai = source.find_layer(*layer); bi = check.find_layer(*layer)
        ar = pya.Region(a.begin_shapes_rec(ai)) if ai is not None else pya.Region()
        br = pya.Region(b.begin_shapes_rec(bi)) if bi is not None else pya.Region()
        assert (ar ^ br).is_empty(), (item['cell'], layer)
    xor[item['cell']] = 0
# Block-unique subcell names (after the master XOR above, which matches by name): the chip GDS merges
# by name, and bringup_and / the as_sc std cells here differ from same-named cells in other blocks.
renamed = 0
for ci in check.cell(top.name).called_cells():
    c = check.cell(ci)
    if not c.name.startswith('pt_core_bias__'):
        c.name = 'pt_core_bias__' + c.name; renamed += 1
options = pya.SaveLayoutOptions(); options.select_cell(check.cell(top.name).cell_index()); options.write_context_info = False
check.write(str(out/'pt_core_bias_routed.gds'), options)
result = dict(renamed_subcells=renamed, status='routed_gds', nets=len(wires['nets']), route_shapes=count, master_xor=xor,
              gds_sha256=hashlib.sha256((out/'pt_core_bias_routed.gds').read_bytes()).hexdigest(), layer_map=layers)
(out/'gds-report.json').write_text(json.dumps(result, indent=2)+'\n'); print(json.dumps(result))
