# Layout negative control for device-level LVS: insert into the COMPLETE
# routed GDS the same Metal3 VDD-VSS bridge the routing LVS uses.
import pya, json
from pathlib import Path
lay = pya.Layout(); lay.read('/work/pt_core_bias_routed.gds')
top = lay.cell('pt_core_bias')
w = json.loads(Path('/work/routed.json').read_text())['nets']
a = next(x for x in w['VDD']['shapes'] if x['layer'] == 'Metal3' and x['kind'] == 'segment')
b = min((x for x in w['VSS']['shapes'] if x['layer'] == 'Metal3' and x['kind'] == 'segment'),
        key=lambda x: abs(x['box_dbu'][0]-a['box_dbu'][0])+abs(x['box_dbu'][1]-a['box_dbu'][1]))
box = [min(a['box_dbu'][0], b['box_dbu'][0]), min(a['box_dbu'][1], b['box_dbu'][1]),
       max(a['box_dbu'][2], b['box_dbu'][2]), max(a['box_dbu'][3], b['box_dbu'][3])]
# routed.json boxes are in DEF units (2000/um); the GDS uses 1000/um. Metal3 = GDS 42/0.
top.shapes(lay.layer(42, 0)).insert(pya.Box(*[v//2 for v in box]))
Path('/work/neg').mkdir(exist_ok=True)
lay.write('/work/neg/pt_core_bias_routed.gds')
print('DEVICE_LVS_NEGATIVE_BRIDGE_DBU', box)
