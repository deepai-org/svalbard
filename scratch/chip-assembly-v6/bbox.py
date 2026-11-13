import klayout.db as db, json, glob
P='/repo/projects/programmable_transceiver_platform/analog/'
G=P+'pads/generated/'
files=[P+x for x in ['rf_rx/generated/lna.gds','rf_rx/generated/rxmix_i.gds','rf_rx/generated/bbfilter_i.gds','rf_rx/generated/bb_tap.gds',
 'rf_tx/generated/txmix_i.gds','rf_tx/generated/txsum.gds','rf_tx/generated/rfdriver.gds','converters/generated/adc_i.gds','converters/generated/adc_q.gds',
 'converters/generated/dac_i.gds','converters/generated/dac_q.gds','converters/generated/refbuf.gds','pll_vreg/generated/pt_pll_vreg2.gds','bbfilter_q_dummy'][:-1]]
files+=glob.glob(P+'timing/generated/*.gds')+glob.glob(P+'timing/generated/lcvco/pt_lc_qvco5.gds')+glob.glob(P+'wired_rx/generated/*.gds')+glob.glob(P+'wired_tx/generated/*.gds')
files+=[G+x for x in ['steering-buffer-compact/tx_steering_buffer_flat.gds','termination-buffer-candidate/compact-array/buffer_compensated_flat.gds','tlp-site/pad_tlp_flat.gds',
 'stress-safe-families/rf-pair/pad.gds','stress-safe-families/rf-tx/pad.gds','stress-safe-families/single-leg/pad.gds','stress-safe-families/reference/combined.gds',
 'stress-safe-families/wired-receive-hs/pad_hspad.gds','stress-safe-families/wired-receive-usb/combined.gds','stress-safe-families/wired-transmit/combined.gds']]
files+=[P+'rf_rx/generated/rxmix_q.gds',P+'rf_rx/generated/bbfilter_q.gds',P+'rf_tx/generated/txmix_q.gds']
files+=[P+'bringup_control/generated/pt_wtx_fallback_control.gds']
out={}
for f in files:
  ly=db.Layout(); ly.read(f)
  for t in ly.top_cells():
    b=t.dbbox(); out[f.replace(P,'')+':'+t.name]=[round(b.left,2),round(b.bottom,2),round(b.right,2),round(b.top,2)]
json.dump(out,open('/work/bbox.json','w'),indent=0)
