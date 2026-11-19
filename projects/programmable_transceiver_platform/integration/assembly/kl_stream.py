# Stage `stream` (tool image, KLayout python):  tool.sh <chip> python3 /asm/kl_stream.py
# The router's wiring (/run/route/routed.def: wires and vias only, read with the PDK layer map) is merged into
# /run/placed.gds -> /run/chip/pt_chip_top.gds (top cell pt_chip_top), the assembled routed chip that the checks read from
# disk. Block and pad macros of the DEF are dropped (the placed GDS holds the real cells).
import glob, json, os
import klayout.db as db
TLEF = '/pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/techlef/gf180mcu_fd_sc_mcu7t5v0__nom.tlef'
MAP = '/pdk/gf180mcuD/libs.tech/klayout/tech/gf180mcu.map'
DEF = os.environ.get('DEF', '/run/route/routed.def')
opt = db.LoadLayoutOptions(); cfg = opt.lefdef_config
cfg.map_file = MAP; cfg.read_lef_with_def = False
cfg.lef_files = [TLEF]+sorted(glob.glob('/run/lef/*.lef'))
cfg.produce_net_names = False; cfg.produce_pin_names = False; cfg.produce_inst_names = False
cfg.produce_cell_outlines = False; cfg.produce_regions = False; cfg.produce_blockages = False; cfg.produce_obstructions = False
cfg.produce_labels = False
cfg.macro_resolution_mode = 1
w = db.Layout(); w.read(DEF, opt); wt = w.top_cell()
macros = set()
for f in cfg.lef_files[1:]:
    for line in open(f):
        if line.startswith('MACRO '): macros.add(line.split()[1])
drop = 0
for i in list(wt.each_inst()):
    if i.cell.name in macros or i.cell.name.split('$')[0] in macros: i.delete(); drop += 1
for c in [c for c in w.top_cells() if c.name != wt.name]: w.prune_cell(c.cell_index(), -1)
ly = db.Layout(); ly.read('/run/placed.gds'); top = ly.cell('pt_chip_top')
wc = ly.create_cell('pt_top_wiring')
wc.copy_tree(wt)
top.insert(db.CellInstArray(wc.cell_index(), db.Trans()))
os.makedirs('/run/chip', exist_ok=True)
ly.write('/run/chip/pt_chip_top.gds')
# manifest for the sign-off flows (integration/signoff: keep-outs, DRC attribution, LVS by name)
PL = json.load(open('/run/place.json')); PADS = json.load(open('/run/pads.json'))
man = dict(top='pt_chip_top', instances=[])
for n, b in PL['blocks'].items():
    man['instances'].append(dict(name=n, master=b['master'], cell=b['master'], trans=b['trans'], kind=b['kind'], bbox=b['bbox'], in_conn=b['in_conn']))
for n, v in PADS['pads'].items():
    man['instances'].append(dict(name=n, master=v['master'], cell=v['master'], trans=v['trans'], kind='published', bbox=v['bbox'], in_conn=True))
json.dump(man, open('/run/chip/manifest.json', 'w'), indent=0)
owner = {}
for i in top.each_inst():
    c = i.cell
    for ci in [c.cell_index()]+list(c.called_cells()): owner.setdefault(ly.cell(ci).name, set()).add(c.name)
json.dump({k: sorted(v) for k, v in owner.items()}, open('/run/chip/cell_owner.json', 'w'))
stat = {f'{ly.get_info(li)}': db.Region(wc.begin_shapes_rec(li)).count() for li in ly.layer_indexes() if not db.Region(wc.begin_shapes_rec(li)).is_empty()}
json.dump(dict(def_file=DEF, macro_instances_dropped=drop, wiring_shapes=stat), open('/run/chip/stream.json', 'w'), indent=0)
print('dropped', drop, 'macro instances; wiring shapes per layer', stat)
