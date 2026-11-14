# Die-fit study: M4/M5/MIM-free area inside STAGED outlines (same method as scratch/area-pass-4/m45free.py).
# Read-only on all inputs. Run in the pinned KLayout image, one job, one thread.
import klayout.db as db, json
S='/scratch/'; P='/proj/analog/'
FILES={
 'pt_adc_i':S+'converters-ap4/meas/adc_i.gds', 'pt_dac_i':S+'converters-ap4/meas/dac_i.gds',
 'pt_lo_mmd':S+'lo-ap4/run_lo_mmd_ap4/lo_mmd/stage/lo_mmd.gds', 'pt_lo_mmd_qdum':S+'lo-ap4/run_lo_mmd_qdum_ap4/lo_mmd_qdum/stage/lo_mmd_qdum.gds',
 'pt_lo_obs':S+'lo-ap4/run_lo_obs_ap4/lo_obs/stage/lo_obs.gds', 'pt_clk_obs16':S+'lo-ap4/run_clk_obs16_ap4/clk_obs16/stage/clk_obs16.gds',
 'pt_lo_ext':S+'lo-ap4/cand/run2/lo_ext/stage/lo_ext.gds', 'pt_wrx_cap':S+'wired_rx/r7cap/r7c/cap/top/pt_wrx_cap.gds',
 'pt_cdr':P+'wired_rx/generated/cdr.gds', 'pad_hspad':S+'pads-core/hspad/b2/pad_hspad.gds',
 'pt_lna':P+'rf_rx/generated/lna.gds', 'pt_rxmix_i':P+'rf_rx/generated/rxmix_i.gds',
 # controls: published cells that area-pass-4 measured (must reproduce m45free.json)
 'CTRL_pt_bbfilter_i':P+'rf_rx/generated/bbfilter_i.gds', 'CTRL_pt_lo_lf':P+'timing/generated/lo_lf.gds',
}
out={}
for name,f in FILES.items():
  try:
    ly=db.Layout(); ly.read(f)
    tops=[c for c in ly.top_cells()]
    t=max(tops,key=lambda c:c.bbox().area())
    bx=t.bbox(); R=db.Region(bx); used=db.Region()
    for lt in [(46,0),(81,0),(75,0),(41,0)]:
      i=ly.find_layer(*lt)
      if i is not None: used+=db.Region(t.begin_shapes_rec(i))
    used=used.merged().sized(3000)
    free=(R-used); big=free.sized(-10000).sized(10000)&free
    dbu=ly.dbu
    out[name]=dict(file=f,top=t.name,w=bx.width()*dbu,h=bx.height()*dbu,outline=bx.area()*dbu*dbu,free_m45=free.area()*dbu*dbu,free_m45_20um=big.area()*dbu*dbu)
  except Exception as e:
    out[name]=dict(file=f,error=str(e))
  print(name,out[name],flush=True)
json.dump(out,open('/work/m45free_staged.json','w'),indent=1)
