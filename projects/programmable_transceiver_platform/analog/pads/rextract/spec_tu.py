#!/usr/bin/env python3
"""netres spec for the 50 TU nets (switch drain -> resistor head) of pad_hspad; run in the image (needs klayout).
spec_tu.py <leg.gds> <leg_top> > spec.json     seeds = the leg's TUi labels (Metal3) mapped into both leg instances."""
import sys, json, klayout.db as k
l = k.Layout(); l.read(sys.argv[1]); t = l.top_cell(); ltop = float(sys.argv[2]); YP, YN, X = 594.75 - ltop, 636.75 + ltop, 340.
nets = []
for li in l.layer_indexes():
    if l.get_info(li).layer != 42: continue
    for s in t.each_shape(li):
        if s.is_text() and s.text_string.startswith('TU'):
            x, y = s.dtext.x, s.dtext.y
            for leg, yy in (('P', YP + y), ('N', YN - y)):
                nets.append(dict(name=f'{s.text_string}_{leg}', seed=['M3', X + x, yy], max_step=0.2, terminals=[dict(auto_contacts='c')], groups=dict(a=dict(members=['c0']), b=dict(members=['c1'])), pairs=[['a', 'b']]))
nets.sort(key=lambda n: (n['name'][-1], int(n['name'][2:-2])))
print(json.dumps(dict(nets=nets)))
