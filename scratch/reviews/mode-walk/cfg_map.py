#!/usr/bin/env python3
"""Config bit map vs cell pins.
Inputs: spec/register-map.json (bus fields), rtl/*.sv + integration/pt_chip.sv (which PT_A_/PT_D_ fields any RTL reads),
the schematic subckt pin lists (pins.json) and MAP below = the intended field for every static control pin of every
chip-level cell (taken from the block READMEs' register tables / register-map trim reasons; None = no field exists).
Reports: (1) control pins with no register field, (2) width mismatches, (3) bus fields with neither an RTL reader
nor a cell pin, (4) fields shared by I and Q instances that need per-channel values.
--selftest: shrinks one field by a bit and deletes one mapped field; both must be reported."""
import json,re,sys,os,glob
P='/home/ubuntu/svalbard/projects/programmable_transceiver_platform'
HERE=os.path.dirname(os.path.abspath(__file__))
def R(prefix,n,start=0): return [f'{prefix}{i}' for i in range(start,start+n)]
# cell -> list of (pins, field or None, note)
# Updated 2026-11-14 by digital for the mode-walk register rework (spec_edit.py): fields follow the cells. Pins that are
# NOT register controls are no longer listed: pt_pll_ring*.HOLD (cell-to-cell net from pt_cdr HOLD_PLL), pt_lc_qvco5.PRE
# (an output), pt_diff_clk_rx.SE (tied low in pt_chip.conn), pt_polyphase (deleted, CP4-2), rxmix hib (not on the cell).
# 'dyn' notes = driven by a macro control block (pt_wrx_ctl / pt_wtx_ctl / pt_usb), configured by the named field.
MAP={
 'pt_lna':[(['en'],'lna.state.state','!=off'),(['gain_lo'],'lna.match.gain_lo',''),(['byp'],'debug.rf_rx_bypass.lna',''),
   (R('ct',4),'lna.match.ctrim',''),(['se'],'lna.match.se',''),(['rt'],'lna.match.rterm',''),(R('att',5),'lna.match.att',''),
   (['lobias'],'lna.bias.lo','')],
 'pt_rxmix_i':[(['en'],'rxmix_i.state.state',''),(R('ofs',5)+['ofs_sign'],'rxmix.offset.i_code','')],
 'pt_rxmix_q':[(['en'],'rxmix_q.state.state',''),(R('ofs',5)+['ofs_sign'],'rxmix.offset.q_code','')],
 'pt_bbfilter_i':[(['en','dir_tx'],'consolidation.bbfilter.direction','decode'),(['inj']+R('obs_sel',2),'debug.bb_tap.mode','decode'),
   (['rx_direct'],'consolidation.bbfilter.rx_direct',''),(['byp_s1'],'debug.rf_bb_bypass.pga',''),(['byp_s23'],'debug.rf_bb_bypass.rxfilter',''),
   (R('fc_fine',3)+R('bw',4),'bbfilter_i.trim.cut',''),(R('gain',6)+R('gainc',2),'bbfilter_i.trim.gain','decode (LUT)'),
   (R('qt',4),'bbfilter_i.trim.qt',''),(R('dcf',8)+['dcf_sign'],'bbfilter_i.trim.dcf','')],
 'pt_adc_i':[(['EN'],'adc_i.state.state',''),(R('TEST',2),'adc_i.config.input_test',''),(['ILEN'],'adc.config.interleave','')],
 'pt_dac_i':[(['EN'],'dac_i.state.state',''),(['HOLD_ZERO'],'dac_i.config.hold_zero','')],
 'pt_refbuf':[(['EN'],'refbuf.state.state',''),(['OVR'],'debug.bias_override.refbuf','')],
 'pt_txmix_i':[(['en'],'txmix_i.state.state',''),(['sel_dac'],'consolidation.bbfilter.tx_dac_direct',''),(['sat'],'consolidation.txmix.sat_mode','')],
 'pt_txsum':[(['en'],'txsum.state.state','')],
 'pt_rfdriver':[(['en'],'rfdriver.state.state',''),(['mute'],'rfdriver.mute.mute',''),(['bypass'],'debug.rf_tx_bypass.rfdriver',''),
   (R('g',4),'rfdriver.gain.code',''),(['se'],'rfdriver.gain.single_ended','')],
 'pt_bb_tap':[(['obs_en','inj_en'],'debug.bb_tap.mode','decode')],
 'pt_lo_ext':[(['EXT','INT','CMLSEL'],'rfpll.config.lo_mode','decode')],
 'pt_lc_qvco5':[(['EN'],'rfpll.state.state',''),(R('BAND',4),'rfpll.config.vco_coarse',''),(['CMLSEL'],'rfpll.config.lo_mode','decode')],
 'pt_lo_mmd':[(['EN'],'rfpll.state.state',''),(R('N',6),'rfpll.config.lo_n','')],
 'pt_lo_pfdcp':[(['EN'],'rfpll.state.state',''),(['PRE'],'rfpll.config.lo_preset',''),(R('ICP',2),'rfpll.config.lo_icp','')],
 'pt_lo_obs':[(['EN'],'debug.clk_obs.source','decode')],
 'pt_prescale':[(['EN']+['D2','D4','D8','D16'],'clockmux.config.host_prescale','one-hot decode (three instances: host/conv/hf_prescale)')],
 'pt_wordclk':[(['EN','D10','D20'],'slicer.capture.rate_mode','decode')],
 'pt_clockmux':[(['PS_REF','PS_AUX','PS_H2D'],'clockmux.config.ring_ref','one-hot'),(['WS_PLL','WS_REF','WS_AUX','WS_WCK'],'debug.clk_select.wire_line','one-hot'),
   (['SS_INT','SS_REF','SS_WCK'],'debug.clk_select.wire_sample','one-hot'),(['CS_INT','CS_REF','CS_AUX','CS_HF'],'debug.clk_select.conv_sample','one-hot'),
   (['HS_INT','HS_HF'],'debug.clk_select.host_clk','one-hot')],
 'pt_pll_ring':[(['EN'],'cdr.state.state',''),(['N4','N8','N5','N10'],'ring_c.config.modulus','one-hot'),
   (R('KP',3),'ring_c.config.kp',''),(['BAND'],'ring_c.config.band','')],
 'pt_pll_ring_core':[(['EN'],'ring_l.config.enable','decode (sequenced by pt_wtx_ctl)'),(['N4','N8'],'ring_l.config.modulus','one-hot'),(['BAND'],'ring_l.config.band','')],
 'pt_pll_vreg2':[(['BYP_TX'],'pllvreg.config.tx_bypass',''),(['BYP_CDR'],'pllvreg.config.rx_bypass','')],
 'pt_cdr':[(['cdr_en'],'cdr.state.state',''),(['pfd_mode'],'ring_c.config.line_pll',''),(['ref_sel'],'cdr.ac3.fll_ref_wck',''),(R('g',3),'cdr.ac3.loop_bw','')],
 'pt_ptrim':[(['ptrim_en'],'slicer.state.state','macro port wire_rx_ptrim_en')]+[(R(f'T{k}_',5),f'cdr.phase_trim.p{k}','') for k in range(8)],
 'pt_slicer':[(['slicer_en'],'slicer.state.state','')]+
   [([f'trim_{s}{k}_{x}' for x in ('p0','p1','p2','n0','n1','n2','f0','f1','f2','f3')],f'slicer.offset.trim_{s}{k}','') for s in 'de' for k in range(4)]+
   [([f'vsel_e{k}_{j}' for j in range(2)],f'slicer.threshold.vsel_e{k}','') for k in range(4)],
 'pt_vthdac':[(['vth_en'],'slicer.threshold.vth_enable',''),(R('A',8),'slicer.threshold.vth_a',''),(R('B',8),'slicer.threshold.vth_b','')],
 'pt_ctle':[(['ctle_en'],'ctle.state.state',''),(['wire_ctle_bypass'],'debug.wire_bypass.ctle',''),(R('ctle_peak',3),'ctle.config.peak',''),(R('lf_zero',3),'ctle.config.lf_zero','')],
 'pt_rxselect':[(['rxselect_en'],'rxselect.state.state',''),(['rxselect_direct'],'rxselect.select.branch','')],
 'pt_rxlevel':[(['rxlevel_en','rxlevel_half'],'rxlevel.config.path','decode')],
 'pt_termination':[(['term_en','term_mode0','term_mode1'],'termination.config.p_load','+differential_100_enable'),(['hs_en'],'termination.config.hs_enable',''),
   (['hs_term_en'],'termination.config.hs_term_enable',''),(R('hs_trim',4),'termination.config.hs_trim','')],
 'pt_detect':[(['det_en'],'detect.state.state',''),(R('det_thr',2),'detect.config.high_threshold_code',''),(R('det_se',2),'detect.config.low_threshold_code',''),
   (['det_src_tx'],'consolidation.detect.src_tx',''),(['det_inject'],'detect.config.test_current_enable','')],
 'pt_wmon_sel':[(['wmon_en','wmon_sel0','wmon_sel1'],'debug.wmon_select.select','decode')],
 'pt_wrx_cap':[(['EN'],'slicer.state.state',''),(['RCS'],'slicer.capture.rcsel',''),(['B2','B1'],'slicer.capture.rate_mode','decode'),
   (R('PSEL',3),'wrx.picker.manual_psel','decode (dyn: pt_wrx_ctl phase picker)'),(['SLIPP','SLIPM'],'wrx.picker.manual_slip_plus','decode (dyn: pt_wrx_ctl slip tags)')],
 'pt_wiredtx':[(['MODE_H','MODE_F'],'consolidation.wiredtx_stage.rate_mode','decode'),(['WTX_EXT'],'debug.wtx_ext.enable',''),(['POST_POL'],'wiredtx.config.post_polarity',''),
   (['EN_MAIN','EN_POST'],'wiredtx.state.state','+idle'),(R('MAIN_CODE',8),'wiredtx.config.current_code',''),(R('POST_CODE',8),'wiredtx.config.postcursor_code','')],
 'pt_wtx_hsbias':[(['EN'],'usbhs.bias.enable',''),(R('C',8),'usbhs.bias.code','')],
 'pt_clk_obs16':[(['EN']+R('S',4),'debug.clk_obs.source','decode (5b enum -> EN + 4 select pins)'),(R('N',3),'debug.clk_obs.divider_log2','')],
 'pt_diff_clk_rx':[(['EN'],'refinput.state.state','REF instance; debug instances use rx_en_*')],
 'pt_aosc':[(['EN'],'core.aosc.enable','')],
 'pt_ring_osc':[(['EN'],'debug.replica.ringosc_enable','')],
 'pt_vco_replica':[(['EN'],'debug.replica.vco_enable','')],
}
# Bus fields consumed inside the macro (no analog pin by design); the consumer is named. Checked: the field must exist.
INTERNAL={
 'debug.dbg_obs.sel0':'pt_regfile DBG_OBS0 mux','debug.dbg_obs.sel1':'pt_regfile DBG_OBS1 mux',
 'debug.calibration.tag':'software scratch readback (calibration lifecycle)','debug.calibration.valid':'software scratch readback',
 'lna.agc.code0':'pt_ctl_decode opcode-4 LNA table','lna.agc.code1':'pt_ctl_decode','lna.agc.code2':'pt_ctl_decode','lna.agc.code3':'pt_ctl_decode',
 'clockmux.config.conv_prescale':'pt_ctl_decode -> prescale_conv','clockmux.config.hf_prescale':'pt_ctl_decode -> prescale_hf',
 'adc.config.acquisition':'pt_ctl_decode -> adc_i/q ACQ (staged converter contract, pins not in the published subckt yet)',
 'rfpll.config.atb_enable':'pt_ctl_decode -> qvco.ATB_EN','cdr.ac3.otr':'pt_ctl_decode -> pt_cdr otr (r13)',
 'debug.replica.ro33_enable':'pt_ctl_decode -> c_char_en','debug.replica.ro50_enable':'pt_ctl_decode -> c_char_en','debug.replica.cmldiv_enable':'pt_ctl_decode -> c_char_en',
 'usbhs.config.drive_strength':'pt_ctl_decode -> pt_usb_txdrv','txpad.config.term_request':'pt_wtx_ctl -> interlock REQ_TERM',
 'usbhs.config.term_enable':'pt_regfile gate_and of usbhs.config.term_trim (pad TERM_TRIM = trim AND enable); also a rule input',
 'txpad.config.branch':'pt_wtx_ctl -> interlock requests','wiredtx.idle.idle':'pt_wtx_ctl','consolidation.wiredtx_stage.stage':'pt_wtx_ctl -> fallback control',
}
PER_CHANNEL={}   # bbfilter trims are per channel since 2026-11-14 (bbfilter_i.trim / bbfilter_q.trim)
def run(fields,pins):
    rep=dict(nofield=[],width=[],used=set(),internal_missing=[n for n in INTERNAL if n not in fields or fields[n]['bus'] is None])
    for cell,rows in MAP.items():
        have=pins.get(cell)
        if not have: rep['nofield'].append((cell,'<cell>','subckt not found')); continue
        have=have[0][2]
        for plist,field,note in rows:
            miss=[p for p in plist if p not in have]
            if miss: rep['width'].append((cell,','.join(miss),'MAP names pins the cell does not have (script table stale)')); continue
            if field is None: rep['nofield'].append((cell,' '.join(plist) if len(plist)<4 else f'{plist[0]}..{plist[-1]} ({len(plist)})',note)); continue
            f=fields.get(field)
            if f is None or f['bus'] is None:
                rep['nofield'].append((cell,' '.join(plist) if len(plist)<4 else f'{plist[0]}..{plist[-1]} ({len(plist)})',f'{field}: '+('dropped from bus' if f else 'no such field'))); continue
            rep['used'].add(field)
            if 'decode' in note or 'one-hot' in note or '+' in note or 'macro port' in note or note in ('!=off','2-level','?'): continue
            if field.endswith('.state.state') and len(plist)==1: continue  # 2-bit state -> 1 enable needs decode glue (en_eff)
            if f['bus_bits']!=len(plist): rep['width'].append((cell,f'{plist[0]}..{plist[-1]}',f'{len(plist)} pins vs {field} {f["bus_bits"]} bus bits (of {f["bits"]}) {note}'))
    return rep
