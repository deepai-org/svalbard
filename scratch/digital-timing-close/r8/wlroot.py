#!/usr/bin/env python3
"""wlroot.py <pkl>: attribute net HPWL (incl. buffer trees) to the root driver's hierarchy."""
import sys,re,pickle,collections
comp,pins,nets,res=pickle.load(open(sys.argv[1],'rb'))
OUT={'Z','ZN','Q','QN','CO','S'}
drv={}; inp=collections.defaultdict(list)
for n,cs in nets.items():
    for i,p in cs:
        if i=='PIN': continue
        if p in OUT: drv[n]=i
        else: inp[i].append(n)
isbuf=lambda i: re.search(r'__(clk)?buf_\d+$',comp[i][0]) is not None
def root(n,d=0):
    i=drv.get(n)
    if i is None or d>60 or not isbuf(i) or not inp[i]: return n,i
    return root(inp[i][0],d+1)
def key(n,i):
    s=(i or n).replace('\\','')
    if n in pins or (i is None): return 'PORT '+re.sub(r'\[.*','',n.replace('\\',''))[:6]
    parts=s.split('.')
    k='.'.join(parts[:3 if parts[0]=='digital' else 2]); k=re.sub(r'\[\d+\]','[]',k); k=re.sub(r'_gf180.*','',k)
    return k[:34]
W=collections.Counter(); C=collections.Counter(); bufw=0; clk=0
rootw=collections.Counter(); rootfo=collections.Counter()
for n,v in res.items():
    r,i=root(n)
    if 'clknet' in n or 'delaynet' in n: k='CLOCKTREE'
    else: k=key(r,i)
    W[k]+=v[0]; C[k]+=1; rootw[r]+=v[0]; rootfo[r]+=v[1]-1
    if r!=n: bufw+=v[0]
tot=sum(W.values()); print('total',round(tot),'in buffered subnets',round(bufw))
for k,w in W.most_common(45): print(f'{w:9.0f} {100*w/tot:5.1f}% {C[k]:6d}  {k}')
print('--- top root nets (whole buffer tree)')
for r,w in rootw.most_common(60): print(round(w),rootfo[r],r[:110])
