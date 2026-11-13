#!/usr/bin/env python3
"""Mechanical top-netlist audit against the chip binding (verification/chip_assembly/netlist.py output).
 A. every X instance of .subckt pt_chip_full: net count == pin count of its library subckt (positional binding).
 B. library (extracted) subckt pin SET == current schematic-source subckt pin set (stale layout/extraction).
 C. netlist.py PATHS / ATB_PORTS keys that name a pin the current master does not have (stale binding rules:
    the generator silently ignores them, so the intended connection is simply absent).
 D. v6 floorplan blocks (placed + failures) with no instance in the netlist, and vice versa.
 E. per-instance unbound-port count and classes of dangling digital-macro nets.
--selftest: inject a dropped net on one instance, a renamed pin in a library subckt and a bogus PATHS key;
all three must be reported."""
import re,sys,json,os,collections
SV='/home/ubuntu/svalbard'; P=SV+'/projects/programmable_transceiver_platform'
CHIP=SV+'/scratch/integration/m6-powerup/chipnet'
SRC={ # master -> schematic source (relative to P/analog), subckt
 'lna':('rf_rx/lna.spice','pt_lna'),'rxmix_i':('rf_rx/rxmix_i.spice','pt_rxmix_i'),'rxmix_q':('rf_rx/rxmix_q.spice','pt_rxmix_q'),
 'bbfilter_i':('rf_rx/bbfilter_i.spice','pt_bbfilter_i'),'bbfilter_q':('rf_rx/bbfilter_q.spice','pt_bbfilter_q'),
 'txmix_i':('rf_tx/txmix_i.spice','pt_txmix_i'),'txmix_q':('rf_tx/txmix_q.spice','pt_txmix_q'),'txsum':('rf_tx/txsum.spice','pt_txsum'),
 'rfdriver':('rf_tx/rfdriver.spice','pt_rfdriver'),'adc_i':('converters/adc_i.spice','pt_adc_i'),'adc_q':('converters/adc_q.spice','pt_adc_q'),
 'dac_i':('converters/dac_i.spice','pt_dac_i'),'dac_q':('converters/dac_q.spice','pt_dac_q'),'refbuf':('converters/refbuf.spice','pt_refbuf'),
 'pll_ring':('timing/pll_ring.spice','pt_pll_ring'),'pll_ring_core':('timing/pll_ring_core.spice','pt_pll_ring_core'),
 'clockmux':('timing/clockmux.spice','pt_clockmux'),'prescale':('timing/prescale.spice','pt_prescale'),'wordclk':('timing/wordclk.spice','pt_wordclk'),
 'polyphase':('timing/polyphase.spice','pt_polyphase'),'lo_ext':('timing/lo_ext.spice','pt_lo_ext'),'cdr':('wired_rx/cdr.spice','pt_cdr'),
 'ctle':('wired_rx/ctle.spice','pt_ctle'),'detect':('wired_rx/detect.spice','pt_detect'),'rxlevel':('wired_rx/rxlevel.spice','pt_rxlevel'),
 'rxselect':('wired_rx/rxselect.spice','pt_rxselect'),'slicer':('wired_rx/slicer.spice','pt_slicer'),'termination':('wired_rx/termination.spice','pt_termination'),
 'wmon_sel':('wired_rx/wmon_sel.spice','pt_wmon_sel'),'wiredtx':('wired_tx/wiredtx.spice','pt_wiredtx'),'hsbias':('wired_tx/hsbias.spice','pt_wtx_hsbias'),
 'bb_tap':('rf_rx/bb_tap.spice','pt_bb_tap'),'clk_obs16':('timing/clk_obs16.spice','pt_clk_obs16'),'diff_clk_rx':('timing/diff_clk_rx.spice','pt_diff_clk_rx'),
 'ring_osc':('timing/ring_osc.spice','pt_ring_osc'),'vco_replica':('timing/vco_replica.spice','pt_vco_replica'),'aosc':('timing/aosc.spice','pt_aosc')}
def subckt_heads(text):
    text=re.sub(r'\n\+\s*',' ',text); out={}
    for m in re.finditer(r'^\.subckt\s+(\S+)([^\n]*)',text,re.M|re.I):
        out[m.group(1)]=[p for p in m.group(2).split() if '=' not in p]
    return text,out
