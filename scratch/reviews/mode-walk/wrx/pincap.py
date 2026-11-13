#!/usr/bin/env python3
"""Rough pin capacitance from a Magic-extracted flat netlist: gate area*Cox(8.6 fF/um2 @3.3V GF180 ~ tox 8nm -> ~4.3 fF/um2) + 2*Cov + extracted C lines."""
import re,sys,collections
COX=4.5e-15  # F/um^2 (3.3 V device, tox ~7.6-8 nm)
COV=0.35e-15 # F/um per edge
def run(path, sub, pins):
    txt=open(path).read()
    txt=re.sub(r'\n\+\s*',' ',txt)
    m=re.search(r'^\.subckt\s+%s\b.*?^\.ends'%sub, txt, re.M|re.S|re.I)
    body=m.group(0)
    gate=collections.Counter(); par=collections.Counter(); sd=collections.Counter()
    for ln in body.splitlines():
        t=ln.split()
        if not t: continue
        if t[0][0] in 'Xx' and len(t)>5 and ('fet' in ln):
            d,g,s,b=t[1:5]
            kv=dict(x.split('=') for x in t[6:] if '=' in x)
            def num(v):
                v=v.lower()
                return float(v[:-1]) if v.endswith('u') else float(v)*1e6
            try:
                w=num(kv.get('w','0')); l=num(kv.get('l','0')); mm=float(kv.get('m',kv.get('nf','1')) if 'm' in kv else 1)
            except Exception: continue
            if g in pins: gate[g]+= (w*l*COX+2*w*COV)*mm
            for n in (d,s):
                if n in pins: sd[n]+= w*1.0e-15*mm
        elif t[0][0] in 'Cc' and len(t)>=4:
            a,b=t[1],t[2]
            v=t[3].lower()
            try:
                val=float(v[:-1])*{'f':1e-15,'p':1e-12,'a':1e-18}[v[-1]] if v[-1] in 'fpa' else float(v)
            except Exception: continue
            if a in pins: par[a]+=val
            if b in pins: par[b]+=val
    for p in pins:
        print(f'{sub:12s} {p:8s} gate {gate[p]*1e15:7.1f} fF  wire/par {par[p]*1e15:7.1f} fF  sd {sd[p]*1e15:6.1f}  total {(gate[p]+par[p]+sd[p])*1e15:7.1f} fF')
if __name__=='__main__':
    run(sys.argv[1], sys.argv[2], sys.argv[3].split(','))
