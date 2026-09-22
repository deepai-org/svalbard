"""Audited positive-resistor DC solver shared by sensitivity screens."""
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import spsolve
def solve(edges,source,loads):
 nodes=sorted({n for a,b,r in edges for n in [a,b]}-{source});index={n:i for i,n in enumerate(nodes)}
 row=[];col=[];value=[]
 for a,b,r in edges:
  assert r>0;g=1/r
  for x,y in [(a,b),(b,a)]:
   if x!=source:
    row.append(index[x]);col.append(index[x]);value.append(g)
    if y!=source:row.append(index[x]);col.append(index[y]);value.append(-g)
 matrix=coo_matrix((value,(row,col)),shape=(len(nodes),len(nodes))).tocsr()
 rhs=np.zeros(len(nodes))
 for n,current in loads.items():
  assert n!=source;rhs[index[n]]+=current
 v=spsolve(matrix,rhs);assert np.isfinite(v).all()
 residual=float(np.max(np.abs(matrix@v-rhs)));assert residual<1e-8,residual
 d={n:float(v[i]) for n,i in index.items()};d[source]=0.
 feed=sum(d[b]/r if a==source else d[a]/r if b==source else 0 for a,b,r in edges)
 assert abs(feed-sum(loads.values()))<1e-8,(feed,sum(loads.values()))
 assert min(d.values())>-1e-8
 return d,residual,feed
