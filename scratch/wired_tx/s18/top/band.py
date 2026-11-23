import sys, conn
gds = sys.argv[1]; x0,x1,y0,y1 = map(float, sys.argv[2:6]); L = int(sys.argv[6]) if len(sys.argv)>6 else 4
sh, comp, lab = conn.build(gds, 'pt_wiredtx8')
rows = []
for i,(k,l,r) in enumerate(sh):
    if k=='m' and l==L and r[0]<x1 and r[2]>x0 and r[1]<y1 and r[3]>y0:
        n = lab.get(comp[i], set())
        top = sorted(x for x in n if ':' not in x); ch = sorted(n - set(top))
        rows.append((top[:3] or ch[:3] or [f'comp{comp[i]}'], r[:4]))
rows.sort(key=lambda z:(str(z[0]), z[1][1], z[1][0]))
for n, r in rows: print(n, r)
