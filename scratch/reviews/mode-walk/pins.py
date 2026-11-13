#!/usr/bin/env python3
"""Collect .subckt pin lists (with file:line) from every spice file under analog/ (source + generated LVS)."""
import re,sys,os,json
ROOT='/home/ubuntu/svalbard/projects/programmable_transceiver_platform'
def subckts(path):
    out={}
    try: lines=open(path,errors='replace').read().split('\n')
    except Exception: return out
    i=0
    while i<len(lines):
        l=lines[i]
        if l.lower().startswith('.subckt'):
            start=i+1; toks=l.split()[1:]
            j=i+1
            while j<len(lines) and lines[j].startswith('+'):
                toks+=lines[j][1:].split(); j+=1
            name=toks[0]; pins=[t for t in toks[1:] if '=' not in t]
            out[name]=(pins,start)
            i=j
        else: i+=1
    return out
def collect():
    db={}
    for d,_,fs in os.walk(os.path.join(ROOT,'analog')):
        for f in fs:
            if f.endswith('.spice') or f.endswith('.cdl') or f.endswith('.sp'):
                p=os.path.join(d,f)
                if os.path.getsize(p)>80e6: continue
                for n,(pins,ln) in subckts(p).items():
                    db.setdefault(n,[]).append((os.path.relpath(p,ROOT),ln,pins))
    return db
if __name__=='__main__':
    db=collect()
    json.dump(db,open(os.path.join(os.path.dirname(__file__),'pins.json'),'w'))
    print(len(db),'subckts')
