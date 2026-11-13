# Replica of the placement/size assertions of the live precheck's KLayout.GenerateID stage (scripts/klayout/generate_id.py,
# --cob). The stage itself needs the python `qrcode` module (absent from the project images); this runs only its checks.
#   klayout -b -r id_check.py -rd gds=top.gds
import klayout.db as pya, json
ly = pya.Layout(); ly.read(gds)
top = ly.top_cell(); W, H = top.dbbox().width(), top.dbbox().height()
exp = {'gf180mcu_ws_ip__qrcode_id': (26, 26, 168.8, 168.8), 'gf180mcu_ws_ip__shuttle_id': (26, 175.6, 85.5, 371.1),
       'gf180mcu_ws_ip__project_id': (175.6, 26, 371.1, 85.5), 'gf180mcu_ws_ip__marker': (W-36-245, H-36-245, W-36, H-36)}
res = {}
for name, c in exp.items():
    if not ly.has_cell(name):
        res[name] = 'MISSING'; continue
    cell = ly.cell(name)
    insts = [it.child_inst() for it in cell.each_parent_inst()]
    bb = [str(i.dbbox()) for i in insts]
    ok = len(insts) == 1 and insts[0].dbbox() == pya.DBox(*c)
    parent = [ly.cell(it.parent_cell_index()).name for it in cell.each_parent_inst()]
    res[name] = dict(ok=ok, instances=len(insts), bbox=bb, expected=str(pya.DBox(*c)), parent=parent, cell_bbox=str(cell.dbbox()))
print(json.dumps(res, indent=1))
