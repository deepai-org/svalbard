#!/usr/bin/env python3
"""defwl.py <def>: HPWL per net from a placed DEF; summaries by port class / hierarchy / fanout."""
import sys,re,collections,pickle
f=open(sys.argv[1]); U=2000.0
comp={}; pins={}; nets={}
sec=None; buf=''
for line in f:
    s=line.strip()
    if s.startswith('UNITS'): U=float(s.split()[3])
    if s.startswith('COMPONENTS '): sec='C'; continue
    if s.startswith('PINS '): sec='P'; continue
    if s.startswith('NETS '): sec='N'; continue
    if s.startswith('SPECIALNETS '): sec='S'; continue
    if s.startswith('END '): sec=None; buf=''; continue
    if sec in('C','P','N'):
        buf+=' '+s
        if s.endswith(';'):
            t=buf; buf=''
            if sec=='C':
                m=re.match(r'\s*- (\S+) (\S+)',t); p=re.search(r'(PLACED|FIXED) \( (-?\d+) (-?\d+) \)',t)
                if m and p: comp[m.group(1)]=(m.group(2),int(p.group(2))/U,int(p.group(3))/U,p.group(1))
            elif sec=='P':
                m=re.match(r'\s*- (\S+) \+ NET (\S+)',t); p=re.search(r'(PLACED|FIXED) \( (-?\d+) (-?\d+) \)',t)
                if m and p: pins[m.group(1)]=(int(p.group(2))/U,int(p.group(3))/U)
            else:
                m=re.match(r'\s*- (\S+)',t)
                conns=re.findall(r'\( (\S+) (\S+) \)',t.split('+')[0])
                nets[m.group(1)]=conns
res={}
for n,cs in nets.items():
    xs=[];ys=[];port=None
    for i,p in cs:
        if i=='PIN':
            port=p
            if p in pins: xs.append(pins[p][0]); ys.append(pins[p][1])
        elif i in comp: xs.append(comp[i][1]); ys.append(comp[i][2])
    if len(xs)<2: continue
    res[n]=(max(xs)-min(xs)+max(ys)-min(ys),len(cs),port)
pickle.dump((comp,pins,nets,res),open(sys.argv[2] if len(sys.argv)>2 else 'wl.pkl','wb'))
tot=sum(v[0] for v in res.values())
print('nets',len(res),'HPWL total um',round(tot),'avg',round(tot/len(res),1))
pt=[v for v in res.values() if v[2]]
print('port nets',len(pt),'HPWL',round(sum(v[0] for v in pt)),'avg',round(sum(v[0] for v in pt)/max(1,len(pt)),1))
cls=collections.Counter(); cn=collections.Counter()
for n,v in res.items():
    if v[2]:
        k='port:'+re.sub(r'\[.*','',v[2]); k=re.sub(r'_[a-z0-9]+$','',k) if k.startswith('port:c_') else k
    else:
        k='.'.join(n.replace('\\','').split('.')[:3]); k=re.sub(r'\[\d+\]','[]',k); k=re.sub(r'_\d+_?$','',k)[:40]
    cls[k]+=v[0]; cn[k]+=1
for k,w in cls.most_common(60): print(f'{w:10.0f} {cn[k]:6d} {w/cn[k]:7.1f}  {k}')
print('--- by fanout')
fb=collections.Counter(); fc=collections.Counter()
for v in res.values():
    b=min(v[1],20); fb[b]+=v[0]; fc[b]+=1
for b in sorted(fb): print(b,fc[b],round(fb[b]),round(fb[b]/fc[b],1))
print('--- top nets')
for n,v in sorted(res.items(),key=lambda x:-x[1][0])[:40]: print(round(v[0]),v[1],v[2],n[:100])
