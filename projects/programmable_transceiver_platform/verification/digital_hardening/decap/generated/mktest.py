import klayout.db as db
ly=db.Layout(); ly.read('/w/pt_decap50.gds')
lib=db.Layout(); lib.read('/foss/pdks/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/gds/gf180mcu_fd_sc_mcu7t5v0.gds')
top=ly.create_cell('pt_decap50_test')
def get(name):
    if ly.has_cell(name): return ly.cell(name)
    src=lib.cell(name); dst=ly.create_cell(name); dst.copy_tree(src); return dst
row=['pt_decap50_64','pt_decap50_32','pt_decap50_16','pt_decap50_8','gf180mcu_fd_sc_mcu7t5v0__nand2_1','pt_decap50_4','gf180mcu_fd_sc_mcu7t5v0__fillcap_8','pt_decap50_16','gf180mcu_fd_sc_mcu7t5v0__dffrnq_1','pt_decap50_8','gf180mcu_fd_sc_mcu7t5v0__filltie','pt_decap50_4']
for r in range(3):
    x=0
    for n in (row if r%2==0 else list(reversed(row))):
        c=get(n); w=c.bbox().width() if not n.startswith('pt_') else c.bbox().width()
        # use the PR boundary width (layer 0/0)
        bl=ly.layer(0,0); pw=c.dbbox_per_layer(bl).width() if hasattr(c,'dbbox_per_layer') else None
        wb=int(round(c.bbox_per_layer(bl).width())) if not c.bbox_per_layer(bl).empty() else w
        if r%2==0: t=db.Trans(0,False,x,r*3920)
        else: t=db.Trans(0,True,x,(r+1)*3920)
        top.insert(db.CellInstArray(c.cell_index(),t))
        x+=wb
ly.write('/w/pt_decap50_test.gds')
print('ok', top.bbox())