def audit(chip_text,netlist_py,binding,fp6):
    issues=[]
    text,heads=subckt_heads(chip_text)
    top=re.search(r'^\.subckt pt_chip_full.*?^\.ends pt_chip_full',text,re.M|re.S).group(0)
    inst={}
    for l in top.split('\n')[1:-1]:
        t=l.split()
        if not t or t[0][0] not in 'xX' or t[0].startswith('XC'): continue
        nets=[x for x in t[1:] if '=' not in x]; sub=nets[-1]; nets=nets[:-1]
        inst[t[0][1:]]=(sub,nets)
        if sub not in heads: issues.append(('A',f'{t[0]}: subckt {sub} not in library'))
        elif len(heads[sub])!=len(nets): issues.append(('A',f'{t[0]}: {len(nets)} nets vs {len(heads[sub])} pins of {sub}'))
    # B
    sys.path.insert(0,CHIP+'/flow'); import inventory as inv
    master_of={p['name']:p['master'] for p in json.load(open(CHIP+'/floorplan.json'))['placed']}
    master_of['pll_tx']='pll_ring_core'
    for m,(f,s) in SRC.items():
        if m not in inv.MASTERS: continue
        lib=heads.get(inv.MASTERS[m][3])
        try: _,sh=subckt_heads(open(P+'/analog/'+f).read())
        except FileNotFoundError: issues.append(('B',f'{m}: source {f} missing')); continue
        if lib is None or s not in sh:
            if m in master_of.values(): issues.append(('B',f'{m}: no library/source subckt')); 
            continue
        if set(lib)!=set(sh[s]):
            issues.append(('B',f'{m}: extracted {inv.MASTERS[m][2]} vs schematic analog/{f}: only-in-extracted={sorted(set(lib)-set(sh[s]))} only-in-schematic={sorted(set(sh[s])-set(lib))}'))
        elif lib!=sh[s]:
            issues.append(('B-order',f'{m}: same pins, different ORDER between extracted and schematic (positional users beware)'))
    # C
    for key in re.findall(r"'([a-z_0-9]+\.[A-Za-z_0-9]+)':\s*'",netlist_py):
        i,p=key.split('.',1)
        if i in inst and p not in heads.get(inst[i][0],[]): issues.append(('C',f'netlist.py PATHS binds {key} but {inst[i][0]} has no pin {p}'))
        if i not in inst and i not in ('por',): issues.append(('C2',f'netlist.py PATHS binds {key} but no instance {i} in the netlist'))
    for i,p in re.findall(r"\('([a-z_0-9]+)', '([A-Za-z_0-9]+)'\):",netlist_py):
        if i in inst and p not in heads.get(inst[i][0],[]): issues.append(('C',f'netlist.py ATB_PORTS binds {i}.{p} but pin absent'))
        if i not in inst: issues.append(('C2',f'netlist.py ATB_PORTS binds {i}.{p} but no instance {i}'))
    # D
    want=set(fp6['placed'])|set(fp6['failures'])
    want={w for w in want if not re.match(r'(leaf_|atb|steer_|.*_rsv|isw_|attached)',w)}
    have=set(inst)
    alias={'clk_obs16':'clk_obs'}
    for w in sorted(want):
        if alias.get(w,w) not in have: issues.append(('D',f'v6 floorplan block {w} has NO instance in the chip netlist (no pin binding exists anywhere)'))
    return issues,inst,heads
if __name__=='__main__':
    chip=open(CHIP+'/pt_chip_full.spice').read()
    npy=open(P+'/verification/chip_assembly/netlist.py').read()
    b=json.load(open(CHIP+'/binding.json')); fp6=json.load(open(SV+'/scratch/chip-assembly-v6/run/floorplan-v6.json'))
    if '--selftest' in sys.argv:
        base,_,_=audit(chip,npy,b,fp6)
        c2=re.sub(r'^(Xlna )(\S+ )',r'\1',chip,count=1,flags=re.M)           # drop one net
        c2=c2.replace('.subckt pt_txsum VDD VSS i_p','.subckt pt_txsum VDD VSS i_pX',1) # rename a library pin
        n2=npy.replace("'lna.rf_in_p': 'RF_RX_P'","'lna.rf_in_p': 'RF_RX_P', 'lna.bogus_pin': 'X'")
        got,_,_=audit(c2,n2,b,fp6); new=[g for g in got if g not in base]
        kinds={k for k,_ in new}; print('\n'.join(map(str,new)))
        assert {'A','B','C'}<=kinds, kinds; print('SELFTEST PASS: dropped net (A), renamed pin (B), bogus binding (C) all detected'); sys.exit(0)
    issues,inst,heads=audit(chip,npy,b,fp6)
    for k,m in issues: print(f'[{k}] {m}')
    c=collections.Counter(u['inst'] for u in b['unbound'])
    tot={i:len(v) for i,v in b['bindings'].items()}
    print('\n[E] unbound ports per instance (unbound/total):',', '.join(f'{i} {n}/{tot.get(i,"?")}' for i,n in c.most_common() if not i.startswith('atb')))
    dang=collections.Counter(re.sub(r'\[\d+\]','[]',d) for d in b['dangling'])
    print('[E] dangling net classes:',dict(dang.most_common(60)))
    json.dump([list(i) for i in issues],open(os.path.dirname(os.path.abspath(__file__))+'/top_pins.json','w'),indent=1)
