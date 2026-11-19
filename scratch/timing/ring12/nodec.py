import sys,re,collections
t=open(sys.argv[1]).read()
i=t.index('.subckt ct_ring9 ');j=t.index('\n.ends',i);s=t[i:j]
c=collections.Counter()
for l in s.splitlines():
  p=l.split()
  if p and p[0][0] in 'Cc' and len(p)>=4:
    v=p[3]; m=re.match(r'([\d.eE+-]+)([fpa]?)',v); x=float(m.group(1))*{'f':1,'p':1e3,'a':1e-3,'':1e15}[m.group(2)]
    for n in p[1:3]: c[n]+=x
print(sys.argv[1], {n:round(c[n],2) for n in ['P0','N0','P1','N1','P2','N2','P3','N3']+[f'A{k}' for k in range(8)]+[f'O{k}' for k in range(8)]})
