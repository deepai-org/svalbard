#!/usr/bin/env python3
"""Bias trunk audit: every cell pin named *IBIAS*/IB_* in a chip-level cell must (a) appear as a core_bias
consumer (integration/core_bias.py CONSUMERS) and (b) terminate inside the cell on an NMOS diode to VSS
(core_bias banks SOURCE 10 uA from the island rail).  Prints per-pin: first-level devices on the bias net,
classification, and whether core_bias has an output for it.  --selftest injects (1) a PMOS-diode consumer
and (2) a consumer missing from CONSUMERS and requires both to be flagged."""
import re,sys,json,os
P='/home/ubuntu/svalbard/projects/programmable_transceiver_platform'
CELLS={ # instance -> (file, subckt, core_bias consumer name or None)
 'lna':('analog/rf_rx/lna.spice','pt_lna','lna'),'rxmix_i':('analog/rf_rx/rxmix_i.spice','pt_rxmix_i','rxmix_i'),
 'rxmix_q':('analog/rf_rx/rxmix_q.spice','pt_rxmix_q','rxmix_q'),
 'bbfilter_i':('analog/rf_rx/bbfilter_i.spice','pt_bbfilter_i','bbfilter_i'),'bbfilter_q':('analog/rf_rx/bbfilter_q.spice','pt_bbfilter_q','bbfilter_q'),
 'txmix_i':('analog/rf_tx/txmix_i.spice','pt_txmix_i','txmix_i'),'txmix_q':('analog/rf_tx/txmix_q.spice','pt_txmix_q','txmix_q'),
 'rfdriver':('analog/rf_tx/rfdriver.spice','pt_rfdriver','rfdriver'),
 'adc_i':('analog/converters/adc_i.spice','pt_adc_i','adc_i'),'adc_q':('analog/converters/adc_q.spice','pt_adc_q','adc_q'),
 'dac_i':('analog/converters/dac_i.spice','pt_dac_i','dac_i'),'dac_q':('analog/converters/dac_q.spice','pt_dac_q','dac_q'),
 'refbuf':('analog/converters/refbuf.spice','pt_refbuf','refbuf'),
 'pll_cdr':('analog/timing/pll_ring.spice','pt_pll_ring','pll_ring_rx'),
 'pll_tx':('analog/timing/pll_ring_core.spice','pt_pll_ring_core','pll_ring_tx'),
 'lo_pfdcp':('analog/timing/lo_pfdcp.spice','pt_lo_pfdcp',None),
 'qvco':('analog/timing/lcvco/qvco5.spice',None,'lc_vco_reserved'),
 'cdr':('analog/wired_rx/cdr.spice','pt_cdr',None),
 'ctle':('analog/wired_rx/ctle.spice','pt_ctle','ctle'),'detect':('analog/wired_rx/detect.spice','pt_detect','detect'),
 'wiredtx':('analog/wired_tx/wiredtx.spice','pt_wiredtx','wiredtx'),'hsbias':('analog/wired_tx/hsbias.spice','pt_wtx_hsbias',None),
 'bb_tap':('analog/rf_rx/bb_tap.spice','pt_bb_tap','bb_tap_i'),
}
def load(path):
    t=open(path,errors='replace').read(); t=re.sub(r'\n\+',' ',t); subs={}
    for m in re.finditer(r'^\.subckt\s+(\S+)([^\n]*)\n(.*?)^\.ends',t,re.M|re.S|re.I):
        subs[m.group(1)]=([p for p in m.group(2).split() if '=' not in p],m.group(3).split('\n'))
    return subs
def trace(subs,sub,net,depth=0,out=None):
    out=[] if out is None else out
    pins,body=subs[sub]
    for l in body:
        tk=l.split()
        if not tk or tk[0][0] in '*.': continue
        nodes=[x for x in tk[1:] if '=' not in x]
        if tk[0][0] in 'xX':
            model=nodes[-1]; conn=nodes[:-1]
            if net not in conn: continue
            if model in subs and depth<4:
                for i,c in enumerate(conn):
                    if c==net and i<len(subs[model][0]): trace(subs,model,subs[model][0][i],depth+1,out)
            else:
                idx=[i for i,c in enumerate(conn) if c==net]
                out.append((model,conn,idx))
        elif tk[0][0] in 'mM':
            conn=nodes[:4]; model=nodes[4]
            if net in conn: out.append((model,conn,[i for i,c in enumerate(conn) if c==net]))
        elif tk[0][0] in 'rRcCiIvV' and net in nodes[:2]:
            out.append((tk[0][0].upper(),nodes[:2],[]))
    return out
