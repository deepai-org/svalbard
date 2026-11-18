# KLayout: LVS readiness of every cell in the skeleton: do the pins of the netlist (plan.json) exist as text labels in
# the GDS, on which layers, at which hierarchy depth.   kl.sh lvs/pin_audit.py   -> /run/lvs/pin_audit.json
import json, os, collections
import klayout.db as db
man = json.load(open('/run/skel/manifest.json')); plan = json.load(open('/run/skel/plan.json'))
pins = {b['master']: b['pins'] for b in plan['blocks']+plan['pads']}
ly = db.Layout(); ly.read('/run/skel/pt_chip_skel.gds')
out = {}
for cellname, master in sorted({(i['cell'], i['master']) for i in man['instances'] if i.get('cell')}):
    c = ly.cell(cellname)
    top_txt = collections.defaultdict(set); deep_txt = collections.defaultdict(set)
    for li in ly.layer_indexes():
        info = ly.get_info(li); key = f'{info.layer}/{info.datatype}'
        for s in c.shapes(li).each(db.Shapes.STexts): top_txt[s.text.string].add(key)
    want = pins.get(master) or []
    missing = [p for p in want if p not in top_txt]
    if missing:      # look below the top cell
        for li in ly.layer_indexes():
            info = ly.get_info(li); key = f'{info.layer}/{info.datatype}'
            it = c.begin_shapes_rec(li); it.shape_flags = db.Shapes.STexts
            while not it.at_end():
                if it.shape().text.string in missing: deep_txt[it.shape().text.string].add(key)
                it.next()
    lay = collections.Counter(k for p in want for k in top_txt.get(p, ()))
    out[cellname] = dict(master=master, pins=len(want), labelled_top=len(want)-len(missing), labelled_below=sorted(p for p in missing if p in deep_txt),
                         unlabelled=sorted(p for p in missing if p not in deep_txt), label_layers=dict(lay),
                         extra_labels=sorted(t for t in top_txt if t not in want)[:40], n_extra=len([t for t in top_txt if t not in want]))
os.makedirs('/run/lvs', exist_ok=True)
json.dump(out, open('/run/lvs/pin_audit.json', 'w'), indent=0)
ok = [k for k, v in out.items() if v['pins'] and not v['unlabelled'] and not v['labelled_below']]
print(f'{len(out)} cells: {len(ok)} with every netlist pin labelled in the top cell')
for k, v in out.items():
    if k not in ok: print(f" {k}: pins {v['pins']}, top {v['labelled_top']}, below {len(v['labelled_below'])}, none {len(v['unlabelled'])} {v['unlabelled'][:8]} layers {v['label_layers']} extra {v['n_extra']} {v['extra_labels'][:6]}")
print('label layers overall:', dict(collections.Counter(k for v in out.values() for k in v['label_layers'])))
