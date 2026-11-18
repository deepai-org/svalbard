import sys, klayout.db as k
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
gds, top, x1,y1,x2,y2, out = sys.argv[1], sys.argv[2], *map(float, sys.argv[3:7]), sys.argv[7]
layers = sys.argv[8].split(',') if len(sys.argv)>8 else ['M2','M3','M4','M5']
L=k.Layout(); L.read(gds); t=L.cell(top); dbu=L.dbu
LY={'M1':(34,0,'gray'),'M2':(36,0,'tab:blue'),'M3':(42,0,'tab:green'),'M4':(46,0,'tab:orange'),'M5':(81,0,'tab:red'),'V1':(35,0,'k'),'V2':(38,0,'navy'),'V3':(40,0,'darkgreen'),'V4':(41,0,'purple'),'COMP':(22,0,'olive'),'PAD':(37,0,'pink')}
fig,axs=plt.subplots(1,len(layers),figsize=(7*len(layers),7*(y2-y1)/(x2-x1)+1))
if len(layers)==1: axs=[axs]
box=k.Box(int(x1/dbu),int(y1/dbu),int(x2/dbu),int(y2/dbu))
for ax,ls in zip(axs,layers):
    for ln in ls.split('+'):
        l,d,c=LY[ln]; li=L.find_layer(l,d)
        if li is None: continue
        r=k.Region(t.begin_shapes_rec_overlapping(li,box)); r.merge(); r&=k.Region(box)
        for p in r.each():
            for hull in [p.each_point_hull()]:
                pts=[(q.x*dbu,q.y*dbu) for q in hull]
                ax.add_patch(Polygon(pts,closed=True,fc=c,ec='k',lw=.3,alpha=.45 if not ln.startswith('V') else 1))
    ax.set_xlim(x1,x2); ax.set_ylim(y1,y2); ax.set_aspect('equal'); ax.set_title(ls); ax.grid(True,lw=.2)
plt.tight_layout(); plt.savefig(out,dpi=70)