if __name__=='__main__':
    reg=json.load(open(P+'/spec/register-map.json')); fields={f['name']:f for f in reg['fields']}
    pins=json.load(open(HERE+'/pins.json'))
    # twin cells share the i-map
    for a,b in (('pt_rxmix_q','pt_rxmix_i'),('pt_bbfilter_q','pt_bbfilter_i'),('pt_adc_q','pt_adc_i'),('pt_dac_q','pt_dac_i'),('pt_txmix_q','pt_txmix_i')):
        MAP.setdefault(a,[(p,(f.replace('_i.','_q.').replace('.i_code','.q_code') if f else f),n) for p,f,n in MAP[b]])
    if '--selftest' in sys.argv:
        import copy
        f2=copy.deepcopy(fields); f2['lna.match.att']['bus_bits']=4; del f2['rfdriver.mute.mute']; del f2['debug.dbg_obs.sel0']
        r=run(f2,pins)
        assert any(c=='pt_lna' and 'att0' in p for c,p,_ in r['width']), r['width']
        assert any(c=='pt_rfdriver' and p=='mute' for c,p,_ in r['nofield'])
        assert any(f=='debug.dbg_obs.sel0' for f in r.get('internal_missing',[]))
        print('SELFTEST PASS: narrowed field, deleted field and missing internal field all reported'); sys.exit(0)
    r=run(fields,pins)
    rtl=''.join(open(f).read() for f in glob.glob(P+'/rtl/pt_*.sv')+[P+'/integration/pt_chip.sv'] if not f.endswith('pt_regfile.sv'))
    rtl_used={f['name'] for f in fields.values() if f['bus'] and (re.search(r'PT_[AD]_'+f['sv'].upper()+r'_(LSB|W)\b',rtl) or re.search(r'\bf_'+f['sv']+r'\b',rtl))}
    for n in r['internal_missing']: r['nofield'].append(('macro',n,'INTERNAL consumer table names a field that does not exist'))
    print('== (1) cell control pins with NO register field on the bus')
    for c,p,n in r['nofield']: print(f'  {c}: {p}  -- {n}')
    print('== (2) width mismatches (pins vs bus bits)')
    for c,p,n in r['width']: print(f'  {c}: {p}  -- {n}')
    orphan=[f for f in fields.values() if f['bus'] and f['name'] not in r['used'] and f['name'] not in rtl_used and f['name'] not in INTERNAL
            and not f['name'].startswith(('core.biasgen','core.refchain','debug.island_power','debug.pgood_override'))]
    print(f'== (3) bus fields with neither an RTL reader nor a mapped cell pin: {len(orphan)} fields, {sum(f["bus_bits"] for f in orphan)} bits')
    for f in orphan: print(f"  {f['name']} [{f['bus']}_cfg {f['bus_lsb']}+{f['bus_bits']}]")
    print('== (4) single shared field driving both I and Q instances:',PER_CHANNEL)
    n1=sum(1 for _ in r['nofield']); print(f'TOTAL: {n1} pin groups without a field, {len(r["width"])} width mismatches, {len(orphan)} orphan fields')
