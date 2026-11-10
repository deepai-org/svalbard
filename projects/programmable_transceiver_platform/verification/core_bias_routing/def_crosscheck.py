# KLayout stage: validate the geometry export (including non-default-rule
# widths, tapers, patches and special-net vias) against KLayout's own LEF/DEF
# reader of the router's DEF. Top-level routing metal and cuts must XOR to zero.
import pya, json, glob, re
from pathlib import Path

work = Path('/work')
opt = pya.LoadLayoutOptions(); cfg = opt.lefdef_config
cfg.lef_files = [str(work/'tech.lef')] + sorted(glob.glob(str(work/'precise'/'*.lef')))
cfg.read_lef_with_def = False
cfg.dbu = 0.0005  # DEF UNITS 2000
cfg.produce_cell_outlines = False; cfg.produce_placement_blockages = False; cfg.produce_regions = False
cfg.produce_obstructions = False; cfg.produce_blockages = False
cfg.macro_resolution_mode = 1  # LEF abstracts only; masters compared elsewhere
d = pya.Layout(); d.read(str(work/'routed.def'), opt)
dtop = d.top_cell()
masters = {c['cell'] for c in json.loads(Path('/input/pin-inputs.json').read_text())['cells']}
g = pya.Layout(); g.read(str(work/'pt_core_bias_routed.gds')); gtop = g.cell('pt_core_bias')
gds_map = json.loads((work/'gds-report.json').read_text())['layer_map']
scale = g.dbu/d.dbu
result = {}; ok = True
for name, (ln, dt) in gds_map.items():
    dr = pya.Region()
    for i in d.layer_indexes():
        info = d.get_info(i)
        base = re.split(r'[.\s]', info.name or '')[0]
        if base == name and 'LABEL' not in (info.name or '').upper():
            # top-level routing plus via cells; leaf-master abstracts excluded
            it = dtop.begin_shapes_rec(i)
            for c in d.each_cell():
                if c.name in masters:
                    it.unselect_cells([c.cell_index()])
            dr.insert(it)
    gi = g.find_layer(ln, dt)
    gr = pya.Region(gtop.shapes(gi)) if gi is not None else pya.Region()
    gr = gr.transformed(pya.ICplxTrans(scale)) if scale != 1 else gr
    a, b = dr.merged(), gr.merged()
    a.merged_semantics = b.merged_semantics = True
    x = (a - b) + (b - a)
    result[name] = dict(def_area=a.area(), gds_area=b.area(), def_minus_gds=(a-b).area(), gds_minus_def=(b-a).area(), xor_polygons=x.count())
    # Built-in control: the same comparison against a 0.1 um shifted copy
    # must report a difference, or the check is vacuous.
    shifted = b.moved(round(.1/g.dbu*scale), 0)
    control = not ((a - shifted) + (shifted - a)).is_empty()
    result[name]['shift_control_detected'] = control
    ok &= x.is_empty() and not a.is_empty() and control
(work/'def-crosscheck.json').write_text(json.dumps(dict(status='pass' if ok else 'fail', layers=result,
    scope='KLayout LEF/DEF reading of routed.def vs exported routed GDS, top-level routing and pins.'), indent=2)+'\n')
print('DEF_CROSSCHECK', 'pass' if ok else 'fail', result)
