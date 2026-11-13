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
MAP={
 'pt_lna':[(['en'],'lna.state.state','!=off'),(['gain_lo'],'lna.gain.gain_db','2-level'),(['byp'],'debug.rf_rx_bypass.lna',''),
   (R('ct',4),'lna.match.ctrim',''),(['se'],'lna.match.se',''),(['rt'],'lna.match.rterm',''),(R('att',5),'lna.match.att',''),
   (['lobias'],None,'duplex reduced-bias mode (characterize.py:167)')],
 'pt_rxmix_i':[(['en'],'rxmix_i.state.state',''),(R('ofs',5)+['ofs_sign'],'rxmix.offset.i_code',''),(['hib'],None,'')],
 'pt_rxmix_q':[(['en'],'rxmix_q.state.state',''),(R('ofs',5)+['ofs_sign'],'rxmix.offset.q_code',''),(['hib'],None,'')],
 'pt_bbfilter_i':[(['en','dir_tx'],'consolidation.bbfilter.direction','decode'),(['inj']+R('obs_sel',2),'debug.bb_tap.mode','decode'),
   (['rx_direct'],'consolidation.bbfilter.rx_direct',''),(['byp_s1'],'debug.rf_bb_bypass.pga',''),(['byp_s23'],'debug.rf_bb_bypass.rxfilter',''),
   (R('bw',4),'consolidation.bbfilter.bw',''),(R('gain',6),'consolidation.bbfilter.gain',''),(R('gainc',2),None,'coarse PGA state'),
   (R('qt',4),'consolidation.bbfilter.qtrim',''),(R('fc_fine',3),None,'fine cutoff'),(R('dcf',8)+['dcf_sign'],None,'fine DCOC, per channel')],
 'pt_adc_i':[(['EN'],'adc_i.state.state',''),(R('TEST',2),'adc_i.config.input_test',''),(['ILEN'],None,'')],
 'pt_dac_i':[(['EN'],'dac_i.state.state',''),(['HOLD_ZERO'],'dac_i.config.hold_zero','')],
 'pt_refbuf':[(['EN'],'refbuf.state.state',''),(['OVR'],'debug.bias_override.refbuf','')],
 'pt_txmix_i':[(['en'],'txmix_i.state.state',''),(['sel_dac'],'consolidation.bbfilter.tx_dac_direct',''),(['sat'],'consolidation.txmix.sat_mode','')],
 'pt_txsum':[(['en'],'txsum.state.state','')],
 'pt_rfdriver':[(['en'],'rfdriver.state.state',''),(['mute'],'rfdriver.mute.mute',''),(['bypass'],'debug.rf_tx_bypass.rfdriver',''),
   (R('g',4),'rfdriver.gain.code',''),(['se'],'rfdriver.gain.single_ended','')],
 'pt_bb_tap':[(['obs_en','inj_en'],'debug.bb_tap.mode','decode')],
 'pt_lo_ext':[(['EXT','INT'],'debug.clk_select.rf_lo','decode'),(['CMLSEL'],None,'')],
 'pt_polyphase':[(['EN'],None,'')],
 'pt_lc_qvco5':[(['EN'],'rfpll.state.state',''),(R('BAND',4),None,'rfpll.config.vco_coarse is dropped'),(['CMLSEL'],None,''),(['PRE'],None,'VTUNE precharge')],
 'pt_lo_mmd':[(['EN'],'rfpll.state.state',''),(R('N',6),None,'rfpll.config.feedback_integer is dropped; consolidation.pll.feedback_n is 2 bits')],
 'pt_lo_pfdcp':[(['EN'],'rfpll.state.state',''),(['PRE'],None,''),(R('ICP',2),None,'rfpll.config.charge_pump_code is dropped')],
 'pt_lo_obs':[(['EN'],'debug.clk_obs.source','decode')],
 'pt_prescale':[(['EN']+['D2','D4','D8','D16'],'consolidation.pll.output_divider','one-hot decode of 3b')],
 'pt_wordclk':[(['EN','D10','D20'],'consolidation.wiredtx_stage.bits_per_cycle','decode')],
 'pt_clockmux':[(['PS_REF','PS_AUX','PS_H2D'],'refinput.select.branch','one-hot'),(['WS_PLL','WS_REF','WS_AUX','WS_WCK'],'debug.clk_select.wire_line','one-hot'),
   (['SS_INT','SS_REF','SS_WCK'],'debug.clk_select.wire_sample','one-hot'),(['CS_INT','CS_REF','CS_AUX','CS_HF'],'debug.clk_select.conv_sample','one-hot'),
   (['HS_INT','HS_HF'],'debug.clk_select.host_clk','one-hot')],
 'pt_pll_ring':[(['EN'],'cdr.state.state',''),(['N4','N8','N5','N10'],'consolidation.pll.feedback_n','one-hot of 2b'),(['HOLD'],None,'from pt_cdr HOLD_PLL'),
   (R('KP',3),None,'CDR proportional gain'),(['BAND'],None,'tied VDD in netlist.py:120')],
 'pt_pll_ring_core':[(['EN'],'rfpll.state.state','shared-PLL state'),(['N4','N8'],'consolidation.pll.feedback_n',''),(['HOLD'],None,''),(['BAND'],None,'tied VDD')],
 'pt_pll_vreg2':[(['BYP_TX'],'pllvreg.config.tx_bypass',''),(['BYP_CDR'],'pllvreg.config.rx_bypass','')],
 'pt_cdr':[(['cdr_en'],'cdr.state.state',''),(['pfd_mode'],'cdr.ac3.integral_enable','?'),(['ref_sel'],'cdr.ac3.fll_ref_wck',''),(R('g',3),'cdr.ac3.loop_bw',''),
   (R('otr',5)+['otrs'],None,'OTA offset trim (schematic only; not in layout)')],
 'pt_ptrim':[(['ptrim_en'],'slicer.state.state','macro port wire_rx_ptrim_en')]+[(R(f'T{k}_',5),f'cdr.phase_trim.p{k}','') for k in range(8)],
 'pt_slicer':[(['slicer_en'],'slicer.state.state','')]+
   [([f'trim_d{k}_{x}' for x in ('p0','p1','p2','n0','n1','n2','f0','f1','f2','f3')],'slicer.offset.data' if k==0 else None,'10 trim bits per sampler; field keeps 4') for k in range(4)]+
   [([f'trim_e{k}_{x}' for x in ('p0','p1','p2','n0','n1','n2','f0','f1','f2','f3')],('slicer.offset.early','slicer.offset.late',None,None)[k],'10 trim bits per sampler; field keeps 4') for k in range(4)]+
   [([f'vsel_e{k}_{j}' for k in range(4) for j in range(2)],None,'edge-sampler threshold select (IX-10)')],
 'pt_vthdac':[(['vth_en'],None,''),(R('A',8),None,'IX-10 threshold DAC A'),(R('B',8),None,'IX-10 threshold DAC B')],
 'pt_ctle':[(['ctle_en'],'ctle.state.state',''),(['wire_ctle_bypass'],'debug.wire_bypass.ctle',''),(R('ctle_peak',3),'ctle.config.zero_trim','keeps [1:0]'),(R('lf_zero',3),None,'IX-13 LF zero')],
 'pt_rxselect':[(['rxselect_en'],'rxselect.state.state',''),(['rxselect_direct'],'rxselect.select.branch','')],
 'pt_rxlevel':[(['rxlevel_en','rxlevel_half'],'rxlevel.config.path','decode')],
 'pt_termination':[(['term_en','term_mode0','term_mode1'],'termination.config.p_load','+differential_100_enable'),(['hs_en','hs_term_en'],'usbhs.config.term_enable',''),
   (R('hs_trim',4),'usbhs.config.term_trim','')],
 'pt_detect':[(['det_en'],'detect.state.state',''),(R('det_thr',2),'detect.config.high_threshold_code',''),(R('det_se',2),'detect.config.low_threshold_code',''),
   (['det_src_tx'],'consolidation.detect.src_tx',''),(['det_inject'],'detect.config.test_current_enable','')],
 'pt_wmon_sel':[(['wmon_en','wmon_sel0','wmon_sel1'],'debug.wmon_select.select','decode')],
 'pt_wrx_cap':[(['EN'],'slicer.state.state',''),(['RCS'],'cdr.config.cap_rcsel','2b field, 1 pin'),(['B2','B1'],'consolidation.wiredtx_stage.bits_per_cycle','RX uses the TX field?'),
   (R('PSEL',3),None,'phase select'),(['SLIPP','SLIPM'],None,'bit slip')],
 'pt_wiredtx':[(['MODE_H','MODE_F'],'consolidation.wiredtx_stage.rate_mode','decode'),(['WTX_EXT'],'debug.wtx_ext.enable',''),(['POST_POL'],None,'post-cursor polarity'),
   (['EN_MAIN','EN_POST'],'wiredtx.state.state','+idle'),(R('MAIN_CODE',8),'wiredtx.config.current_code',''),(R('POST_CODE',8),'wiredtx.config.postcursor_code','')],
 'pt_wtx_hsbias':[(['EN'],'usbhs.bias.enable',''),(R('C',8),'usbhs.bias.code','')],
 'pt_clk_obs16':[(['EN']+R('S',4),'debug.clk_obs.source','5b field vs 4 select pins + EN'),(R('N',3),'debug.clk_obs.divider_log2','4b field vs 3 pins')],
 'pt_diff_clk_rx':[(['EN'],'refinput.state.state','REF instance; debug instances use rx_en_*'),(['SE'],None,'single-ended mode')],
 'pt_aosc':[(['EN'],'core.aosc.enable','')],
 'pt_ring_osc':[(['EN'],'debug.replica.ringosc_enable','')],
 'pt_vco_replica':[(['EN'],'debug.replica.vco_enable','')],
}
PER_CHANNEL={'consolidation.bbfilter.qtrim':'Q trim differs per channel after layout mismatch','consolidation.bbfilter.gain':'I/Q gain trim'}
def run(fields,pins):
    rep=dict(nofield=[],width=[],used=set())
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
        f2=copy.deepcopy(fields); f2['lna.match.att']['bus_bits']=4; del f2['rfdriver.mute.mute']
        r=run(f2,pins)
        assert any(c=='pt_lna' and 'att0' in p for c,p,_ in r['width']), r['width']
        assert any(c=='pt_rfdriver' and p=='mute' for c,p,_ in r['nofield'])
        print('SELFTEST PASS: narrowed field and deleted field both reported'); sys.exit(0)
    r=run(fields,pins)
    rtl=''.join(open(f).read() for f in glob.glob(P+'/rtl/pt_*.sv')+[P+'/integration/pt_chip.sv'] if not f.endswith('pt_regfile.sv'))
    rtl_used={f['name'] for f in fields.values() if f['bus'] and re.search(r'PT_[AD]_'+f['sv'].upper()+r'_(LSB|W)\b',rtl)}
    print('== (1) cell control pins with NO register field on the bus')
    for c,p,n in r['nofield']: print(f'  {c}: {p}  -- {n}')
    print('== (2) width mismatches (pins vs bus bits)')
    for c,p,n in r['width']: print(f'  {c}: {p}  -- {n}')
    orphan=[f for f in fields.values() if f['bus'] and f['name'] not in r['used'] and f['name'] not in rtl_used
            and not f['name'].startswith(('core.biasgen','core.refchain','debug.island_power','debug.pgood_override'))]
    print(f'== (3) bus fields with neither an RTL reader nor a mapped cell pin: {len(orphan)} fields, {sum(f["bus_bits"] for f in orphan)} bits')
    for f in orphan: print(f"  {f['name']} [{f['bus']}_cfg {f['bus_lsb']}+{f['bus_bits']}]")
    print('== (4) single shared field driving both I and Q instances:',PER_CHANNEL)
    n1=sum(1 for _ in r['nofield']); print(f'TOTAL: {n1} pin groups without a field, {len(r["width"])} width mismatches, {len(orphan)} orphan fields')