def follow(subs,sub,net):
    """first-level devices, plus one hop through a series pass switch/resistor (other terminal net, same subckt)."""
    devs=trace(subs,sub,net); extra=[]
    for model,conn,idx in devs:
        other=None
        if ('fet' in model) and idx in ([0],[2]) : other=conn[2] if idx==[0] else conn[0]
        elif 'ppolyf' in model or 'nplus' in model or model=='R': other=[c for c in conn[:2] if c!=net][0] if len(conn)>=2 and net in conn[:2] else None
        if other and other.upper() not in ('VSS','VDD','0'):
            # search the subckt that contains this hop: approximate by scanning every subckt for the net name
            for sn in subs:
                extra+= [d for d in trace(subs,sn,other,depth=4) if d[0]!=model or d[1]!=conn]
    return devs+extra
def classify(devs):
    kinds=set()
    for model,conn,idx in devs:
        if 'nfet' in model or 'nmos' in model:
            d,g,s=conn[0],conn[1],conn[2]
            if 0 in idx and 1 in idx: kinds.add('NMOS-diode(sinks from rail-side source)')
            elif idx==[1]: kinds.add('nmos-gate')
            elif 0 in idx: kinds.add('nmos-drain')
            elif 2 in idx: kinds.add('nmos-source')
        elif 'pfet' in model or 'pmos' in model:
            if 0 in idx and 1 in idx: kinds.add('PMOS-diode(needs a SINK)')
            elif idx==[1]: kinds.add('pmos-gate')
            elif 0 in idx: kinds.add('pmos-drain')
            elif 2 in idx: kinds.add('pmos-source')
        else: kinds.add(model[:14])
    return kinds
def run(cells,consumers):
    bad=[]
    for inst,(f,sub,cons) in cells.items():
        path=os.path.join(P,f)
        if not os.path.exists(path): print(f'{inst}: MISSING FILE {f}'); bad.append(inst); continue
        subs=load(path)
        if sub is None: sub=list(subs)[-1]
        if sub not in subs: print(f'{inst}: no subckt {sub}'); bad.append(inst); continue
        bp=[p for p in subs[sub][0] if re.search(r'ibias|^IB_|lobias',p,re.I)]
        if not bp:
            print(f'{inst}: {sub} has NO bias pin; core_bias output {"BIAS_"+cons if cons else "-"} would be unused')
            if cons: bad.append(inst+':no-pin')
            continue
        for p in bp:
            k=classify(follow(subs,sub,p))
            ok_dir=any(x.startswith('NMOS-diode') for x in k) and not any(x.startswith('PMOS-diode') for x in k)
            ok_src=(cons in consumers) and p.lower()=='ibias'
            flag=[]
            if not ok_dir: flag.append('DIRECTION?')
            if not ok_src: flag.append('NO core_bias OUTPUT')
            if cons=='lc_vco_reserved': flag.append('core_bias EN tied VSS (integration/core_bias.py:128)')
            print(f'{inst}.{p} [{f}] -> {sorted(k)} consumer={cons} {" ".join(flag) or "ok"}')
            if flag: bad.append(f'{inst}.{p}')
    return bad
if __name__=='__main__':
    sys.path.insert(0,P+'/integration'); 
    src=open(P+'/integration/core_bias.py').read()
    cons=eval(re.search(r'CONSUMERS = (\{.*?\n\})',src,re.S).group(1))
    allc=[c for v in cons.values() for c in v]
    if '--selftest' in sys.argv:
        import tempfile
        d=tempfile.mkdtemp(); open(d+'/t.spice','w').write('.subckt t ibias VDD VSS\nXM1 ibias ibias VDD VDD pfet_03v3 w=1 l=1\n.ends\n')
        global_P=P
        bad=run({'t':(d+'/t.spice','t','lna')},allc); assert bad==['t.ibias'],bad
        bad=run({'lna':CELLS['lna'][:2]+('not_a_consumer',)},allc); assert bad,bad
        print('SELFTEST PASS (pmos-diode consumer and missing consumer both flagged)'); sys.exit(0)
    print('core_bias consumers:',cons)
    bad=run(CELLS,allc)
    print('\nFLAGGED:',bad); print('outputs per trunk:',{k:len(v) for k,v in cons.items()},'x 10 uA nominal (7.6-12.1 uA untrimmed)')
