import re,sys,collections
# routed DEF: per-net wire length (um) of host-link nets
d=open(sys.argv[1]).read(); u=float(re.search(r'UNITS DISTANCE MICRONS (\d+)',d)[1])
nets=d[d.index('\nNETS'):d.index('END NETS')]
L={}
for m in re.finditer(r'\n- (\S+)(.*?);',nets,re.S):
  n,b=m.groups()
  if not re.match(r'(h2d|d2h)_|host_word_clk',n): continue
  t=0
  for seg in re.split(r'NEW|ROUTED',b):
    pts=re.findall(r'\(\s*(\S+)\s+(\S+)(?:\s+\S+)?\s*\)',seg); prev=None
    for x,y in pts:
      if prev is None: prev=(float(x),float(y)); continue
      x=prev[0] if x=='*' else float(x); y=prev[1] if y=='*' else float(y)
      t+=abs(x-prev[0])+abs(y-prev[1]); prev=(x,y)
  L[n]=t/u
g=collections.defaultdict(list)
for n,v in L.items(): g[n.split('_')[0]].append((n,v))
for k,v in sorted(g.items()):
  vs=[a for _,a in v]; print(k,len(vs),'min %.0f max %.0f spread %.0f mean %.0f'%(min(vs),max(vs),max(vs)-min(vs),sum(vs)/len(vs)))
  print('  ',' '.join('%s=%.0f'%(n,a) for n,a in sorted(v)))
