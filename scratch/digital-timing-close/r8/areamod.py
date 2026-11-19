#!/usr/bin/env python3
"""areamod.py <pkl> [depth]: placed cell area by module; inserted buffers attributed to the root driver's module."""
import sys,re,pickle,collections
comp,pins,nets,res=pickle.load(open(sys.argv[1],'rb')); depth=int(sys.argv[2]) if len(sys.argv)>2 else 3
lib=open('/home/ubuntu/svalbard/projects/programmable_transceiver_platform/verification/digital_hardening/liberty/gf180mcu_fd_sc_mcu7t5v0__ss_032C_3v15.lib').read()
area={m.group(1):float(m.group(2)) for m in re.finditer(r'cell\s*\(\s*"?(\w+)"?\s*\)\s*\{[^}]*?area\s*:\s*([\d.]+)',lib)}
OUT={'Z','ZN','Q','QN','CO','S'}
drv={}; inp=collections.defaultdict(list)
for n,cs in nets.items():
    for i,p in cs:
        if i=='PIN': continue
        if p in OUT: drv[n]=i
        else: inp[i].append(n)
def modof(i):
    s=i.replace('\\',''); s=re.sub(r'_gf180.*','',s); s=re.sub(r'\[[^\]]*\]','',s)
    p=s.split('.'); d=depth if p[0]=='digital' else depth-1
    return '.'.join(p[:d]) if len(p)>d else ('.'.join(p[:-1]) or '(top:'+re.sub(r'\d+$','',p[0])[:12]+')')
INS=re.compile(r'^(fanout|wire|max_cap|max_length|rebuffer|split|clone|hold|input|output|gain|clkbuf|clkload|delaybuf|ANTENNA|place|load_slew|buffer)\d*')
def owner(i,d=0):
    s=i.replace('\\','')
    if not INS.match(s) : return modof(i),'logic'
    if s.startswith(('clkbuf','clkload','delaybuf')): return 'CLOCKTREE','clk'
    if d>80 or not inp[i]: return '(port/unknown)','buf'
    for n in inp[i]:
        j=drv.get(n)
        if j is None: return 'PORTBUF','buf'
        m,_=owner(j,d+1); return m,'buf'
A=collections.Counter(); B=collections.Counter(); F=collections.Counter(); T=collections.Counter()
for i,(c,x,y,st) in comp.items():
    a=area.get(c)
    if a is None:
        T[re.sub(r'.*__','',c)]+=1; continue
    if 'filltie' in c or 'endcap' in c or 'fill' in c: A['TAP/ENDCAP']+=a; continue
    m,k=owner(i)
    A[m]+=a
    if k=='buf': B[m]+=a
    if '__dff' in c or 'latq' in c: F[m]+=1
tot=sum(A.values())
print(f"{'module':36s}  mm2     %    of which inserted buffers  FF")
for k,v in A.most_common(48): print(f"{k:36s} {v/1e6:.4f} {100*v/tot:5.1f}%  {B[k]/1e6:.4f}  {F[k]:5d}")
print('total',round(tot/1e6,4),'buffers',round(sum(B.values())/1e6,4),'ff',sum(F.values()),'noarea',dict(T))
