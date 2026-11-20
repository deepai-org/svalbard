import pya
for g,t in (('/repo/scratch/wired_rx/r10cap/r7e/gen/wrx_cap.gds','pt_wrx_cap'),('/repo/scratch/wired_rx/r10ptrim/l8/work/top/pt_ptrim.gds','pt_ptrim')):
    try:
        ly=pya.Layout(); ly.read(g); c=ly.cell(t); A=c.dbbox().area()
        for L in ((46,0),(81,0)):
            r=pya.Region(c.begin_shapes_rec(ly.layer(*L))).merged(); a=r.area()*ly.dbu**2
            print(t,L,round(a),'um2',round(100*a/A,1),'%')
    except Exception as e: print(t,'ERR',e)
