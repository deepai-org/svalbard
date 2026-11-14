# Off-chip passives pass: passive-device area per block, measured on layout layers (read-only).
# Layers (GF180MCU): MIM top plate FuseTop 75/0, RES_MK 110/5, MOS_CAP_MK 166/5, IND_MK 151/5.
# Run in the pinned KLayout image, one job, one thread. Output: passive_area.csv
import klayout.db as db, glob, os, csv
P='/proj/analog/'
files=[]
for pat in ['timing/generated/*.gds','timing/generated/lcvco/*.gds','rf_rx/generated/*.gds','rf_tx/generated/*.gds',
  'wired_rx/generated/*.gds','wired_tx/generated/*.gds','converters/generated/*.gds','pll_vreg/generated/*.gds',
  'characterization/generated/*.gds','decap/generated/*.gds','island_support/generated/isw/*.gds',
  'core_support/*/*.gds','core_support/*/*/*.gds','bringup_control/generated/*.gds',
  'pads/generated/stress-safe-families/*/combined.gds','pads/generated/stress-safe-families/*/pad.gds',
  'pads/generated/stress-safe-families/wired-receive-hs/pad_hspad.gds',
  'pads/generated/termination-buffer-candidate/compact-array/buffer_compensated_flat.gds',
  'pads/generated/steering-buffer-compact/*.gds','pads/generated/transmit-control-candidate/tx_mode_interlock_flat.gds']:
    files+=sorted(glob.glob(P+pat))
L={'mim':(75,0),'res_mk':(110,5),'moscap_mk':(166,5),'ind_mk':(151,5)}
rows=[]
for f in files:
    try:
        ly=db.Layout(); ly.read(f)
        t=max(ly.top_cells(),key=lambda c:c.bbox().area()); bx=t.bbox(); u=ly.dbu*ly.dbu
        r=dict(file=f.replace(P,''),top=t.name,w_um=round(bx.width()*ly.dbu,2),h_um=round(bx.height()*ly.dbu,2),bbox_um2=round(bx.area()*u))
        for k,lt in L.items():
            i=ly.find_layer(*lt)
            r[k+'_um2']=round(db.Region(t.begin_shapes_rec(i)).merged().area()*u) if i is not None else 0
        r['passive_um2']=r['mim_um2']+r['res_mk_um2']+r['moscap_mk_um2']+r['ind_mk_um2']
        r['passive_frac']=round(r['passive_um2']/max(1,r['bbox_um2']),3)
        rows.append(r)
    except Exception as e:
        rows.append(dict(file=f.replace(P,''),top='ERROR '+str(e)[:60]))
keys=['file','top','w_um','h_um','bbox_um2','mim_um2','res_mk_um2','moscap_mk_um2','ind_mk_um2','passive_um2','passive_frac']
with open('/out/passive_area.csv','w',newline='') as fh:
    w=csv.DictWriter(fh,fieldnames=keys); w.writeheader()
    for r in rows: w.writerow(r)
print(len(rows),'files')
