#!/usr/bin/env python3
"""pathsum.py <max.rpt> [group ...]: compact worst path per group: launch clock arrival, data stages (cell, fanout, delay), capture."""
import sys,re
txt=open(sys.argv[1]).read(); want=set(sys.argv[2:])
seen=set()
for blk in txt.split('Startpoint: ')[1:]:
    g=re.search(r'Path Group: (\S+)',blk)
    if not g: continue
    g=g.group(1)
    if g in seen or (want and g not in want): continue
    seen.add(g)
    sl=re.search(r'(-?[\d.]+)\s+slack',blk); 
    lines=blk.split('\n'); sp=lines[0].split()[0]
    ep=re.search(r'Endpoint: (\S+)',blk).group(1)
    clean=lambda s: re.sub(r'_gf180mcu_fd_sc_mcu7t5v0__\w+','',s)
    print(f'== {g} slack {sl.group(1) if sl else "?"}  {clean(sp)} -> {clean(ep)}')
    stage=[]; phase=0; arr=None; fan=None
    for l in lines:
        m=re.match(r'\s*(\d+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+[\^v]\s+(\S+)\s+\((\w+)\)',l)
        if 'data arrival time' in l and phase==0:
            phase=1; print('   launch: '+' '.join(stage)); stage=[]; continue
        if m:
            fo,cap,slew,d,t,pin,cell=m.groups(); cell=cell.replace('gf180mcu_fd_sc_mcu7t5v0__','')
            name=clean(pin).split('/')[0]
            tag='' 
            if re.match(r'(gain|max_cap|wire|rebuffer|load_slew|split|fanout|hold|place)\d+',name): tag='*'
            if cell.startswith('dff'): 
                if phase==0: print(f'   clk@{float(t)-float(d):.2f} ', end='')
                stage=[]
            stage.append(f'{cell}{tag}/{fo}:{float(d):.2f}')
    m=re.search(r'([\d.]+)\s+data required time',blk); a=re.search(r'([\d.]+)\s+data arrival time',blk)
    cc=[re.search(r'([\d.-]+)\s+([\d.-]+)\s+\^ (\S+)/CLK',l) for l in blk.split('data arrival time')[1].split('\n')] if 'data arrival time' in blk else []
    cc=[c for c in cc if c]
    print(f'   arrival {a.group(1) if a else "?"} required {m.group(1) if m else "?"} capture clk@{cc[-1].group(2) if cc else "?"}')
